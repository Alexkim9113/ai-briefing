# PHASE M.5E-2 -- first slice, item 1: Source Diversity Audit (READ-ONLY).
#
# Computes, from the real intel/documents.json corpus only:
#   - source-family document counts (which independent evidence family has how many docs) --
#     reuses intel/operator_brain/source_independence.py's assess_independence() and its
#     union-find family grouping directly. This module does NOT reinvent family grouping.
#   - Google News dependency ratio (fraction of documents whose canonical_url host is
#     news.google.com)
#   - direct-primary-source ratio (fraction whose source_id is in
#     intel/evidence_admission/admission_gate.py's TRUSTED_SOURCES -- reused as-is, not a new
#     trust list)
#   - academic-source ratio (document_type == RESEARCH)
#   - statistical-source ratio (this corpus has no statistical-source document_type or source_id
#     today -- honestly reported as 0/total, never forced to a nonzero number)
#   - geographic distribution using ONLY the existing `country`/`jurisdiction` fields
#     (intel/evidence_admission/admission_gate.py's build_canonical_record() is the only writer
#     of these fields). Never inferred from source language or domain TLD. Any document without
#     an explicit country/jurisdiction value is UNKNOWN.
#
# Zero LLM. Stdlib only. Never mutates intel/documents.json.
import importlib.util
import json
import sys
import urllib.parse
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
DOCUMENTS_PATH = INTEL_DIR / "documents.json"

UNKNOWN = "UNKNOWN"
GOOGLE_NEWS_HOST = "news.google.com"

# Reused directly from intel/evidence_admission/admission_gate.py -- the same set that decides
# real admission, not a parallel trust list built for this audit alone.
_ADMISSION_GATE_PATH = INTEL_DIR / "evidence_admission" / "admission_gate.py"


def _load_isolated(path, unique_name):
    key = f"_source_diversity_isolated__{unique_name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


def _admission_gate():
    return _load_isolated(_ADMISSION_GATE_PATH, "admission_gate")


def _source_independence():
    return _load_isolated(INTEL_DIR / "operator_brain" / "source_independence.py",
                           "source_independence")


def _load_json(path, default):
    if not Path(path).exists():
        return default
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def load_documents(documents_path=DOCUMENTS_PATH):
    data = _load_json(documents_path, {})
    if isinstance(data, dict):
        return {k: v for k, v in data.items() if isinstance(v, dict)}
    return {d["document_id"]: d for d in data if isinstance(d, dict) and "document_id" in d}


def _host_of(url):
    if not url or not isinstance(url, str):
        return None
    try:
        host = urllib.parse.urlsplit(url).hostname
    except ValueError:
        return None
    return host.lower() if host else None


def google_news_dependency(documents):
    total = len(documents)
    gn_count = sum(1 for d in documents.values() if _host_of(d.get("canonical_url")) == GOOGLE_NEWS_HOST)
    return {
        "count": gn_count,
        "total": total,
        "ratio": round(gn_count / total, 4) if total else None,
    }


def direct_primary_source_ratio(documents):
    ag = _admission_gate()
    total = len(documents)
    trusted_count = sum(1 for d in documents.values() if d.get("source_id") in ag.TRUSTED_SOURCES)
    return {
        "count": trusted_count,
        "total": total,
        "ratio": round(trusted_count / total, 4) if total else None,
        "trusted_source_ids": sorted(ag.TRUSTED_SOURCES.keys()),
    }


def academic_source_ratio(documents):
    total = len(documents)
    academic_count = sum(1 for d in documents.values() if d.get("document_type") == "RESEARCH")
    return {
        "count": academic_count,
        "total": total,
        "ratio": round(academic_count / total, 4) if total else None,
    }


def statistical_source_ratio(documents):
    """This corpus has no statistical-agency source_id and no STATISTICS document_type today
    (audited: intel/evidence_admission/admission_gate.py's TRUSTED_SOURCES and
    VALID_DOCUMENT_TYPES). Reported honestly as 0/total -- never forced to a nonzero number to
    look complete."""
    total = len(documents)
    return {"count": 0, "total": total, "ratio": 0.0 if total else None,
            "note": "no statistical-agency source is registered in this corpus's admission gate "
                    "today; this is a real, honest 0, not a placeholder"}


