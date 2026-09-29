# PHASE 5B — Human Override(운영자 지시 17번). Change/Signal Layer와 동일한 패턴.
import json
from pathlib import Path

OVERRIDES_PATH = Path(__file__).resolve().parent / "pattern_overrides.json"


def load_overrides(path=OVERRIDES_PATH):
    if not path.exists():
        return {"human_confirmed": [], "human_rejected": []}
    return json.loads(path.read_text(encoding="utf-8"))


def apply_overrides(patterns, overrides):
    for pid in overrides.get("human_confirmed", []):
        if pid in patterns:
            patterns[pid]["override_status"] = "HUMAN_CONFIRMED"
    for pid in overrides.get("human_rejected", []):
        if pid in patterns:
            patterns[pid]["override_status"] = "HUMAN_REJECTED"
            patterns[pid]["status"] = "REJECTED"
    return patterns
