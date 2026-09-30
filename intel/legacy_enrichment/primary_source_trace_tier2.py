# PHASE M.5E-3 slice: Legacy Enrichment continuation -- tier 2 (READ-ONLY, sidecar output only).
#
# M.5E's primary_source_trace.py traced the top 5 NEWS-type candidates from
# priority_candidates.py's top-20 priority list (via its own top_news_candidates(), which filters
# the top-20 to document_type == "NEWS" and takes the first 5). This module extends that SAME
# trace method (trace_candidate(), imported and reused verbatim -- not reimplemented, not a new
# status vocabulary) to the NEXT tier of the same priority list.
#
# JUDGMENT CALL (documented, not hidden): the M.5E-3 instructions ask for "ranks 6-15 of the same
# existing priority list". Taken LITERALLY against the top-20 list's own rank order (1-indexed,
# by score then document_id, exactly as priority_candidates.py sorts it), ranks 6-8 are
# document_ids that primary_source_trace.py's NEWS-only filter ALREADY selected and traced as
# part of its top-5 NEWS set (that filter skips the 3 highest-scoring POLICY documents at ranks
# 1-3, so its "top 5 NEWS" lands at overall ranks 4-8, not ranks 1-5). Re-tracing ranks 6-8 here
# would duplicate tier 1's own committed output for those 3 documents, not extend it. Instead,
# this module traces the NEXT 10 documents in the SAME top-20 list that tier 1 did NOT already
# trace (in the list's own rank order) -- for the current corpus that works out to overall ranks
# 1-3, 9, and 10-15. This is reported explicitly below (`already_traced_excluded`,
# `rank_range_note`) so the substitution is never silently assumed.
#
# Zero LLM. Deterministic Python, stdlib only. Never mutates intel/documents.json.
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
DOCUMENTS_PATH = INTEL_DIR / "documents.json"
CANDIDATES_PATH = HERE / "priority_candidates.json"
OUT_PATH = HERE / "primary_source_trace_tier2_result.json"

TIER2_SIZE = 10


def _load_isolated(path, unique_name):
    key = f"_legacy_enrichment_isolated__{unique_name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


def _primary_source_trace():
    return _load_isolated(HERE / "primary_source_trace.py", "primary_source_trace")


def _load_documents():
    pst = _primary_source_trace()
    return pst._load_documents()


def select_tier2_candidates(candidates_report=None, tier2_size=TIER2_SIZE):
    """Returns (tier2_candidates, already_traced_ids, rank_range_note) -- the next `tier2_size`
    candidates from the top-20 list, in the list's own existing rank order, EXCLUDING whichever
    document_ids tier 1 (primary_source_trace.py's own top_news_candidates(), unmodified) already
    selected."""
    pst = _primary_source_trace()
    candidates_report = (
        candidates_report if candidates_report is not None
        else json.loads(CANDIDATES_PATH.read_text(encoding="utf-8"))
    )
    all_candidates = candidates_report["candidates"]
    tier1_ids = {c["document_id"] for c in pst.top_news_candidates(candidates_report)}

    tier2 = []
    ranks_included = []
    for rank, cand in enumerate(all_candidates, start=1):
        if cand["document_id"] in tier1_ids:
            continue
        tier2.append(cand)
        ranks_included.append(rank)
        if len(tier2) >= tier2_size:
            break

    rank_range_note = (
        f"tier 1 already traced overall ranks {sorted(_ranks_of(all_candidates, tier1_ids))}; "
        f"tier 2 (this module) covers overall ranks {ranks_included} of the same top-20 list "
        f"(the next {len(tier2)} candidates not already traced)"
    )
    return tier2, sorted(tier1_ids), rank_range_note


def _ranks_of(all_candidates, ids):
    return [i + 1 for i, c in enumerate(all_candidates) if c["document_id"] in ids]


def run_tier2_trace(documents=None, candidates_report=None, tier2_size=TIER2_SIZE):
    documents = documents if documents is not None else _load_documents()
    pst = _primary_source_trace()
    tier2_candidates, tier1_ids, rank_range_note = select_tier2_candidates(
        candidates_report, tier2_size
    )

    results = {}
    for cand in tier2_candidates:
        outcome = pst.trace_candidate(cand, documents)
        results[cand["document_id"]] = {
            "document_id": cand["document_id"],
            "title": cand.get("title"),
            "document_type": cand.get("document_type"),
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
        "already_traced_excluded": tier1_ids,
        "rank_range_note": rank_range_note,
        "status_vocabulary_used": pst.STATUS_VALUES,
        "relationship_vocabulary_note": (
            "A general REPORTS_ON/DERIVED_FROM/PRIMARY_SOURCE_FOR/CITES/CONFIRMS/CONTRADICTS "
            "relationship-typed vocabulary does NOT exist as a single unified system in this "
            "codebase today. REPORTS_ON exists but narrowly, as a DOI/arXiv citation-detection "
            "relationship computed by evidence_service.resolve_reports_on() and stored in "
            "intel/relationships.json (and its company/government analogue in "
            "reports_on_expansion.py -> intel/relationships_company_gov.json); "
            "DERIVED_FROM_SAME_SOURCE/SHARED_ORIGIN/INDEPENDENT/UNKNOWN is a separate vocabulary "
            "used only by operator_brain/source_independence.py for evidence-family "
            "independence assessment; CONTRADICTS/SUPPORTS/EXTENDS/QUALIFIES/WEAKENS/"
            "REVEALS_BOUNDARY is yet another, separate vocabulary used only by "
            "operator_brain/view_revision.py for view-revision scoring. None of these three "
            "vocabularies is the general-purpose primary-source-trace relationship type this "
            "spec describes, and none is reused here -- this module instead reuses "
            "primary_source_trace.py's own NEWS_ONLY/PRIMARY_SOURCE_FOUND/"
            "PRIMARY_SOURCE_NOT_FOUND/OFFICIAL_CORROBORATED/INDEPENDENTLY_CORROBORATED/"
            "INSUFFICIENT_EVIDENCE status vocabulary, exactly as instructed, rather than "
            "inventing a new relationship-typed vocabulary of its own."
        ),
        "traces": results,
    }


def main():
    report = run_tier2_trace()
    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {OUT_PATH}: {report['candidates_traced']} tier-2 candidates traced, "
        f"status breakdown: {report['status_breakdown']}"
    )


if __name__ == "__main__":
    main()
