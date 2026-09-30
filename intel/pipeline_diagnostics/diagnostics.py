# PHASE M.1 — INTELLIGENCE INPUT INTEGRITY REMEDIATION, Step 3. Read-only, deterministic
# diagnostic/traceability layer over the REAL pipeline's own output files. This module NEVER
# writes to any Stage 1-6+ file, never recomputes classification/evidence/notes/changes/
# signals/patterns, and never invents a reason when the real data does not support one -
# UNKNOWN_REASON is an honest, expected answer, not a bug.
#
# It answers exactly the questions Phase M found unanswerable:
#   - why did document X not produce a knowledge_memory note?
#   - why did note/event Y not produce a change_layer change?
#   - what does the whole pipeline actually contain right now, end to end?
#   - what KIND of knowledge gap is this (CORPUS_GAP vs SEARCH_GAP vs PIPELINE_GAP etc.)?
#
# Modeled directly on intel/foresight_engine/intelligence_package.py's approach: plain
# json.load over each layer's own JSON file, no schema.py import (these packages' schema.py
# modules collide by name), read-only, honest 0/UNKNOWN is a valid final answer.
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
INTEL = ROOT / "intel"

DOCUMENTS_PATH = INTEL / "documents.json"
CLAIMS_PATH = INTEL / "evidence_pipeline" / "claims.json"
FACTS_VERIFIED_PATH = INTEL / "evidence_pipeline" / "facts_verified.json"
PRODUCTION_EVENTS_PATH = INTEL / "event_production" / "production_events.json"
CHANGES_PATH = INTEL / "change_layer" / "changes.json"
SIGNALS_PATH = INTEL / "signal_layer" / "signals.json"
PATTERNS_PATH = INTEL / "pattern_layer" / "patterns.json"
NOTES_PATH = INTEL / "knowledge_memory" / "notes.json"

# Reused/adjacent vocabulary (per-document / per-note "why not" reason codes). Kept small and
# deliberately overlapping with existing status vocabulary already in use elsewhere in the
# repo (claim_status values like INSUFFICIENT_SOURCE/SECONDARY_ONLY) rather than inventing a
# fully parallel enum.
DOCUMENT_REASON_CODES = (
    "HAS_NOTE",                 # not a "reason it failed" - it produced at least one note
    "NOT_ELIGIBLE",             # document exists but produced zero claims of any kind
    "INSUFFICIENT_EVIDENCE",    # every claim for this document is INSUFFICIENT_SOURCE/SECONDARY_ONLY
    "CLASSIFICATION_NOT_TRIGGERED",  # claims/events exist but never reached facts_verified/production_events
    "PIPELINE_NOT_EXECUTED",    # document not found in documents.json at all (can't have run)
    "UNKNOWN_REASON",           # real data does not let us determine which of the above applies
)

NOTE_REASON_CODES = (
    "HAS_CHANGE",
    "NO_TEMPORAL_CHANGE",       # event exists, is not part of any change_layer change
    "SCHEMA_REJECTED",          # event's change was HUMAN_REJECTED / override_status rejected
    "NOT_AN_EVENT_NOTE",        # note is FACT-type; change_layer only ever consumes EVENT-derived candidates
    "UNKNOWN_REASON",
)

GAP_CLASSES = (
    "CORPUS_GAP", "SEARCH_GAP", "CLASSIFICATION_GAP", "PIPELINE_GAP",
    "KNOWLEDGE_MEMORY_GAP", "CHANGE_LAYER_GAP", "DOMAIN_COVERAGE_GAP",
    "TEMPORAL_COVERAGE_GAP", "GEOGRAPHIC_METADATA_GAP", "INSUFFICIENT_EVIDENCE",
    "UNKNOWN_GAP",
)

_INSUFFICIENT_CLAIM_STATUSES = {"INSUFFICIENT_SOURCE", "SECONDARY_ONLY"}


def _load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _as_dict_by_id(data, id_field):
    if isinstance(data, dict):
        return data
    return {item[id_field]: item for item in data if isinstance(item, dict) and id_field in item}


def load_documents():
    return _as_dict_by_id(_load_json(DOCUMENTS_PATH, []), "document_id")


def load_claims():
    data = _load_json(CLAIMS_PATH, [])
    return data if isinstance(data, list) else list(data.values())


def load_facts_verified():
    data = _load_json(FACTS_VERIFIED_PATH, [])
    return data if isinstance(data, list) else list(data.values())


def load_production_events():
    return _as_dict_by_id(_load_json(PRODUCTION_EVENTS_PATH, {}), "event_id")


def load_changes():
    return _load_json(CHANGES_PATH, {})


