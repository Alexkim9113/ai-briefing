# STAGE 7 PHASE B — Retriever. 섹션 17 SEARCH BROAD, CONTEXT STRICT: recall 단계에서는
# scope 차원 중 하나라도 맞으면 넓게 모은다(OR). 좁히는 것은 reranker의 몫이지 retriever가
# 미리 걸러서 중요한 걸 놓치지 않는다.
import adapter
import dedup as dedup_mod
import provenance as provenance_mod
import reranker
from retrieval_planner import plan_retrieval


# 실제 corpus pilot(섹션 63)에서 발견한 문제 수정: scope 신호가 전혀 없을 때 intent를
# 무시하고 index 전체를 반환하면, 예를 들어 COUNTER_EVIDENCE_SEARCH 질문이 아무 관련 없는
# FACT/EVENT 20건을 "결과"로 돌려줘서 실제로는 0건이라는 사실을 숨기게 된다(섹션 63
# 리뷰 기준: FALSE CONNECTION / MISSING IMPORTANT EVIDENCE). intent가 특정 note_type만
# 의미 있게 다루는 경우 broad recall도 그 note_type으로 제한한다 - "모르면 전체 반환"이
# 아니라 "모르면 intent가 말이 되는 범위로 제한 후 0건이면 정직하게 0건".
_INTENT_NOTE_TYPES = {
    "FACT_LOOKUP": ("FACT",),
    "EVENT_LOOKUP": ("EVENT",),
    "CHANGE_ANALYSIS": ("EVENT", "CHANGE"),
    "TREND_ANALYSIS": ("CHANGE",),
    "COUNTER_EVIDENCE_SEARCH": ("FACT", "EVENT", "CHANGE"),  # 아래에서 추가로 필터링
    "HYPOTHESIS_TEST": ("FACT", "EVENT", "CHANGE"),
}


def retrieve(intent, scope, note_type_filter=None, limit=20):
    plan = plan_retrieval(intent)
    notes = adapter.load_notes()
    index = adapter.build_index(notes)  # REJECTED 기본 제외 (섹션 31)

    candidates = []
    matched_any_filter = False
    for entity in (scope.get("ENTITY") or []):
        matched_any_filter = True
        candidates += adapter.filter_index(index, entity=entity)
    for concept in (scope.get("CONCEPT") or []):
        matched_any_filter = True
        candidates += adapter.filter_index(index, concept=concept)

    if not matched_any_filter:
        if intent == "UNKNOWN":
            # 섹션 0(Te CONTINUE) CORE RULE: NO EVIDENCE != FILL WITH SOMETHING. intent조차
            # 못 알아낸 질문에 scope 신호까지 없으면 아무 근거도 없이 index 전체를 "관련
            # 있다"고 우기지 않는다 - 정직하게 0건.
            candidates = []
        else:
            # intent는 알지만(예: GENERAL_SYNTHESIS, "최근 Policy 변화는?") scope로 좁힐
            # 신호가 없는 경우 - intent가 의미 있는 note_type으로 제한한 broad recall.
            allowed_types = _INTENT_NOTE_TYPES.get(intent)
            candidates = [c for c in index if c["note_type"] in allowed_types] if allowed_types else list(index)

    if intent == "COUNTER_EVIDENCE_SEARCH":
        # counter_evidence_ids가 실제로 있는 note만 - 없으면(현재 corpus 전부 그렇다) 0건이
        # 맞다(Stage 6 readiness: 실전 Counter Evidence 0건, 정직한 결과이지 결함이 아님).
        candidates = [c for c in candidates if notes.get(c["note_id"], {}).get("counter_evidence_ids")]

    if note_type_filter:
        candidates = [c for c in candidates if c["note_type"] in note_type_filter]

    candidates = dedup_mod.dedup_by_note_id(candidates)
    candidates = reranker.rerank(candidates, scope)[:limit]

    documents = adapter.load_documents()
    results = []
    for row in candidates:
        note = notes.get(row["note_id"], {})
        results.append({
            "note_id": row["note_id"],
            "note_type": row["note_type"],
            "statement": row["statement"],
            "concepts": row["concepts"],
            "entities": row["entities"],
            "provenance": provenance_mod.reconstruct(note, documents),
        })

    return {
        "plan": plan,
        "total_candidates_before_limit": len(candidates),
        "results": results,
    }
