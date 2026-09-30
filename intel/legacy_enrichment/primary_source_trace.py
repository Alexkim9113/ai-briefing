# PHASE M.5E -- first slice, item 2: primary-source trace for a handful of high-priority NEWS
# candidates (READ-ONLY, sidecar output only).
#
# For up to 5 of the highest-priority NEWS documents from priority_candidates.py's audit, this
# module determines -- from the document's OWN existing title/metadata and the REAL corpus it
# already sits in, never by fetching a new URL or fabricating one -- whether a primary source
# (government notice, court filing, official statistics, company filing) is plausibly
# identifiable via a domain a real connector in this repo already trusts
# (intel/evidence_admission/admission_gate.py's TRUSTED_SOURCES: federalregister.gov, doi.org)
# or via another real corpus document that shares the same underlying event and already sits on
# such a domain. Nothing here invents a URL, a source, or a connection between documents.
#
# Status vocabulary (exact, per M.5E spec -- never a value outside this set):
#   NEWS_ONLY, PRIMARY_SOURCE_FOUND, PRIMARY_SOURCE_NOT_FOUND, OFFICIAL_CORROBORATED,
#   INDEPENDENTLY_CORROBORATED, INSUFFICIENT_EVIDENCE
#
# This sandbox has no live outbound network (see session constraints), so this module can only
# reason from data already present in documents.json -- it does NOT resolve Google News'
# opaque redirect URLs (news.google.com/rss/articles/...) to their real destination, since doing
# so requires a live fetch. Any document behind such a redirect is honestly INSUFFICIENT_EVIDENCE,
# never guessed at.
import importlib.util
import json
import re
import sys
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
DOCUMENTS_PATH = INTEL_DIR / "documents.json"
CANDIDATES_PATH = HERE / "priority_candidates.json"
OUT_PATH = HERE / "primary_source_trace.json"

MAX_CANDIDATES = 5

STATUS_VALUES = (
    "NEWS_ONLY", "PRIMARY_SOURCE_FOUND", "PRIMARY_SOURCE_NOT_FOUND",
    "OFFICIAL_CORROBORATED", "INDEPENDENTLY_CORROBORATED", "INSUFFICIENT_EVIDENCE",
)

# Domains this repo's own connectors already treat as primary/official sources (reused from
# admission_gate.TRUSTED_SOURCES -- not a new, separate trust list).
TRUSTED_PRIMARY_DOMAINS = ("federalregister.gov", "doi.org")

# Opaque redirect hosts whose true destination cannot be determined from metadata alone.
OPAQUE_REDIRECT_HOSTS = ("news.google.com",)

# Regulator/agency name hints that make "a primary source plausibly exists somewhere" a
# reasonable inference, even when this corpus doesn't contain it -- used only to distinguish
# PRIMARY_SOURCE_NOT_FOUND (a primary source plausibly exists, but isn't in this corpus/these
# connectors) from plain NEWS_ONLY (no such hint at all). This is a plausibility flag, not a
# claim that the primary source was found.
_REGULATOR_HINTS = (
    "ftc", "sec ", "fda", "doj", "eu commission", "european commission", "court", "ruling",
    "lawsuit", "규제", "공정위", "법원",
)