def load_signals():
    return _load_json(SIGNALS_PATH, {})


def load_patterns():
    return _load_json(PATTERNS_PATH, {})


def load_notes():
    return _load_json(NOTES_PATH, {})


def _claims_for_document(document_id, claims=None):
    claims = load_claims() if claims is None else claims
    return [c for c in claims if c.get("document_id") == document_id]


def _events_for_document(document_id, events_by_id=None):
    events_by_id = load_production_events() if events_by_id is None else events_by_id
    out = []
    for eid, ev in events_by_id.items():
        doc_ids = ev.get("related_document_ids") or ev.get("document_ids") or []
        if document_id in doc_ids:
            out.append((eid, ev))
    return out


def _notes_for_document(document_id, notes=None):
    notes = load_notes() if notes is None else notes
    return [(nid, n) for nid, n in notes.items() if document_id in (n.get("document_ids") or [])]


def document_note_status(document_id):
    """For one document_id: did it produce at least one knowledge_memory note, and if not,
    the most specific reason code the real data (documents.json / claims.json /
    facts_verified.json / production_events.json / notes.json) actually supports."""
    documents = load_documents()
    if document_id not in documents:
        return {"document_id": document_id, "has_note": False,
                "reason_code": "PIPELINE_NOT_EXECUTED",
                "detail": "document_id not found in intel/documents.json"}

    notes = _notes_for_document(document_id)
    if notes:
        return {"document_id": document_id, "has_note": True, "reason_code": "HAS_NOTE",
                "note_ids": [nid for nid, _ in notes]}

    claims = _claims_for_document(document_id)
    events = _events_for_document(document_id)
    facts = [f for f in load_facts_verified() if f.get("document_id") == document_id]

    if not claims and not events:
        return {"document_id": document_id, "has_note": False, "reason_code": "NOT_ELIGIBLE",
                "detail": "no claim and no production event ever referenced this document_id"}

    if claims:
        statuses = {c.get("claim_status") for c in claims}
        if statuses and statuses <= _INSUFFICIENT_CLAIM_STATUSES:
            return {"document_id": document_id, "has_note": False,
                    "reason_code": "INSUFFICIENT_EVIDENCE",
                    "detail": f"all {len(claims)} claim(s) for this document are "
                              f"{sorted(statuses)} (single-source / not independently "
                              f"corroborated) - correctly excluded from facts_verified.json",
                    "claim_statuses": sorted(statuses)}

    if (claims or events) and not facts and not notes:
        return {"document_id": document_id, "has_note": False,
                "reason_code": "CLASSIFICATION_NOT_TRIGGERED",
                "detail": "claims and/or events exist referencing this document, but none "
                          "reached facts_verified.json/notes.json"}

    return {"document_id": document_id, "has_note": False, "reason_code": "UNKNOWN_REASON",
            "detail": "existing data does not clearly indicate why no note exists"}


def note_change_status(note_id):
    """For one knowledge_memory note_id: did the EVENT it wraps ever become part of a
    change_layer change, and if not, why (as far as the real data lets us tell)."""
    notes = load_notes()
    note = notes.get(note_id)
    if note is None:
        return {"note_id": note_id, "has_change": False, "reason_code": "UNKNOWN_REASON",
                "detail": "note_id not found in knowledge_memory/notes.json"}

    if note.get("source_object_type") != "EVENT":
        return {"note_id": note_id, "has_change": False, "reason_code": "NOT_AN_EVENT_NOTE",
                "detail": f"note source_object_type={note.get('source_object_type')!r}; "
                          "change_layer only ever groups EVENT-derived candidates"}

    event_ids = set(note.get("event_ids") or note.get("source_object_ids") or [])
    changes = load_changes()
    for cid, ch in changes.items():
        supporting = set(ch.get("supporting_event_ids") or [])
        if event_ids & supporting:
            if ch.get("status") == "REJECTED" or ch.get("override_status") == "HUMAN_REJECTED":
                return {"note_id": note_id, "has_change": False, "reason_code": "SCHEMA_REJECTED",
                        "detail": f"event is part of change {cid} but that change was rejected",
                        "change_id": cid}
            return {"note_id": note_id, "has_change": True, "reason_code": "HAS_CHANGE",
                     "change_id": cid}

    return {"note_id": note_id, "has_change": False, "reason_code": "NO_TEMPORAL_CHANGE",
            "detail": "event is not referenced by any change_layer change (accepted or "
                      "rejected) - either it never clustered with >=1 other event under a "
                      "shared mechanism fingerprint, or clustering was never attempted for it"}