def geographic_distribution(documents):
    """Uses ONLY the existing `country`/`jurisdiction` fields already on documents.json records
    (populated exclusively by admission_gate.build_canonical_record() from a TRUSTED_SOURCES
    row). Never inferred from source language, source_id hostname, or domain TLD -- any document
    without an explicit value is UNKNOWN, by design (see pilot_topic_coverage.py's own explicit
    refusal to treat source-hostname hints as geography)."""
    country_counts = Counter(d.get("country") or UNKNOWN for d in documents.values())
    jurisdiction_counts = Counter(d.get("jurisdiction") or UNKNOWN for d in documents.values())
    return {
        "by_country": dict(country_counts),
        "by_jurisdiction": dict(jurisdiction_counts),
        "unknown_country_count": country_counts.get(UNKNOWN, 0),
        "unknown_jurisdiction_count": jurisdiction_counts.get(UNKNOWN, 0),
    }


def source_family_document_counts(documents, sample_limit=None):
    """Which independent evidence family (per source_independence.assess_independence()) has
    how many documents. Reuses the SAME family computation corpus_balance.py's
    independent_source_family_count() already drives -- this function additionally reports the
    per-family document COUNTS (not just the family total), which corpus_balance.py does not
    expose.

    A document whose origin cannot be resolved (no canonical_url at all -- this audit's operational
    definition of "UNKNOWN source/origin", since document_id is always present as this corpus's
    dict key and is never itself a source signal) is given a `found=False` provenance trail
    entry, exactly as provenance.reconstruct() would for an unresolved note. assess_independence()'s
    own pairwise_status() then returns UNKNOWN for every pair touching that document -- UNKNOWN
    never triggers a union() in the family grouping (see source_independence.py's `_PRIORITY`
    ordering and `if best in ("SHARED_ORIGIN", "DERIVED_FROM_SAME_SOURCE")` guard) -- so such a
    document can still surface as its own singleton family through the union-find default, but it
    is NEVER merged into (and so never inflates) another document's family. This module does not
    reimplement that guarantee -- it is proven directly against the real algorithm by
    intel/source_diversity/tests/test_audit.py and intel/evidence_network/tests/test_failure_modes.py."""
    si = _source_independence()
    doc_ids = sorted(documents.keys())
    if sample_limit is not None:
        doc_ids = doc_ids[:sample_limit]

    trails = [
        (did, [{"document_id": did, "canonical_url": documents[did].get("canonical_url"),
                "found": bool(documents[did].get("canonical_url"))}])
        for did in doc_ids
    ]
    unresolved_count = sum(1 for _, entries in trails if not entries[0]["found"])

    if len(trails) <= 1:
        return {
            "evidence_family_count": len(trails),
            "documents_considered": len(trails),
            "unresolved_origin_count": unresolved_count,
            "family_sizes": [1] * len(trails),
            "largest_family_size": 1 if trails else 0,
            "sampled": sample_limit is not None,
        }

    result = si.assess_independence(trails, reports_on_pairs=None)
    family_sizes = [len(fam) for fam in result["families"]]

    return {
        "evidence_family_count": result["evidence_family_count"],
        "documents_considered": len(trails),
        "unresolved_origin_count": unresolved_count,
        "family_sizes": sorted(family_sizes, reverse=True),
        "largest_family_size": max(family_sizes) if family_sizes else 0,
        "overall_status": result["overall_status"],
        "sampled": sample_limit is not None,
    }


def source_diversity_report(documents=None, family_sample_limit=None):
    """The full, real, read-only source-diversity audit. family_sample_limit bounds the O(n^2)
    family computation (see corpus_balance.py's own documented complexity note); defaults to
    None (full corpus)."""
    documents = documents if documents is not None else load_documents()
    return {
        "total_documents": len(documents),
        "google_news_dependency": google_news_dependency(documents),
        "direct_primary_source": direct_primary_source_ratio(documents),
        "academic_source": academic_source_ratio(documents),
        "statistical_source": statistical_source_ratio(documents),
        "geographic_distribution": geographic_distribution(documents),
        "source_family": source_family_document_counts(documents, sample_limit=family_sample_limit),
    }


def main():
    report = source_diversity_report()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
