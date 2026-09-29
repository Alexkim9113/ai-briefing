# PHASE 5D — Human Override(운영자 지시 37번). 7개 객체 타입 공통 override 파일 구조:
# {"<collection_name>": {"human_confirmed": [...], "human_rejected": [...]}}
import json
from pathlib import Path

OVERRIDES_PATH = Path(__file__).resolve().parent / "structural_analysis_overrides.json"
COLLECTIONS = ("drivers", "dependencies", "controls", "power_shifts", "value_shifts",
               "scarcity_shifts", "bottlenecks")


def load_overrides(path=OVERRIDES_PATH):
    if not path.exists():
        return {c: {"human_confirmed": [], "human_rejected": []} for c in COLLECTIONS}
    data = json.loads(path.read_text(encoding="utf-8"))
    for c in COLLECTIONS:
        data.setdefault(c, {"human_confirmed": [], "human_rejected": []})
    return data


def apply_overrides(collection, overrides_for_collection):
    for oid in overrides_for_collection.get("human_confirmed", []):
        if oid in collection:
            collection[oid]["override_status"] = "HUMAN_CONFIRMED"
            collection[oid]["status"] = "HUMAN_CONFIRMED"
    for oid in overrides_for_collection.get("human_rejected", []):
        if oid in collection:
            collection[oid]["override_status"] = "HUMAN_REJECTED"
            collection[oid]["status"] = "HUMAN_REJECTED"
    return collection
