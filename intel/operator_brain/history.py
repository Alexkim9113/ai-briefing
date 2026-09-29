# STAGE 7 PHASE K — Operator History. Te CONTINUE 섹션 19: Operator interaction history와
# canonical Knowledge Memory를 분리한다. History 자체는 Evidence가 되지 않는다 - 나중에
# retrieval이 operator_history.json을 FACT/EVENT 소스처럼 검색하면 안 된다(이 모듈은
# 의도적으로 retriever.py의 조회 대상 목록에 없다).
import json
from pathlib import Path

HISTORY_PATH = Path(__file__).resolve().parent / "operator_history.json"


def _load():
    if not HISTORY_PATH.exists():
        return []
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save(entries):
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=1)
        f.write("\n")


def record_interaction(query_record, response_text, candidate_ids, model, prompt_version,
                        cost_estimate, now_iso):
    """섹션 19 최소 필드: question/mode/scope/retrieved object IDs/context hash/response/
    candidate objects/model/prompt_version/cost/timestamp."""
    entry = {
        "query_id": query_record.get("query_id"),
        "question": query_record.get("normalized_text"),
        "mode": query_record.get("mode"),
        "scope": query_record.get("scope"),
        "retrieved_object_ids": query_record.get("context_pack", {}).get("object_references", []),
        "context_hash": query_record.get("context_hash"),
        "response_text": response_text,
        "candidate_ids": candidate_ids,
        "model": model,
        "prompt_version": prompt_version,
        "cost_estimate": cost_estimate,
        "timestamp": now_iso,
    }
    entries = _load()
    entries.append(entry)
    _save(entries)
    return entry


def list_history(limit=50):
    return _load()[-limit:]
