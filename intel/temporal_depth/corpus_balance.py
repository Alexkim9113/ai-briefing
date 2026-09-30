# PHASE M.5E -- first slice, item 4: corpus balance metrics (READ-ONLY).
#
# Computes, from the real intel/documents.json corpus only: source-type distribution,
# source-tier distribution, a best-effort domain/topic distribution (from the existing
# `category`/`field` fields -- no new taxonomy invented), the M.5E temporal-bucket
# distribution (CURRENT/SHORT_TERM/MEDIUM_TERM/LONG_TERM/HISTORICAL, defined below from the
# document's own `published` date relative to "now"), and the corpus-wide independent
# source-family count, reusing intel/operator_brain/source_independence.py's own
# assess_independence() (the SAME independence algorithm intel/change_layer/
# source_independence_gate.py already adapts elsewhere) -- this module does not invent a
# second independence system.
#
# Read-only: never writes intel/documents.json. Writes only this module's own behavior (no
# sidecar file by default -- callers/tests read the returned dict directly, matching
# coverage.py's and pilot_topic_coverage.py's own pattern of pure functions over documents.json).
import importlib.util
import json
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
DOCUMENTS_PATH = INTEL_DIR / "documents.json"

UNKNOWN = "UNKNOWN"

# M.5E temporal buckets, defined relative to "now" (not to the corpus's own min/max date, so
# the buckets mean the same thing on every run). Boundaries are inclusive of the lower day
# count and named to match the M.5E spec vocabulary exactly.
TEMPORAL_BUCKETS = ("CURRENT", "SHORT_TERM", "MEDIUM_TERM", "LONG_TERM", "HISTORICAL", UNKNOWN)

_BUCKET_BOUNDARIES_DAYS = (
    ("CURRENT", 7),        # published within the last 7 days
    ("SHORT_TERM", 90),    # within the last 90 days
    ("MEDIUM_TERM", 365),  # within the last year
    ("LONG_TERM", 1825),   # within the last 5 years
    # anything older -> HISTORICAL
)

# Reused directly from admission_gate.py's TRUSTED_SOURCES tiering + the existing
# document_type->tier proxy pilot_topic_coverage.py already uses (not a new tier system).
_DOCTYPE_TO_SOURCE_TIER = {
    "POLICY": "TIER_1_OFFICIAL",
    "RESEARCH": "TIER_1_ACADEMIC",
    "PRESS_RELEASE": "TIER_2_SECONDARY",
    "NEWS": "TIER_2_SECONDARY",
    "OTHER": "TIER_UNKNOWN",
}


def _load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _load_isolated(path, unique_name):
    key = f"_corpus_balance_isolated__{unique_name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


def _source_independence():
    return _load_isolated(INTEL_DIR / "operator_brain" / "source_independence.py",
                           "source_independence")


def load_documents():
    documents = _load_json(DOCUMENTS_PATH, {})
    if isinstance(documents, dict):
        return {k: v for k, v in documents.items() if isinstance(v, dict)}
    return {d["document_id"]: d for d in documents if isinstance(d, dict) and "document_id" in d}


def _parse_date(value):
    if not value or not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def temporal_bucket(published_value, as_of=None):
    """One document's real published date -> a M.5E temporal bucket, relative to as_of
    (defaults to real UTC 'now'). UNKNOWN when published is missing/unparseable or in the
    future relative to as_of (never guessed into a bucket)."""
    as_of = as_of or datetime.now(timezone.utc).date()
    d = _parse_date(published_value)
    if d is None or d > as_of:
        return UNKNOWN
    age_days = (as_of - d).days
    for name, max_days in _BUCKET_BOUNDARIES_DAYS:
        if age_days <= max_days:
            return name
    return "HISTORICAL"


def source_type_distribution(documents):
    """document_type IS this corpus's real source/content-type field (documents.json has no
    separate 'source_type' key -- see document_service.py's schema); reused as-is, never
    invented."""
    counts = Counter(d.get("document_type") or UNKNOWN for d in documents.values())
    return dict(counts)


def source_tier_distribution(documents):
    counts = Counter(_DOCTYPE_TO_SOURCE_TIER.get(d.get("document_type"), "TIER_UNKNOWN")
                      for d in documents.values())
    return dict(counts)


def domain_distribution(documents, top_n=15):
    """Best-effort topic/domain distribution from the existing `category`/`field` fields.
    `field` is the more specific, human-curated Korean topic label (e.g. 에이전트, 사회·노동);
    `category` is the coarser existing bucket (news_ko/news_global/policy/papers). Both are
    reported -- neither replaces the other, and neither is a new taxonomy."""
    category_counts = Counter(d.get("category") or UNKNOWN for d in documents.values())
    field_counts = Counter(d.get("field") or UNKNOWN for d in documents.values())
    return {
        "by_category": dict(category_counts),
        "by_field_top": dict(field_counts.most_common(top_n)),
        "field_unknown_count": field_counts.get(UNKNOWN, 0),
    }


def temporal_bucket_distribution(documents, as_of=None):
    counts = Counter(temporal_bucket(d.get("published"), as_of) for d in documents.values())
    return {b: counts.get(b, 0) for b in TEMPORAL_BUCKETS}


def independent_source_family_count(documents, sample_limit=None):
    """Corpus-wide independent-evidence-family count, reusing
    operator_brain.source_independence.assess_independence() directly (same algorithm
    intel/change_layer/source_independence_gate.py already adapts for the change layer) --
    treats each document as its own evidence unit with a one-entry provenance trail
    (document_id/canonical_url/found=True), since documents.json has no separate event layer
    indirection needed here (unlike the change-layer gate, which groups Events).

    This is O(n^2) pairwise comparison (matches assess_independence()'s own documented
    complexity) -- fine for a periodic corpus-wide audit, not for a hot path. sample_limit
    caps it for callers/tests that want a bounded-time run over a deterministic subset (the
    first sample_limit documents by sorted document_id, never a random sample)."""
    si = _source_independence()
    doc_ids = sorted(documents.keys())
    if sample_limit is not None:
        doc_ids = doc_ids[:sample_limit]
    trails = [
        (did, [{"document_id": did, "canonical_url": documents[did].get("canonical_url"),
                "found": True}])
        for did in doc_ids
    ]
    if len(trails) <= 1:
        return {"evidence_family_count": len(trails), "documents_considered": len(trails),
                "sampled": sample_limit is not None}
    result = si.assess_independence(trails, reports_on_pairs=set())
    return {
        "evidence_family_count": result["evidence_family_count"],
        "documents_considered": len(trails),
        "sampled": sample_limit is not None,
        "overall_status": result["overall_status"],
    }


def corpus_balance_report(documents=None, as_of=None, independence_sample_limit=None):
    """The full, real, read-only balance report. independence_sample_limit defaults to None
    (full corpus) for callers that can afford O(n^2); pass a smaller value (e.g. 100) for a
    fast, bounded-time check (used by this module's own tests)."""
    documents = documents if documents is not None else load_documents()
    return {
        "total_documents": len(documents),
        "source_type_distribution": source_type_distribution(documents),
        "source_tier_distribution": source_tier_distribution(documents),
        "domain_distribution": domain_distribution(documents),
        "temporal_bucket_distribution": temporal_bucket_distribution(documents, as_of),
        "independent_source_family": independent_source_family_count(
            documents, sample_limit=independence_sample_limit),
    }


def main():
    report = corpus_balance_report()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
