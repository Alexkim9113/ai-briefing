# STAGE 7 PHASE B — Retriever. 섹션 17 SEARCH BROAD, CONTEXT STRICT: recall 단계에서는
# scope 차원 중 하나라도 맞으면 넓게 모은다(OR). 좁히는 것은 reranker의 몫이지 retriever가
# 미리 걸러서 중요한 걸 놓치지 않는다.
import adapter
import dedup as dedup_mod
import provenance as provenance_mod
import reranker
from retrieval_planner import plan_retrieval


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
        # scope 신호가 전혀 없으면 intent가 허용하는 note_type 전체를 broad recall.
        candidates = list(index)

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
