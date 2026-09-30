# PHASE M.1 — GAP B remediation. Pattern candidates (candidate_generation.py) currently
# count "independent Change" purely by change_id uniqueness (MIN_INDEPENDENT_CHANGES). That
# check never asks whether the documents *behind* those Changes are actually independent
# sources - several derivative/syndicated reports of one underlying source could in principle
# supply 2+ distinct change_ids that are not, in fact, 2 independent confirmations.
#
# This module does NOT build a new source-truth system. It adapts the existing
# intel/operator_brain/source_independence.py (INDEPENDENT/LIKELY_INDEPENDENT/SHARED_ORIGIN/
# DERIVED_FROM_SAME_SOURCE/UNKNOWN vocabulary, pairwise_status/assess_independence logic) via
# the same importlib isolation pattern intel/private_api/loader.py already uses for
# cross-package imports that would otherwise collide on module names like schema.py/memory.py.
#
# The gate is ADDITIVE ONLY: it can reduce the effective count of independent evidence behind
# a pattern candidate (by collapsing SHARED_ORIGIN/DERIVED_FROM_SAME_SOURCE changes into one
# family), never increase it, and never treats UNKNOWN provenance as INDEPENDENT (that is
# already how operator_brain/source_independence.assess_independence's family union works:
# it only unions on SHARED_ORIGIN/DERIVED_FROM_SAME_SOURCE, never on UNKNOWN or
# LIKELY_INDEPENDENT). It never lowers MIN_INDEPENDENT_CHANGES or any other existing gate.
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
OPERATOR_BRAIN_DIR = INTEL_DIR / "operator_brain"


def _load_isolated(path, unique_name):
    key = f"_pattern_layer_isolated__{unique_name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_source_independence():
    """operator_brain/source_independence.py is self-contained (stdlib only: json, pathlib,
    urllib.parse) so it is safe to load in isolation without touching operator_brain's other
    modules or sys.path - same reasoning private_api/loader.py documents for knowledge_memory
    modules."""
    return _load_isolated(OPERATOR_BRAIN_DIR / "source_independence.py", "source_independence")


def _load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def load_real_corpus_trail_inputs():
    """Real-corpus loader for production use: documents.json + event_production/
    production_events.json, both read-only. Returns (documents_by_id, events_by_id)."""
    documents = _load_json(INTEL_DIR / "documents.json", [])
    if isinstance(documents, dict):
        documents_by_id = {k: v for k, v in documents.items() if isinstance(v, dict)}
        # some documents.json shapes are document_id-keyed already; also handle a values-list
        if documents_by_id and "document_id" not in next(iter(documents_by_id.values()), {}):
            pass
    else:
        documents_by_id = {d["document_id"]: d for d in documents if isinstance(d, dict) and "document_id" in d}
    events = _load_json(INTEL_DIR / "event_production" / "production_events.json", {})
    events_by_id = events if isinstance(events, dict) else {e["event_id"]: e for e in events if "event_id" in e}
    return documents_by_id, events_by_id


def change_document_ids(change, events_by_id):
    """Change -> the real document_ids behind it, via its supporting_event_ids (Master Chain:
    DOCUMENT -> EVENT -> CHANGE). Never invents a document_id that isn't actually referenced."""
    doc_ids = []
    for eid in change.get("supporting_event_ids", []) or []:
        ev = events_by_id.get(eid)
        if not ev:
            continue
        for did in ev.get("related_document_ids") or ev.get("document_ids") or []:
            if did not in doc_ids:
                doc_ids.append(did)
    return doc_ids


def _trail_for_change(change_id, change, documents_by_id, events_by_id):
    doc_ids = change_document_ids(change, events_by_id)
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


def independence_families(change_ids, changes, documents_by_id, events_by_id, reports_on_pairs=None):
    """Groups the given change_ids into evidence families using the existing
    source_independence.assess_independence() union-find (SHARED_ORIGIN /
    DERIVED_FROM_SAME_SOURCE only). Returns the full assess_independence() result dict, keyed
    by change_id instead of note_id (the function is generic over the id type)."""
    si = _load_source_independence()
    trails = [(cid, _trail_for_change(cid, changes[cid], documents_by_id, events_by_id))
              for cid in change_ids]
    return si.assess_independence(trails, reports_on_pairs=reports_on_pairs)


def independent_evidence_count(change_ids, changes, documents_by_id, events_by_id, reports_on_pairs=None):
    """The number of distinct evidence FAMILIES behind change_ids, after collapsing
    SHARED_ORIGIN/DERIVED_FROM_SAME_SOURCE changes together. This is <= len(change_ids) always
    (it can only ever reduce the naive count, per the additive-only contract above)."""
    if len(change_ids) <= 1:
        return len(change_ids)
    result = independence_families(change_ids, changes, documents_by_id, events_by_id, reports_on_pairs)
    return result["evidence_family_count"]


def passes_independence_gate(change_ids, changes, documents_by_id, events_by_id,
                              min_independent, reports_on_pairs=None):
    """True iff the candidate still has >= min_independent independent evidence families.
    This NEVER replaces MIN_INDEPENDENT_CHANGES (the caller still enforces that on raw
    change_ids first) - it is checked in addition, using the same threshold value, so a
    candidate that only clears the raw count because several of its changes share an
    underlying source is correctly rejected instead of silently promoted."""
    return independent_evidence_count(change_ids, changes, documents_by_id, events_by_id,
                                       reports_on_pairs) >= min_independent
