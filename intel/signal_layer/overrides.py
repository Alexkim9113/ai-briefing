# PHASE 5A — Human Override(운영자 지시 16번). Change/Event Layer와 동일한 패턴.
import json
from pathlib import Path

OVERRIDES_PATH = Path(__file__).resolve().parent / "signal_overrides.json"


def load_overrides(path=OVERRIDES_PATH):
    if not path.exists():
        return {"human_confirmed": [], "human_rejected": []}
    return json.loads(path.read_text(encoding="utf-8"))


def apply_overrides(signals, overrides):
    for sid in overrides.get("human_confirmed", []):
        if sid in signals:
            signals[sid]["override_status"] = "HUMAN_CONFIRMED"
    for sid in overrides.get("human_rejected", []):
        if sid in signals:
            signals[sid]["override_status"] = "HUMAN_REJECTED"
            signals[sid]["status"] = "REJECTED"
    return signals
