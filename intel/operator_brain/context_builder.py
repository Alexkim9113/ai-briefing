# STAGE 7 PHASE D — Context Pack builder. 섹션 22: Claude에게 raw DB dump 금지, 없는
# 영역은 비운다(Claude가 빈 공간을 자기 지식으로 채우지 못하게). 섹션 18: object
# reference/source reference를 반드시 남겨 provenance 추적 가능하게 한다.
from context_budget import apply_budget
from schema import new_context_pack_shell


def build_context_pack(query_record, retrieval, sufficiency):
    pack = new_context_pack_shell()
    pack["question"] = query_record.get("normalized_text")
    pack["intent"] = query_record.get("intent")
    pack["mode"] = query_record.get("mode")
    pack["scope"] = {k: v for k, v in (query_record.get("scope") or {}).items() if v is not None}

    facts = [r for r in retrieval["results"] if r["note_type"] == "FACT"]
    events = [r for r in retrieval["results"] if r["note_type"] == "EVENT"]
    changes = [r for r in retrieval["results"] if r["note_type"] == "CHANGE"]

    pack["known_facts"] = [{"note_id": f["note_id"], "statement": f["statement"]} for f in facts]
    pack["key_events"] = [{"note_id": e["note_id"], "statement": e["statement"]} for e in events]
    pack["observed_changes"] = [{"note_id": c["note_id"], "statement": c["statement"]} for c in changes]

    # 섹션 22: 이 corpus엔 SIGNAL/PATTERN/STRUCTURAL_CHANGE/COUNTER_EVIDENCE/UNCERTAINTY
    # 실제 데이터가 아직 없다(Stage 6 readiness: 0건, 정직한 결과) - 빈 리스트로 그대로 둔다.
    # Claude가 이 빈 자리를 사실처럼 채우지 못하게 하는 것이 이 구조의 핵심이다.

    pack["object_references"] = [r["note_id"] for r in retrieval["results"]]
    pack["source_references"] = sorted({
        p["document_id"] for r in retrieval["results"] for p in r["provenance"] if p["found"]
    })

    pack["claim_ceiling"] = sufficiency.get("claim_ceiling")
    pack["metrics"] = {
        "evidence_sufficiency": sufficiency.get("state"),
        "supporting_evidence_count": len(retrieval["results"]),
        "counter_evidence_count": 0,
    }

    trimmed_pack, budget_info = apply_budget(pack)
    return trimmed_pack, budget_info
