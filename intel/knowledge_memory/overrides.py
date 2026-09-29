# STAGE 6 — Human Overrides(섹션 38, 71). 사람이 intel/knowledge_memory/overrides.json에
# {note_id: {"human_review_status": ..., "reason": ...}} 를 직접 적으면 그 판단을 따른다.
# 이 세션은 이 파일을 스스로 채우지 않는다 — 오직 읽기만 한다(사람이 검토 후 채워야 함,
# 섹션 65: Human Review).
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
OVERRIDES_PATH = HERE / "overrides.json"

VALID_HUMAN_STATUSES = ("HUMAN_CONFIRMED", "HUMAN_REJECTED", "HUMAN_REVISED")


def load_overrides():
    if not OVERRIDES_PATH.exists():
        return {}
    try:
        with open(OVERRIDES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def apply_overrides(notes_by_id, overrides=None):
    """notes_by_id를 직접 수정하지 않고 새 dict를 반환한다."""
    overrides = overrides if overrides is not None else load_overrides()
    out = {}
    for nid, note in notes_by_id.items():
        note = dict(note)
        ov = overrides.get(nid)
        if ov and ov.get("human_review_status") in VALID_HUMAN_STATUSES:
            note["human_review_status"] = ov["human_review_status"]
            if ov.get("human_review_status") == "HUMAN_REJECTED":
                note["status"] = "REJECTED"
            elif ov.get("human_review_status") == "HUMAN_REVISED" and ov.get("revised_statement"):
                note["statement"] = ov["revised_statement"]
                note["status"] = "REVISED"
        out[nid] = note
    return out
