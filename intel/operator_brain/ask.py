# STAGE 7 PHASE E — Retrieval-Only Ask METAXIS (Claude=0). 섹션 8: Claude AUTO-CALL OFF,
# DEFAULT RETRIEVAL_ONLY. 이 함수가 현재 ask() 파이프라인의 최종 진입점이다 - Claude
# Adapter(PHASE G)가 붙기 전까지는 이게 곧 "Ask METAXIS"의 전체 기능이다.
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import stable_response_id  # noqa: E402
from pipeline import ask as run_pipeline  # noqa: E402
from response_parser import format_retrieve_answer  # noqa: E402
from schema import new_structured_response_shell  # noqa: E402


def ask_metaxis(question_text, mode="RETRIEVE"):
    record = run_pipeline(question_text, mode)
    answer_text = format_retrieve_answer(record["context_pack"], record["evidence_sufficiency"])

    response_id = stable_response_id(record["query_id"], record["context_hash"])
    structured = new_structured_response_shell(
        response_id, record["query_id"], record["created_at"],
        record["mode"], record["intent"], record["scope"])
    structured["factual_claims"] = [f["statement"] for f in record["context_pack"]["known_facts"]]
    structured["used_fact_ids"] = [f["note_id"] for f in record["context_pack"]["known_facts"]]
    structured["used_event_ids"] = [e["note_id"] for e in record["context_pack"]["key_events"]]
    structured["used_change_ids"] = [c["note_id"] for c in record["context_pack"]["observed_changes"]]
    structured["used_source_ids"] = record["context_pack"]["source_references"]
    structured["claim_ceiling"] = record["evidence_sufficiency"]["claim_ceiling"]
    structured["evidence_sufficiency"] = record["evidence_sufficiency"]["state"]
    structured["context_hash"] = record["context_hash"]
    structured["model"] = None  # PHASE E: Claude 미호출
    structured["cache_status"] = "MISS"

    return {
        "answer_text": answer_text,
        "structured_response": structured,
        "query_record": record,
    }


if __name__ == "__main__":
    import json
    result = ask_metaxis("최근 Nvidia 규제 관련 사건은?")
    print(result["answer_text"])
    print()
    print(json.dumps(result["structured_response"], ensure_ascii=False, indent=1))
