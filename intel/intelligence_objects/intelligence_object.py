# M.6 -- minimal Intelligence Object with revision history (never delete-and-rewrite). Separate
# sidecar (intelligence_objects.json). Only unfilled items this round's real evidence doesn't
# support stay as explicit empty lists / known_gaps entries -- never backfilled with narrative.
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
OBJECTS_PATH = HERE / "intelligence_objects.json"

IMPACT_EVENT_TYPES = (
    "NEW_EVIDENCE_NO_CHANGE", "CLAIM_STRENGTHENED", "CLAIM_WEAKENED", "CLAIM_CONTESTED",
    "STATE_CHANGED", "UNCERTAINTY_REDUCED", "UNCERTAINTY_INCREASED", "GAP_CLOSED",
    "NEW_GAP_DISCOVERED",
)


def _intelligence_id(topic, question):
    return f"intel_{hashlib.sha256(f'{topic}|{question}'.encode()).hexdigest()[:16]}"


def new_intelligence_object(topic, question):
    now = datetime.now(timezone.utc).isoformat()
    return {
        "intelligence_id": _intelligence_id(topic, question), "topic": topic, "question": question,
        "current_state": "UNKNOWN", "key_claims": [], "supporting_evidence": [],
        "counterevidence": [], "alternative_explanations": [], "statistics": [],
        "research_context": [], "policy_context": [], "historical_context": [],
        "geographic_context": [], "temporal_chain": [], "uncertainties": [], "known_gaps": [],
        "provenance": [], "last_updated": now, "readiness": "NOT_READY",
        "version": 1, "previous_version": None, "revision_history": [],
    }


def _load():
    return json.loads(OBJECTS_PATH.read_text(encoding="utf-8")) if OBJECTS_PATH.exists() else {}


def _save(data):
    OBJECTS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def upsert_intelligence_object(obj, trigger_evidence=None, changed_fields=None, change_reason=None,
                                impact_event=None):
    """The ONLY function permitted to write intelligence_objects.json. Preserves revision
    history -- never overwrites a prior version's record, only appends to revision_history."""
    objects = _load()
    existing = objects.get(obj["intelligence_id"])
    if existing:
        obj["version"] = existing["version"] + 1
        obj["previous_version"] = existing["version"]
        obj["revision_history"] = existing.get("revision_history", []) + [{
            "version": existing["version"], "snapshot_current_state": existing["current_state"],
            "updated_at": existing["last_updated"], "trigger_evidence": trigger_evidence,
            "changed_fields": changed_fields or [], "change_reason": change_reason,
            "impact_event": impact_event,
        }]
    obj["last_updated"] = datetime.now(timezone.utc).isoformat()
    objects[obj["intelligence_id"]] = obj
    _save(objects)
    return obj


def load_intelligence_objects():
    return _load()
