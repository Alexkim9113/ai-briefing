# PHASE M.5E-3 -- item 1: TRANSITION-bucket gap attack for the AI_ENERGY_INFRA deep pilot.
#
# intel/evidence_network/deep_pilot.py found a real, honest gap: for topic AI_ENERGY_INFRA,
# the TRANSITION bucket (BASELINE_CUTOFF=2026-01-01 <= published < CURRENT_CUTOFF=2026-09-01)
# has ZERO documents, so the evidence chain's CONFIRMED_CHANGE node cannot be built from real
# evidence -- there is nothing bridging the single 2025-09/10 BASELINE POLICY document and the
# 2026-09-28/29 CURRENT cluster.
#
# This module is a thin, EXPLICIT REUSE of fetch_federal_register.py's already-hardened
# contract (validate_url/real_json_fetcher/validate_schema/canonicalize_document/run_pilot),
# following the exact pattern of fetch_federal_register_historical.py: only the query URL
# (date window + search terms) and GAP_TYPE differ. No pipeline logic is copied or forked.
#
# The Federal Register API documents real, supported query params for both search terms
# (conditions[term], free text, repeatable) and date ranges
# (conditions[publication_date][gte]/[lte]), see
# https://www.federalregister.gov/developers/documentation/api/v1. This module targets
# exactly the TRANSITION window deep_pilot.py defines (2026-01-01 to 2026-09-01, exclusive of
# CURRENT), with search terms relevant to AI energy-infrastructure transition: "data center",
# "electricity", "power grid", combined with "artificial intelligence" so results stay on
# topic rather than pulling in generic energy notices.
#
# NETWORK REALITY (honest, not assumed): like every other connector in this repo, this was NOT
# run against a live network from this authoring sandbox (outbound HTTPS to
# federalregister.gov is blocked here). Whether the window/terms combination actually returns
# any real TRANSITION-bucket document is UNKNOWN until this runs on GitHub Actions' real
# network. This module does not fabricate that outcome -- see gap_closure_log.json, which
# records the attempt as code-written-and-unit-tested only, not as a closed gap.
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

HIST_DIR = HERE.parent / "historical_acquisition"
sys.path.insert(0, str(HIST_DIR))

import fetch_federal_register as base  # noqa: E402  (reuse, not fork)

OUT_PATH = HERE / "transition_evidence_energy_result.json"

# Real gap type this connector targets -- distinct from INSUFFICIENT_TIME_DEPTH (the M.5E
# historical connector's target) and from MISSING_REGULATORY_HISTORY (the base pilot's
# target): this connector specifically attacks deep_pilot.py's empty TRANSITION bucket for
# topic AI_ENERGY_INFRA.
GAP_TYPE = "TRANSITION_GAP"
TARGET_TOPIC = "AI_ENERGY_INFRA"

# Mirrors deep_pilot.py's own real cutoffs exactly (imported as strings, not re-derived, so
# this connector's window can never silently drift out of sync with the bucket definition it
# is meant to fill). See intel/evidence_network/deep_pilot.py BASELINE_CUTOFF/CURRENT_CUTOFF.
TRANSITION_WINDOW_START = "2026-01-01"  # == deep_pilot.BASELINE_CUTOFF
TRANSITION_WINDOW_END = "2026-09-01"    # == deep_pilot.CURRENT_CUTOFF (exclusive)

# Search terms relevant to AI energy-infrastructure transition. Federal Register's
# conditions[term] is a single free-text field (not a list of ANDed terms), so terms are
# combined into one query string the way a person would type them into the site's own search
# box; this is the same convention fetch_federal_register.py and
# fetch_federal_register_historical.py already use for their own single conditions[term].
SEARCH_TERMS = ("artificial intelligence", "data center", "electricity", "power grid")


def build_transition_fetch_url(window_start=TRANSITION_WINDOW_START,
                                window_end=TRANSITION_WINDOW_END,
                                terms=SEARCH_TERMS):
    """Builds the real Federal Register date-range + term-search query URL for the
    TRANSITION window. Pure function of its arguments (no wall-clock dependency) since the
    window is fixed by deep_pilot.py's own bucket cutoffs, not by "today"."""
    term_query = urllib_quote_plus(" ".join(terms))
    return (
        "https://www.federalregister.gov/api/v1/documents.json"
        f"?conditions%5Bterm%5D={term_query}"
        f"&conditions%5Bpublication_date%5D%5Bgte%5D={window_start}"
        f"&conditions%5Bpublication_date%5D%5Blte%5D={window_end}"
        "&per_page=20&order=oldest"
        "&fields%5B%5D=title&fields%5B%5D=type&fields%5B%5D=abstract"
        "&fields%5B%5D=document_number&fields%5B%5D=html_url&fields%5B%5D=pdf_url"
        "&fields%5B%5D=publication_date&fields%5B%5D=agencies&fields%5B%5D=citation"
    )


def urllib_quote_plus(s):
    import urllib.parse
    return urllib.parse.quote_plus(s)


def run_pilot(fetcher=base.real_json_fetcher, window_start=TRANSITION_WINDOW_START,
              window_end=TRANSITION_WINDOW_END, terms=SEARCH_TERMS, url=None):
    """Reuses base.run_pilot() end-to-end (identical fetch/validate/canonicalize/status
    pipeline) -- only the URL differs, targeting the TRANSITION window with on-topic search
    terms instead of order=newest with no bound. canonicalize_document() (imported, unmodified)
    is reused as-is, so records stay byte-identical in shape to fetch_federal_register.py's and
    remain compatible with admission_gate.py's existing src_federal_register trusted-source
    row."""
    if url is None:
        url = build_transition_fetch_url(window_start, window_end, terms)
    summary = base.run_pilot(fetcher=fetcher, url=url)
    summary["gap_type"] = GAP_TYPE
    summary["target_topic"] = TARGET_TOPIC
    summary["query_window"] = {"start": window_start, "end": window_end, "terms": list(terms)}
    for r in summary["results"]:
        r["gap_type"] = GAP_TYPE
        r["target_topic"] = TARGET_TOPIC
        for doc in r.get("documents_canonicalized", []):
            doc["gap_type_addressed"] = GAP_TYPE
    return summary


def main():
    summary = run_pilot()
    OUT_PATH.write_text(base.json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH} -- window={summary['query_window']} -- overall_status(es): "
          f"{[r['overall_status'] for r in summary['results']]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
