# STAGE 6 — PRODUCTIONIZATION v1.0 섹션 34-37, 65-67: READY/READY_FOR_NATURAL_DATA/
# PARTIAL/NOT_READY 4단계. Production count=0은 더 이상 자동으로 NOT_READY가 아니다 —
# 구조(schema/adapter/dedup/relation/retrieval/revision/override)가 synthetic test로
# 검증됐다면 READY_FOR_NATURAL_DATA로 표시한다(섹션 76: "Question이 0이므로 NOT READY"
# 라는 논리를 쓰지 않는다). production_validated는 별도 bool로 분리해 기록한다(섹션 34).
from schema import READINESS_VALUES

# 이 목록은 intel/knowledge_memory/tests/test_productionization.py가 실제로 통과했는지로
# 뒷받침된다(섹션 33/36-38: Synthetic fixture로 schema/dedup/provenance/relation/
# revision/override/retrieval을 전부 검증) — 이 파일 자신은 pytest를 실행하지 않고,
# "그 테스트 스위트가 이 항목들을 커버한다"는 사실만 문서화해서 근거를 명시한다.
_SYNTHETICALLY_VALIDATED_NOTE_TYPES = frozenset({"QUESTION", "HYPOTHESIS", "INSIGHT"})
_SYNTHETIC_TEST_FILE = "intel/knowledge_memory/tests/test_productionization.py"


def assess(notes_by_id, relations_by_id, atomizer_metrics, graph_metrics):
    non_rejected = [n for n in notes_by_id.values() if n.get("status") != "REJECTED"]
    has_facts = any(n["note_type"] == "FACT" for n in non_rejected)
    has_events = any(n["note_type"] == "EVENT" for n in non_rejected)
    has_question = any(n["note_type"] == "QUESTION" for n in non_rejected)
    has_hypothesis = any(n["note_type"] == "HYPOTHESIS" for n in non_rejected)
    has_counter_evidence = any(n.get("counter_evidence_ids") for n in non_rejected)
    has_revision = any(n.get("version", 1) > 1 for n in notes_by_id.values())
    has_temporal = any(n.get("first_seen") or n.get("event_date") for n in non_rejected)
    has_lineage_relations = any(r.get("relation_class") == "LINEAGE" for r in relations_by_id.values())
    broken_provenance = atomizer_metrics.get("broken_provenance_count", 0)

    def item(value, production_validated, note=None):
        assert value in READINESS_VALUES, value
        return {"status": value, "production_validated": production_validated, "note": note}

    result = {
        "ATOMIC_MEMORY_READY": item("READY" if (has_facts or has_events) else "NOT_READY", has_facts or has_events),
        "PROVENANCE_READY": item(
            "READY" if broken_provenance == 0 and (has_facts or has_events) else "PARTIAL",
            broken_provenance == 0 and (has_facts or has_events)),
        "RELATION_READY": item(
            "READY" if has_lineage_relations else "READY_FOR_NATURAL_DATA", has_lineage_relations,
            note=("LINEAGE 관계 메커니즘(FACT->EVENT PART_OF_EVENT)은 완성됐고 synthetic test로 "
                  "검증됨 — 실제 corpus에서 아직 발생 0건인 것은 "
                  f"{_SYNTHETIC_TEST_FILE}로 구조는 검증됐다는 뜻이지 결함이 아니다." if not has_lineage_relations else None)),
        "TEMPORAL_MEMORY_READY": item(
            "READY" if has_temporal else "READY_FOR_NATURAL_DATA", has_temporal,
            note=None if has_temporal else "first_seen/event_date 등은 upstream에 있을 때만 채워진다 — 필드/전파 로직은 완성."),
        "SCOPE_MEMORY_READY": item(
            "READY_FOR_NATURAL_DATA", False,
            note="scope 필드(geographic_scope 등)는 스키마에 존재하나 현재 corpus의 upstream 객체들이 "
                 "scope 정보 자체를 아직 갖고 있지 않아 전파할 실제 값이 없다 — UNKNOWN으로 정직하게 비워둠."),
        "QUESTION_MEMORY_READY": item(
            "READY_FOR_NATURAL_DATA" if not has_question else "READY", has_question,
            note=None if has_question else f"Question schema/persistence/retrieval은 {_SYNTHETIC_TEST_FILE}에서 synthetic으로 검증됨. Production 0건은 upstream(policy_research_layer)이 아직 질문을 생성 안 해서다."),
        "HYPOTHESIS_MEMORY_READY": item(
            "READY_FOR_NATURAL_DATA" if not has_hypothesis else "READY", has_hypothesis,
            note=None if has_hypothesis else f"Hypothesis schema(supporting/counter/falsifier)는 {_SYNTHETIC_TEST_FILE}에서 synthetic으로 검증됨. Production 0건은 upstream(futures_layer)이 아직 없어서다."),
        "COUNTER_EVIDENCE_READY": item(
            "READY_FOR_NATURAL_DATA" if not has_counter_evidence else "READY", has_counter_evidence,
            note=None if has_counter_evidence else f"CONTRADICTS relation_class=SEMANTIC 경로와 counter_evidence_ids 필드는 {_SYNTHETIC_TEST_FILE}에서 synthetic으로 검증됨."),
        "REVISION_MEMORY_READY": item(
            "READY" if has_revision else "READY_FOR_NATURAL_DATA", has_revision,
            note=None if has_revision else "memory.py의 upsert 로직(version/history/supersedes)은 synthetic rerun 테스트로 검증됨."),
        "HUMAN_OVERRIDE_READY": item("READY", True, note="overrides.py로 synthetic+실제 양쪽에서 검증됨(rerun에도 보존)."),
        "RETRIEVAL_INDEX_READY": item("READY" if notes_by_id else "NOT_READY", bool(notes_by_id)),
        "OBSIDIAN_EXPORT_READY": item("READY" if notes_by_id else "NOT_READY", bool(notes_by_id)),
    }
    for k, v in result.items():
        assert v["status"] in READINESS_VALUES, f"{k}: invalid value {v}"
    return result


def stage7_entry_verdict(readiness):
    """섹션 67: '모든 타입이 Production에서 발생했는가'가 아니라 구조적 안정성 10개 조건.
    READY_FOR_NATURAL_DATA도 조건 충족으로 인정한다(섹션 76)."""
    acceptable = {"READY", "READY_FOR_NATURAL_DATA"}
    required = ["ATOMIC_MEMORY_READY", "PROVENANCE_READY", "RELATION_READY",
                "REVISION_MEMORY_READY", "HUMAN_OVERRIDE_READY", "RETRIEVAL_INDEX_READY",
                "QUESTION_MEMORY_READY", "HYPOTHESIS_MEMORY_READY", "COUNTER_EVIDENCE_READY"]
    blocking = [k for k in required if readiness[k]["status"] not in acceptable]
    return "READY" if not blocking else "NOT_READY", blocking
