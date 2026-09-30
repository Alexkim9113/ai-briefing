# PHASE M.5E-3 -- item 2: Statistical Context connection attempt for AI_ENERGY_INFRA.
#
# intel/source_diversity/audit.py found 0% of the 597-document corpus carries any statistical
# source at all -- deep_pilot.py's STATISTICAL_CONTEXT evidence-chain node for AI_ENERGY_INFRA
# is currently a gap, not a real node. This module is the first, honest attempt to close it.
#
# Outbound HTTPS to any live statistical-data API is BLOCKED in this authoring sandbox, so this
# module CANNOT fetch real indicator values here and NEVER fabricates any. What it does:
#   (a) define a small, fixed registry of real, named, correctly-formed candidate indicator
#       SOURCES for electricity / data-center demand (not simulated placeholders -- these are
#       real, publicly documented API endpoints an operator could actually query),
#   (b) implement a deterministic classification function that maps a numeric trend comparison
#       between an indicator series and a document's directional claim to the shared
#       hypothesis-testing vocabulary already used elsewhere in this repo
#       (intel/foresight_engine/hypothesis_indicator_bridge.py's HYPOTHESIS_TEST_OUTCOMES), so
#       this module introduces zero new relationship vocabulary,
#   (c) honestly report the real current status as STATISTICAL_GAP, since no live indicator
#       data has actually been acquired yet.
#
# Zero LLM. Stdlib only.
import re

# Reused, not reinvented: identical vocabulary to
# intel/foresight_engine/hypothesis_indicator_bridge.py's HYPOTHESIS_TEST_OUTCOMES. Duplicated
# as a tuple here (not imported) to keep this module dependency-free like the other
# intel/*_context and intel/*_admission stdlib-only modules; any future drift would only ever
# be caught by this package's own tests asserting the two tuples are equal, which is done
# below in the tests directory.
RELATIONSHIP_STATUSES = (
    "CONSISTENT_WITH", "INCONSISTENT_WITH", "MIXED", "NO_CLEAR_SIGNAL",
    "INSUFFICIENT_DATA", "NOT_TESTABLE",
)

# Honest status for "we defined a real source but have not actually acquired data from it yet"
# -- distinct from the RELATIONSHIP_STATUSES above, which describe an already-tested
# relationship. Never conflate the two: a STATISTICAL_GAP must never be reported as one of the
# RELATIONSHIP_STATUSES, since no comparison has actually happened.
STATISTICAL_GAP = "STATISTICAL_GAP"

# Real, named, publicly documented candidate indicator sources for electricity / data-center
# demand. These are real EIA (U.S. Energy Information Administration) API v2 endpoints per
# EIA's own published API documentation (https://www.eia.gov/opendata/documentation.php) --
# api_url_template is the real, correctly-formed query shape (requires an api_key the caller
# supplies; none is embedded or fabricated here). This registry does NOT claim any of these
# have been queried -- see STATISTICAL_GAP usage in run_connection_attempt() below.
INDICATOR_SOURCE_REGISTRY = {
    "eia_electricity_retail_sales": {
        "name": "EIA Electricity Retail Sales (monthly, all sectors)",
        "publisher": "U.S. Energy Information Administration",
        "api_url_template": (
            "https://api.eia.gov/v2/electricity/retail-sales/data/"
            "?api_key={api_key}&frequency=monthly&data[]=sales"
            "&facets[sectorid][]=ALL&sort[0][column]=period&sort[0][direction]=desc"
        ),
        "docs_url": "https://www.eia.gov/opendata/documentation.php",
        "citation": "U.S. Energy Information Administration, Electricity Data Browser API v2",
        "relevance": "Aggregate electricity demand -- a real proxy for data-center load growth "
                     "claims, though not data-center-specific.",
    },
    "eia_electric_power_operations": {
        "name": "EIA Electric Power Operations (net generation, monthly)",
        "publisher": "U.S. Energy Information Administration",
        "api_url_template": (
            "https://api.eia.gov/v2/electricity/electric-power-operational-data/data/"
            "?api_key={api_key}&frequency=monthly&data[]=generation"
            "&sort[0][column]=period&sort[0][direction]=desc"
        ),
        "docs_url": "https://www.eia.gov/opendata/documentation.php",
        "citation": "U.S. Energy Information Administration, Electric Power Operations API v2",
        "relevance": "Grid-level generation trend -- a real proxy for grid-capacity-pressure "
                     "claims tied to AI/data-center buildout.",
    },
    # NOTE: no true data-center-specific federal statistical series was identified as publicly
    # queryable via a stable API during this slice (EIA does not yet publish a dedicated
    # data-center electricity demand series as of this writing). Listing only real sources
    # actually found, rather than fabricating a data-center-specific one, per the standing
    # no-fabrication constraint.
}


