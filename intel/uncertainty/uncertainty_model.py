# M.6 -- minimal Uncertainty vocabulary. Uncertainty is never a fabricated confidence number;
# every uncertainty entry names its cause from this fixed vocabulary plus a free-text detail.
UNCERTAINTY_CAUSES = (
    "SOURCE_UNCERTAINTY", "MEASUREMENT_UNCERTAINTY", "TEMPORAL_UNCERTAINTY",
    "GEOGRAPHIC_UNCERTAINTY", "ATTRIBUTION_UNCERTAINTY", "CAUSAL_UNCERTAINTY",
    "ACCESS_UNCERTAINTY", "CONFLICTING_EVIDENCE", "INSUFFICIENT_EVIDENCE",
)


def new_uncertainty(cause, detail):
    assert cause in UNCERTAINTY_CAUSES, f"unknown uncertainty cause: {cause!r}"
    return {"cause": cause, "detail": detail}


def summarize_known_unknown_missing(intelligence_object):
    """Splits an Intelligence Object's own fields into what_is_known / what_is_uncertain /
    what_is_missing -- never fabricates content for any of the three; empty stays empty."""
    return {
        "what_is_known": [s for s in intelligence_object.get("statistics", [])] +
                         [c for c in intelligence_object.get("key_claims", [])],
        "what_is_uncertain": list(intelligence_object.get("uncertainties", [])),
        "what_is_missing": list(intelligence_object.get("known_gaps", [])),
    }
