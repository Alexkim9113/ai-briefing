# PHASE 5E — Human Override(운영자 지시 36번). 11개 객체 타입 공통 override 파일 구조:
# {"<collection_name>": {"human_confirmed": [...], "human_rejected": [...]}}
import json
from pathlib import Path

OVERRIDES_PATH = Path(__file__).resolve().parent / "epistemic_overrides.json"
COLLECTIONS = ("counter_evidence", "contradictions", "tensions", "paradox_candidates",
               "uncertainties", "assumptions", "falsifiers", "evidence_gaps",
               "alternative_explanations", "view_revisions", "epistemic_assessments")

_STATUS_FIELD = {
    "uncertainties": "status", "evidence_gaps": "status", "falsifiers": "status",
    "epistemic_assessments": "assessment_status",
}


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
