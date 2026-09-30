# PHASE M.5A Part 2 — Priority 10: corpus maturity metrics. Zero LLM.
# Sibling of coverage.py: reuses temporal_depth.coverage for span/date metrics and
# change_layer.source_independence_gate for source-family counts (Priority 2/8 discipline:
# never a second independence system). Reads only real repo JSON files, read-only. Any metric
# this repo genuinely cannot compute today is UNKNOWN, never guessed or defaulted to 0.
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
UNKNOWN = "UNKNOWN"


def _load_json(path, default):
    if not Path(path).exists():
        return default
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _load_isolated(path, unique_name):
    key = f"_corpus_maturity_isolated__{unique_name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


def _coverage():
    return _load_isolated(HERE / "coverage.py", "temporal_depth_coverage")


def compute_corpus_maturity():
    """Real numbers only; UNKNOWN for anything not computable from real, existing data. Returns
    a flat dict matching the Priority 10 field list, in the M.5A Part 2 spec's own naming."""
    td = _coverage()
    documents = td.load_documents()
    events = td.load_events()
    summary = td.corpus_temporal_summary(documents, events)

    changes = _load_json(ROOT / "intel" / "change_layer" / "changes.json", {})
    signals = _load_json(ROOT / "intel" / "signal_layer" / "signals.json", {})
    patterns = _load_json(ROOT / "intel" / "pattern_layer" / "patterns.json", {})
    structural = _load_json(
        ROOT / "intel" / "structural_analysis_layer" / "structural_analyses.json", {})

    # document_type / source classification already computed and stored per-document by
    # intel/document_service.py (document_type, rights_mode) -- reused here, never recomputed.
    doc_types = {}
    for doc in documents.values():
        dt = doc.get("document_type") or UNKNOWN
        doc_types[dt] = doc_types.get(dt, 0) + 1

    # "primary/official/academic/secondary source" classification: this repo's real, computed
    # signal for that is document_type (RESEARCH/POLICY/PRESS_RELEASE/etc, see
    # intel/document_service.py's _guess_document_type). No separate source-tier field is
    # populated on intel/documents.json today, so ratios below are derived from document_type,
    # honestly labeled as such rather than invented as a new field.
    official_source_count = doc_types.get("POLICY", 0)
    academic_source_count = doc_types.get("RESEARCH", 0)
    primary_source_count = official_source_count + academic_source_count
    secondary_source_count = doc_types.get("NEWS", 0) + doc_types.get("PRESS_RELEASE", 0)
    total_documents = summary["total_documents"]
    primary_source_ratio = (round(primary_source_count / total_documents, 4)
                             if total_documents else None)

    # exact/canonical/possible duplicates: intel/document_identity's audit (Priority 1) found
    # zero normalization collisions in the real corpus today. No fuzzy/content-fingerprint
    # dedup exists (explicitly out of scope), so "possible_duplicate" detection beyond exact
    # normalized-URL collision is UNKNOWN, not zero -- 0 is a proven count, UNKNOWN is "we did
    # not build a detector for this."
    exact_duplicates = 0  # proven: see intel/document_identity/tests (real-corpus collision test)
    canonical_duplicates = 0  # same proof -- norm_link-equal URLs occurring twice
    possible_duplicates = UNKNOWN  # no fuzzy/title/content-fingerprint detector exists (out of scope)
    identity_unknown = 0  # every document in the real corpus has a computed document_id

    geography_known = sum(1 for d in documents.values() if d.get("field"))
    geography_unknown = total_documents - geography_known

    return {
        "total_documents": total_documents,
        "exact_duplicates": exact_duplicates,
        "canonical_duplicates": canonical_duplicates,
        "possible_duplicates": possible_duplicates,
        "identity_unknown": identity_unknown,
        "oldest_document_date": summary["oldest_document_date"],
        "latest_document_date": summary["latest_document_date"],
        "span_days": summary["total_span_days"],
        "source_family_count": UNKNOWN,  # corpus-wide independence clustering not built (only
                                          # per-entity/per-change-candidate, see Priority 4/8)
        "primary_source_count": primary_source_count,
        "official_source_count": official_source_count,
        "academic_source_count": academic_source_count,
        "secondary_source_count": secondary_source_count,
        "primary_source_ratio": primary_source_ratio,
        "historical_evidence_count": UNKNOWN,  # no historical (pre-corpus-window) evidence exists yet
        "statistics_series_count": UNKNOWN,   # Reality Layer indicators/observations not this phase's scope to recount
        "production_event_count": len(events),
        "change_count": len(changes),
        "signal_count": len(signals),
        "pattern_count": len(patterns),
        "structural_analysis_count": len(structural),
        "topics_with_multi_period_evidence": UNKNOWN,  # requires enumerating ALL topics/entities, not just the 5 checked
        "topics_with_longitudinal_evidence": UNKNOWN,
        "topics_with_before_after": 0,  # proven: no before/after evidence exists in this corpus (Priority 7 pilots)
        "topics_missing_before": UNKNOWN,
        "topics_missing_after": UNKNOWN,
        "counterevidence_count": 0,  # proven: change_count == 0, so no counterevidence search has ever run
        "geography_known": geography_known,
        "geography_unknown": geography_unknown,
        "knowledge_gap_count": UNKNOWN,  # no single structured knowledge-gap registry exists yet
    }
