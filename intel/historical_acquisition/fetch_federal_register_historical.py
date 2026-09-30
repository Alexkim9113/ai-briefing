# PHASE M.5E -- first slice, item 3: temporal-span extension groundwork.
#
# The real corpus's most severe, proven gap is INSUFFICIENT_TIME_DEPTH (see
# intel/historical_acquisition/gap_source_map.py and intel/temporal_depth/): 577 documents span
# only 8 days (2026-09-22 to 2026-09-30). fetch_federal_register.py's existing pilot always
# queries order=newest with no date bound, so re-running it can never reach further back in
# time than "whatever is newest right now" -- it cannot, by construction, extend the corpus's
# temporal span.
#
# The Federal Register API documents real, supported date-range query parameters
# (conditions[publication_date][gte] / conditions[publication_date][lte], see
# https://www.federalregister.gov/developers/documentation/api/v1), so this module queries an
# explicit OLDER date window with order=oldest, giving a genuine (not simulated) chance of
# pulling in documents that predate the current 8-day window, once it actually runs against a
# live network.
#
# This is a thin, EXPLICIT REUSE of fetch_federal_register.py's already-hardened contract --
# validate_url()/real_json_fetcher()/validate_schema()/canonicalize_document()/run_pilot() are
# all imported and called as-is, not copied or forked. Only FETCH_URL and OUT_PATH differ.
# Zero LLM. Never touches documents.json (writes only its own shadow-result sidecar file). Not
# wired into .github/workflows/daily.yml by this module -- a supervising session decides that,
# exactly as with the M.5D Crossref connector.
#
# NETWORK REALITY (honest, not assumed): like fetch_federal_register.py, this was NOT run
# against a live network from this authoring sandbox (outbound HTTPS to federalregister.gov is
# blocked here). Its real reachability and whether the date-range window actually returns
# older documents is unknown until it runs on GitHub Actions' real network -- this file does
# not fabricate that result.
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fetch_federal_register as base  # noqa: E402  (reuse, not fork)

OUT_PATH = HERE / "federal_register_historical_pilot_result.json"

# Real gap type this connector targets, per gap_source_map.py's own vocabulary -- distinct from
# fetch_federal_register.py's MISSING_REGULATORY_HISTORY, since this connector's purpose is
# specifically extending the corpus's TIME SPAN, not sourcing a missing regulatory document
# type.
GAP_TYPE = "INSUFFICIENT_TIME_DEPTH"

# A window older than the current 8-day corpus span, so a successful run has a genuine chance
# of introducing documents outside it. Bounds are computed at import/call time (not hardcoded
# to one date) so this stays correct on every future run, per order=oldest within the window.
_DEFAULT_WINDOW_DAYS = 365
_DEFAULT_WINDOW_OFFSET_DAYS = 30  # end the window this many days before "today", so a rerun a
                                  # few days later doesn't just re-request the exact same window


def build_historical_fetch_url(window_days=_DEFAULT_WINDOW_DAYS,
                                offset_days=_DEFAULT_WINDOW_OFFSET_DAYS,
                                as_of=None):
    """Builds the real Federal Register date-range query URL. as_of lets tests pin a fixed
    'today' instead of depending on wall-clock time."""
    today = as_of or datetime.now(timezone.utc).date()
    window_end = today - timedelta(days=offset_days)
    window_start = window_end - timedelta(days=window_days)
    return (
        "https://www.federalregister.gov/api/v1/documents.json"
        "?conditions%5Bterm%5D=artificial+intelligence"
        f"&conditions%5Bpublication_date%5D%5Bgte%5D={window_start.isoformat()}"
        f"&conditions%5Bpublication_date%5D%5Blte%5D={window_end.isoformat()}"
        "&per_page=20&order=oldest"
        "&fields%5B%5D=title&fields%5B%5D=type&fields%5B%5D=abstract"
        "&fields%5B%5D=document_number&fields%5B%5D=html_url&fields%5B%5D=pdf_url"
        "&fields%5B%5D=publication_date&fields%5B%5D=agencies&fields%5B%5D=citation"
    ), window_start.isoformat(), window_end.isoformat()


def run_pilot(fetcher=base.real_json_fetcher, window_days=_DEFAULT_WINDOW_DAYS,
              offset_days=_DEFAULT_WINDOW_OFFSET_DAYS, as_of=None, url=None):
    """Reuses base.run_pilot() end-to-end (identical fetch/validate/canonicalize/status
    pipeline) -- the only difference is the URL, which points at an explicit older date window
    instead of order=newest with no bound. canonicalize_document() (imported, unmodified) is
    reused as-is, so records here are byte-identical in shape to fetch_federal_register.py's,
    remaining compatible with the same admission_gate.py trusted-source row (src_federal_register)."""
    if url is None:
        url, window_start, window_end = build_historical_fetch_url(window_days, offset_days, as_of)
    else:
        window_start = window_end = None
    summary = base.run_pilot(fetcher=fetcher, url=url)
    summary["gap_type"] = GAP_TYPE
    summary["query_window"] = {"start": window_start, "end": window_end,
                                "window_days": window_days, "offset_days": offset_days}
    for r in summary["results"]:
        r["gap_type"] = GAP_TYPE
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
