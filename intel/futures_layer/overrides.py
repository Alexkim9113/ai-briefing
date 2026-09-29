# PHASE 5F — Human Override. 8개 override 가능 객체 타입(Forecast Observation/Revision은
# 이벤트 로그라 override 대상에서 제외).
import json
from pathlib import Path

OVERRIDES_PATH = Path(__file__).resolve().parent / "futures_overrides.json"
COLLECTIONS = ("trajectories", "outlooks", "alternative_paths", "scenarios",
               "second_order_effects", "third_order_effects", "forecasts", "futures_assessments")

_STATUS_FIELD = {"futures_assessments": "assessment_status"}


def load_overrides(path=OVERRIDES_PATH):
    if not path.exists():
        return {c: {"human_confirmed": [], "human_rejected": []} for c in COLLECTIONS}
    data = json.loads(path.read_text(encoding="utf-8"))
    for c in COLLECTIONS:
        data.setdefault(c, {"human_confirmed": [], "human_rejected": []})
    return data


def apply_overrides(name, collection, overrides_for_collection):
    status_field = _STATUS_FIELD.get(name, "status")
    for oid in overrides_for_collection.get("human_confirmed", []):
        if oid in collection:
            if "override_status" in collection[oid]:
                collection[oid]["override_status"] = "HUMAN_CONFIRMED"
            if status_field in collection[oid]:
                collection[oid][status_field] = "HUMAN_CONFIRMED"
    for oid in overrides_for_collection.get("human_rejected", []):
        if oid in collection:
            if "override_status" in collection[oid]:
                collection[oid]["override_status"] = "HUMAN_REJECTED"
            if status_field in collection[oid]:
                collection[oid][status_field] = "HUMAN_REJECTED"
    return collection
