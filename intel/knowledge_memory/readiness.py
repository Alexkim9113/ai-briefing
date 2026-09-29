# STAGE 6 — Stage 7 Readiness(섹션 72-74). 각 항목을 READY/PARTIAL/NOT_READY로 정직하게
# 평가한다 — 자연 발생 데이터가 없는 것을 억지로 READY로 만들지 않는다(섹션 73).
READINESS_VALUES = ("READY", "PARTIAL", "NOT_READY")


def assess(notes_by_id, relations_by_id, atomizer_metrics, graph_metrics):
    non_rejected = [n for n in notes_by_id.values() if n.get("status") != "REJECTED"]
    has_facts = any(n["note_type"] == "FACT" for n in non_rejected)
    has_events = any(n["note_type"] == "EVENT" for n in non_rejected)
    has_changes = any(n["note_type"] == "CHANGE" for n in non_rejected)
    has_question = any(n["note_type"] == "QUESTION" for n in non_rejected)
    has_hypothesis = any(n["note_type"] == "HYPOTHESIS" for n in non_rejected)
    has_counter_evidence = any(n.get("counter_evidence_ids") for n in non_rejected)
    has_revision = any(n.get("version", 1) > 1 for n in notes_by_id.values())
    broken_provenance = atomizer_metrics.get("broken_provenance_count", 0)

    result = {
        "ATOMIC_MEMORY_READY": "READY" if (has_facts or has_events) else "NOT_READY",
        "PROVENANCE_READY": "READY" if broken_provenance == 0 and (has_facts or has_events) else "PARTIAL",
        "RELATION_READY": "PARTIAL" if relations_by_id else "NOT_READY",  # RELATED_TO뿐이라 PARTIAL 고정
        "QUESTION_MEMORY_READY": "READY" if has_question else "NOT_READY",
        "HYPOTHESIS_MEMORY_READY": "READY" if has_hypothesis else "NOT_READY",
        "COUNTER_EVIDENCE_READY": "READY" if has_counter_evidence else "NOT_READY",
        "REVISION_MEMORY_READY": "READY" if has_revision else "PARTIAL",  # 메커니즘은 있음(memory.py), 실제 발생 0건
        "RETRIEVAL_INDEX_READY": "READY" if notes_by_id else "NOT_READY",
        "OBSIDIAN_EXPORT_READY": "READY" if notes_by_id else "NOT_READY",
    }
    for k, v in result.items():
        assert v in READINESS_VALUES, f"{k}: invalid value {v}"
    return result
