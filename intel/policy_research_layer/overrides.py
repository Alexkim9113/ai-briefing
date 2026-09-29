# PHASE 5G — Human Override. 11개 컬렉션.
import json
from pathlib import Path

OVERRIDES_PATH = Path(__file__).resolve().parent / "policy_research_overrides.json"
COLLECTIONS = ("policy_questions", "policy_options", "policy_tradeoffs", "stakeholder_impacts",
               "policy_constraints", "policy_uncertainties", "research_questions", "research_gaps",
               "evidence_needs", "monitoring_indicators", "policy_research_assessments")

_STATUS_FIELD = {"policy_research_assessments": "assessment_status"}


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
