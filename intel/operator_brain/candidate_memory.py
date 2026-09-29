# STAGE 7 PHASE J — Candidate Memory. 섹션 52 / Te CONTINUE 섹션 18: Claude가 생성한
# QUESTION/HYPOTHESIS/INSIGHT/CONNECTION/POLICY_IDEA/RESEARCH_IDEA는 절대 자동으로
# Stage 6 canonical memory가 되지 않는다. 전부 CANDIDATE 상태로만 저장하고, 운영자가
# 명시적으로 승인(SAVE TO MEMORY)해야만 Stage 6 promotion 후보가 된다 - 이 모듈 자체는
# Stage 6 notes.json을 절대 쓰지 않는다(별도 파일, 별도 책임).
import hashlib
import json
from pathlib import Path

CANDIDATE_PATH = Path(__file__).resolve().parent / "candidate_memory.json"
CANDIDATE_TYPES = ("QUESTION", "HYPOTHESIS", "INSIGHT", "CONNECTION", "POLICY_IDEA", "RESEARCH_IDEA")
CANDIDATE_STATUSES = ("CANDIDATE", "SAVE_REQUESTED", "DISCARDED")


def _load():
    if not CANDIDATE_PATH.exists():
        return {}
    try:
        with open(CANDIDATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save(store):
    with open(CANDIDATE_PATH, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")


def new_candidate(candidate_type, statement, query_id, now_iso, source_object_ids=None):
    assert candidate_type in CANDIDATE_TYPES, f"unknown candidate_type: {candidate_type}"
    cid = "cand_" + hashlib.sha1(f"{candidate_type}|{statement}|{query_id}".encode("utf-8")).hexdigest()[:16]
    return {
        "candidate_id": cid, "candidate_type": candidate_type, "statement": statement,
        "query_id": query_id, "source_object_ids": source_object_ids or [],
        "status": "CANDIDATE", "created_at": now_iso,
    }


def save_candidate(candidate):
    """섹션 52: NO AUTOMATIC MEMORY POLLUTION - 이 함수는 candidate_memory.json에만 쓴다.
    Stage 6 notes.json으로의 실제 promotion은 이 모듈의 책임이 아니고, 운영자가
    request_promotion()으로 SAVE_REQUESTED로 표시한 뒤 별도 사람 검토를 거쳐야 한다."""
    store = _load()
    store[candidate["candidate_id"]] = candidate
    _save(store)
    return candidate


def request_promotion(candidate_id):
    """운영자가 UI에서 'SAVE TO MEMORY'를 눌렀을 때만 호출된다 - 이 호출 자체도 아직
    Stage 6 canonical memory에 쓰지 않는다. 사람 검토를 거쳐야 하는 대기 상태로만 바꾼다."""
    store = _load()
    if candidate_id not in store:
        return None
    store[candidate_id]["status"] = "SAVE_REQUESTED"
    _save(store)
    return store[candidate_id]


def list_candidates(status=None):
    store = _load()
    values = list(store.values())
    if status:
        values = [v for v in values if v["status"] == status]
    return values