def _load_documents():
    data = json.loads(DOCUMENTS_PATH.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return {k: v for k, v in data.items() if isinstance(v, dict)}
    return {d["document_id"]: d for d in data if isinstance(d, dict) and "document_id" in d}


def _load_isolated(path, unique_name):
    key = f"_legacy_enrichment_isolated__{unique_name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


def _priority_candidates():
    return _load_isolated(INTEL_DIR / "legacy_enrichment" / "priority_candidates.py",
                           "priority_candidates")


def _host_of(url):
    if not url:
        return None
    return (urllib.parse.urlsplit(url).hostname or "").lower()


def top_news_candidates(report=None, limit=MAX_CANDIDATES):
    """The highest-priority NEWS-type documents from the real audit report (not re-sorting by
    a different metric -- same score/order the audit already produced)."""
    report = report if report is not None else json.loads(CANDIDATES_PATH.read_text(encoding="utf-8"))
    news = [c for c in report["candidates"] if c.get("document_type") == "NEWS"]
    return news[:limit]


def _tokens(title):
    pc = _priority_candidates()
    return pc._tokens(title)


def find_corpus_primary_source(candidate, documents, jaccard_threshold=0.5):
    """Looks for ANOTHER real document already in documents.json whose title overlaps this
    candidate's title heavily (same underlying event/story) AND whose canonical_url sits on a
    domain this repo's own connectors already trust. Never invents an overlap threshold result
    -- pure token-Jaccard over real titles, same method priority_candidates.py already uses for
    its cluster signal, applied here for a single, explicit purpose."""
    cand_tokens = _tokens(candidate.get("title"))
    if not cand_tokens:
        return None
    for did, doc in documents.items():
        if did == candidate["document_id"]:
            continue
        host = _host_of(doc.get("canonical_url"))
        if not host or not any(host == d or host.endswith("." + d) for d in TRUSTED_PRIMARY_DOMAINS):
            continue
        other_tokens = _tokens(doc.get("title"))
        if not other_tokens:
            continue
        union_size = len(cand_tokens | other_tokens)
        if union_size == 0:
            continue
        jaccard = len(cand_tokens & other_tokens) / union_size
        if jaccard >= jaccard_threshold:
            return {"document_id": did, "canonical_url": doc.get("canonical_url"),
                    "title": doc.get("title"), "jaccard": round(jaccard, 3)}
    return None


def trace_candidate(candidate, documents):
    host = _host_of(candidate.get("canonical_url"))
    title_lower = (candidate.get("title") or "").lower()

    if host in OPAQUE_REDIRECT_HOSTS:
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "reason": (
                f"canonical_url resolves to opaque redirect host {host!r} "
                "(news.google.com/rss/articles/...); the real destination publisher domain "
                "cannot be determined from stored metadata alone, and no live fetch is "
                "available in this sandbox to resolve it"
            ),
        }

    if host and any(host == d or host.endswith("." + d) for d in TRUSTED_PRIMARY_DOMAINS):
        return {
            "status": "PRIMARY_SOURCE_FOUND",
            "reason": f"document's own canonical_url already sits on a trusted primary-source "
                      f"domain ({host!r})",
        }

    match = find_corpus_primary_source(candidate, documents)
    if match is not None:
        return {
            "status": "PRIMARY_SOURCE_FOUND",
            "reason": (
                f"another real corpus document ({match['document_id']}) with overlapping "
                f"title (jaccard={match['jaccard']}) sits on a trusted primary-source domain"
            ),
            "primary_source_document_id": match["document_id"],
            "primary_source_url": match["canonical_url"],
        }

    if host and any(h in title_lower for h in _REGULATOR_HINTS):
        return {
            "status": "PRIMARY_SOURCE_NOT_FOUND",
            "reason": (
                "title contains a regulator/court/agency hint suggesting a primary source "
                "plausibly exists, but no such document is present in this corpus and no "
                "connector in this repo (Federal Register, Crossref) currently covers it"
            ),
        }

    if host:
        return {
            "status": "NEWS_ONLY",
            "reason": f"canonical_url is a direct, identifiable news-outlet domain ({host!r}) "
                      f"with no primary-source or corroborating-official-record linkage "
                      f"findable in this corpus's existing metadata",
        }

    return {
        "status": "INSUFFICIENT_EVIDENCE",
        "reason": "canonical_url is missing or unparseable -- host could not be determined",
    }


def run_trace(limit=MAX_CANDIDATES, documents=None, candidates_report=None):
    documents = documents if documents is not None else _load_documents()
    candidates = top_news_candidates(candidates_report, limit=limit)

    results = {}
    for cand in candidates:
        outcome = trace_candidate(cand, documents)
        results[cand["document_id"]] = {
            "document_id": cand["document_id"],
            "title": cand.get("title"),
            "source_id": cand.get("source_id"),
            "canonical_url": cand.get("canonical_url"),
            "priority_score": cand.get("score"),
            **outcome,
        }

    by_status = {}
    for r in results.values():
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1

    return {
        "candidates_traced": len(results),
        "status_breakdown": by_status,
        "traces": results,
    }


def main():
    report = run_trace()
    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH}: {report['candidates_traced']} candidates traced, "
          f"status breakdown: {report['status_breakdown']}")


if __name__ == "__main__":
    main()
