# PHASE M.5 — Change-layer source independence gate (Priority 1).
# run_pilot.py currently sets independent_source_count = len(supporting_event_ids), i.e. it
# treats every supporting EVENT as an independently-sourced unit. That is true of the EVENT
# merge layer's own dedup (event_matching already collapses duplicate articles into one Event),
# but it never checks whether two *different* Events behind the same Change candidate are
# themselves reports on the same underlying source (e.g. two Events, each merged from its own
# article set, that both ultimately trace back to one press release/outlet). No independence
# check exists anywhere in intel/change_layer/ today (this is the exact gap M.4 flagged).
#
# This module is the SAME KIND of adapter as intel/pattern_layer/source_independence_gate.py
# (itself adapting intel/operator_brain/source_independence.py) — it is the third instance of
# this pattern (pattern_layer, foresight_engine's historical/reality_source_independence, and
# now change_layer). It does NOT invent a new independence system: it reuses
# operator_brain.source_independence.assess_independence()'s union-find over the
# INDEPENDENT/LIKELY_INDEPENDENT/SHARED_ORIGIN/DERIVED_FROM_SAME_SOURCE/UNKNOWN vocabulary,
# collapsing SHARED_ORIGIN/DERIVED_FROM_SAME_SOURCE Events into one evidence family and never
# treating UNKNOWN as independent.
#
# ADDITIVE ONLY, same contract as the pattern-layer gate: this can only REDUCE the effective
# independent-evidence count behind a change candidate (by collapsing Events whose documents
# share an origin), never increase it, and it never lowers MIN_SUPPORTING_EVENTS or any other
# existing gate. The gate is applied to EVENTS (not Changes, unlike the pattern-layer gate,
# which groups Changes) because in change_layer the supporting units are Events, and each
# Event already carries related_document_ids directly (Master Chain: DOCUMENT -> EVENT ->
# CHANGE), so no separate change->event->document indirection is needed here.
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent


def _load_isolated(path, unique_name):
    key = f"_change_layer_isolated__{unique_name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_source_independence():
    """operator_brain/source_independence.py is self-contained (stdlib only: json, pathlib,
    urllib.parse), so it is safe to load in isolation without touching operator_brain's other
    modules or sys.path — same reasoning private_api/loader.py and pattern_layer's gate
    document for cross-package imports that would otherwise collide on module names."""
    return _load_isolated(INTEL_DIR / "operator_brain" / "source_independence.py",
                           "source_independence")


def _load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def load_documents():
    """Real-corpus loader: intel/documents.json, read-only. Handles both a document_id-keyed
    dict shape and a list-of-dicts shape (the repo's documents.json is currently dict-shaped)."""
    documents = _load_json(INTEL_DIR / "documents.json", {})
    if isinstance(documents, dict):
        return {k: v for k, v in documents.items() if isinstance(v, dict)}
    return {d["document_id"]: d for d in documents if isinstance(d, dict) and "document_id" in d}


def event_document_trail(event, documents_by_id):
    """One Event -> its real document trail entries, via related_document_ids/document_ids
    (never invents a document_id that isn't actually referenced on the Event)."""
    doc_ids = event.get("related_document_ids") or event.get("document_ids") or []
    trail = []
    for did in doc_ids:
        doc = documents_by_id.get(did)
        if doc is None:
            trail.append({"document_id": did, "found": False})
        else:
            trail.append({
                "document_id": did, "found": True,
                "canonical_url": doc.get("canonical_url"),
            })
    return trail


def independence_families(event_ids, events_by_id, documents_by_id, reports_on_pairs=None):
    """Groups the given event_ids into evidence families using
    operator_brain.source_independence.assess_independence()'s union-find (SHARED_ORIGIN /
    DERIVED_FROM_SAME_SOURCE only). Returns the full assess_independence() result dict, keyed
    by event_id instead of note_id/change_id (the function is generic over the id type)."""
    si = _load_source_independence()
    trails = [(eid, event_document_trail(events_by_id[eid], documents_by_id))
              for eid in event_ids]
    return si.assess_independence(trails, reports_on_pairs=reports_on_pairs)


def independent_evidence_count(event_ids, events_by_id, documents_by_id, reports_on_pairs=None):
    """The number of distinct evidence FAMILIES behind event_ids, after collapsing
    SHARED_ORIGIN/DERIVED_FROM_SAME_SOURCE events together. Always <= len(event_ids) (additive
    only — can only ever reduce the naive per-event count)."""
    if len(event_ids) <= 1:
        return len(event_ids)
    result = independence_families(event_ids, events_by_id, documents_by_id, reports_on_pairs)
    return result["evidence_family_count"]


def passes_independence_gate(event_ids, events_by_id, documents_by_id, min_independent,
                              reports_on_pairs=None):
    """True iff the candidate's supporting events still resolve to >= min_independent
    independent evidence families. This never replaces MIN_SUPPORTING_EVENTS (the caller still
    enforces that on the raw supporting_event_ids first) — it is checked IN ADDITION, using the
    same threshold value, so a candidate that only clears the raw event count because several
    of its events trace back to the same underlying document/source is correctly rejected
    rather than silently promoted."""
    return independent_evidence_count(event_ids, events_by_id, documents_by_id,
                                       reports_on_pairs) >= min_independent
