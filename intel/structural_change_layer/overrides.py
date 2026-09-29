# PHASE 5C — Human Override(운영자 지시 22번). 하위 Layer와 동일한 패턴.
import json
from pathlib import Path

OVERRIDES_PATH = Path(__file__).resolve().parent / "structural_change_overrides.json"


def load_overrides(path=OVERRIDES_PATH):
    if not path.exists():
        return {"human_confirmed": [], "human_rejected": []}
    return json.loads(path.read_text(encoding="utf-8"))


def apply_overrides(structural_changes, overrides):
    for scid in overrides.get("human_confirmed", []):
        if scid in structural_changes:
            structural_changes[scid]["override_status"] = "HUMAN_CONFIRMED"
    for scid in overrides.get("human_rejected", []):
        if scid in structural_changes:
            structural_changes[scid]["override_status"] = "HUMAN_REJECTED"
            structural_changes[scid]["status"] = "REJECTED"
    return structural_changes
