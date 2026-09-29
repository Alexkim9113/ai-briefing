# PHASE 4C — Human Override(운영자 지시 16번). Event Layer와 동일한 패턴.
import json
from pathlib import Path

OVERRIDES_PATH = Path(__file__).resolve().parent / "change_overrides.json"


def load_overrides():
    if not OVERRIDES_PATH.exists():
        return {"human_confirmed": [], "human_rejected": []}
    return json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))


def apply_overrides(changes, overrides):
    for cid in overrides.get("human_confirmed", []):
        if cid in changes:
            changes[cid]["override_status"] = "HUMAN_CONFIRMED"
    for cid in overrides.get("human_rejected", []):
        if cid in changes:
            changes[cid]["override_status"] = "HUMAN_REJECTED"
            changes[cid]["status"] = "REJECTED"
    return changes