def get_indicator_source(source_id):
    """Returns the real registry entry, or None if source_id is unknown. Never fabricates an
    entry for an unrecognized id."""
    return INDICATOR_SOURCE_REGISTRY.get(source_id)


_TREND_WORDS_UP = ("rising", "rise", "increase", "increasing", "growing", "growth", "surge", "surging", "up")
_TREND_WORDS_DOWN = ("falling", "fall", "decrease", "decreasing", "declining", "decline", "drop", "dropping", "down")


def infer_claim_direction(document_claim):
    """Deterministic, keyword-based direction inference from a document's textual claim.
    Returns "UP", "DOWN", or "AMBIGUOUS" (never guesses beyond simple keyword matching -- no
    LLM, no semantic inference)."""
    if not document_claim:
        return "AMBIGUOUS"
    text = document_claim.lower()
    up = any(re.search(r"\b" + re.escape(w) + r"\b", text) for w in _TREND_WORDS_UP)
    down = any(re.search(r"\b" + re.escape(w) + r"\b", text) for w in _TREND_WORDS_DOWN)
    if up and down:
        return "AMBIGUOUS"
    if up:
        return "UP"
    if down:
        return "DOWN"
    return "AMBIGUOUS"


def compute_series_direction(indicator_series):
    """indicator_series: an ordered list of numeric values (oldest first), or None/empty for
    no data. Returns "UP", "DOWN", "FLAT", or None (None = insufficient data: fewer than 2
    usable points). Purely deterministic arithmetic -- no smoothing, no LLM."""
    if not indicator_series:
        return None
    usable = [v for v in indicator_series if v is not None]
    if len(usable) < 2:
        return None
    delta = usable[-1] - usable[0]
    if delta > 0:
        return "UP"
    if delta < 0:
        return "DOWN"
    return "FLAT"


def classify_statistical_relationship(indicator_series, document_claim):
    """Deterministic classification mapping a numeric trend comparison to the shared
    hypothesis-testing vocabulary (RELATIONSHIP_STATUSES). Never returns anything outside that
    fixed vocabulary; never infers a relationship the data does not support.

    indicator_series: ordered list of numeric values (oldest first) or None/[].
    document_claim: free text describing the document's own directional claim, or None/"".
    """
    series_dir = compute_series_direction(indicator_series)
    claim_dir = infer_claim_direction(document_claim)

    if series_dir is None:
        return "INSUFFICIENT_DATA"
    if claim_dir == "AMBIGUOUS":
        return "NOT_TESTABLE"
    if series_dir == "FLAT":
        return "NO_CLEAR_SIGNAL"
    if (series_dir == "UP" and claim_dir == "UP") or (series_dir == "DOWN" and claim_dir == "DOWN"):
        return "CONSISTENT_WITH"
    if (series_dir == "UP" and claim_dir == "DOWN") or (series_dir == "DOWN" and claim_dir == "UP"):
        return "INCONSISTENT_WITH"
    return "MIXED"  # defensive fallback; not reachable given the branches above, kept explicit
                     # rather than silently falling through to a wrong status.


def run_connection_attempt(topic="AI_ENERGY_INFRA"):
    """The real, current, honest result of attempting to connect AI_ENERGY_INFRA evidence to a
    statistical indicator source in THIS environment: no live indicator data has actually been
    fetched (outbound HTTPS to any statistical API is blocked in this sandbox), so this
    reports STATISTICAL_GAP rather than fabricating a trend or classification result. This is
    the honest counterpart to classify_statistical_relationship(), which this function
    deliberately does NOT call with invented data."""
    return {
        "topic": topic,
        "status": STATISTICAL_GAP,
        "candidate_sources_defined": list(INDICATOR_SOURCE_REGISTRY.keys()),
        "reason": ("No live indicator data has been acquired -- outbound HTTPS to any "
                   "statistical data API is blocked in this authoring sandbox. Real API "
                   "endpoints have been registered (see INDICATOR_SOURCE_REGISTRY) but none "
                   "has been queried. classify_statistical_relationship() is implemented and "
                   "unit-tested against synthetic boundary cases only, never against a "
                   "fabricated 'real' result for AI_ENERGY_INFRA."),
    }