def pipeline_audit_summary():
    """Honest, whole-pipeline counts computed only from what the real files actually contain.
    Every field here is a real count, not an estimate; UNKNOWN_REASON counts are also real
    (the number of documents for which document_note_status() could not resolve a specific
    reason)."""
    documents = load_documents()
    claims = load_claims()
    facts = load_facts_verified()
    events = load_production_events()
    changes = load_changes()
    signals = load_signals()
    patterns = load_patterns()
    notes = load_notes()

    documents_with_notes = set()
    for n in notes.values():
        documents_with_notes.update(n.get("document_ids") or [])
    documents_with_notes &= set(documents.keys())

    documents_with_claims = {c.get("document_id") for c in claims if c.get("document_id")}
    documents_with_claims &= set(documents.keys())

    notes_by_type = {}
    for n in notes.values():
        t = n.get("note_type") or n.get("source_object_type") or "UNKNOWN"
        notes_by_type[t] = notes_by_type.get(t, 0) + 1

    changes_by_status = {}
    for c in changes.values():
        s = c.get("status") or "UNKNOWN"
        changes_by_status[s] = changes_by_status.get(s, 0) + 1

    active_changes = [c for c in changes.values()
                      if c.get("status") != "REJECTED" and c.get("override_status") != "HUMAN_REJECTED"]

    return {
        "documents_total": len(documents),
        "documents_with_claims": len(documents_with_claims),
        "documents_without_claims": len(documents) - len(documents_with_claims),
        "documents_with_notes": len(documents_with_notes),
        "documents_without_notes": len(documents) - len(documents_with_notes),
        "documents_eligible_note": "UNKNOWN - not computable without re-running claim "
                                    "extraction on every document; documents_with_claims is "
                                    "the closest honest lower-bound proxy",
        "claims_total": len(claims),
        "facts_verified_total": len(facts),
        "production_events_total": len(events),
        "notes_total": len(notes),
        "notes_by_type": notes_by_type,
        "change_candidates_active": len(active_changes),
        "changes_total": len(changes),
        "changes_by_status": changes_by_status,
        "signals_total": len(signals),
        "patterns_total": len(patterns),
    }


def classify_gap(document_ids):
    """Best-effort knowledge-gap classification for a set of document_ids that make up "a
    topic" (the caller decides what counts as the topic - this function makes no search
    decisions of its own). Only assigns a class the data actually supports; falls back to
    UNKNOWN_GAP rather than guessing."""
    document_ids = list(document_ids)
    if not document_ids:
        return {"gap_class": "SEARCH_GAP",
                "detail": "no documents were supplied for this topic at all - "
                          "this function cannot tell whether that is because none exist or "
                          "because none were found; caller-side search coverage, not corpus "
                          "content, is the first thing to check"}

    documents = load_documents()
    found = [d for d in document_ids if d in documents]
    if not found:
        return {"gap_class": "SEARCH_GAP",
                "detail": "none of the given document_ids exist in documents.json"}

    statuses = [document_note_status(d) for d in found]
    reason_codes = {s["reason_code"] for s in statuses}

    if reason_codes == {"HAS_NOTE"}:
        # notes exist; whether they became changes is a separate CHANGE_LAYER_GAP question,
        # not this function's job to also answer without being asked.
        return {"gap_class": "UNKNOWN_GAP",
                "detail": "documents have notes; not a knowledge-acquisition gap - if the "
                          "question is about missing CHANGE/pattern, check note_change_status() "
                          "and pattern_layer instead",
                "per_document": statuses}

    if reason_codes <= {"INSUFFICIENT_EVIDENCE", "HAS_NOTE"}:
        return {"gap_class": "CORPUS_GAP",
                "detail": f"{len(found)} document(s) found, but evidence is single-source / "
                          "not independently corroborated (INSUFFICIENT_EVIDENCE) for at "
                          "least one - the corpus genuinely lacks a second independent "
                          "confirming source for this topic, not a code defect",
                "per_document": statuses}

    if "CLASSIFICATION_NOT_TRIGGERED" in reason_codes:
        return {"gap_class": "CLASSIFICATION_GAP",
                "detail": "claims/events exist for at least one document but never reached "
                          "facts_verified.json/notes.json",
                "per_document": statuses}

    if "NOT_ELIGIBLE" in reason_codes:
        return {"gap_class": "CORPUS_GAP",
                "detail": "at least one document produced zero claims - nothing in the "
                          "document content the extraction stage could act on",
                "per_document": statuses}

    return {"gap_class": "UNKNOWN_GAP",
            "detail": "reason codes present do not map cleanly to one gap class",
            "per_document": statuses}
