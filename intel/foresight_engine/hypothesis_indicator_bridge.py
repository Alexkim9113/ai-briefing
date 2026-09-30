# PHASE M.3 — Hypothesis <-> Indicator bridge (spec Step 7). Extends historical_analogy.py's
# `observable_implications`/`candidate_indicators` fields (added empty in M.2) with real linking
# for the first time. Never produces VERIFIED/CONFIRMED - only the defined vocabulary below.
from reality_indicator import check_comparability, MISSING

HYPOTHESIS_TEST_OUTCOMES = (
    "CONSISTENT_WITH", "INCONSISTENT_WITH", "MIXED", "NO_CLEAR_SIGNAL",
    "INSUFFICIENT_DATA", "NOT_TESTABLE",
)

REALITY_SIGNAL_STATUSES = (
    "REALITY_SUPPORT", "REALITY_COUNTEREVIDENCE", "REALITY_MIXED", "REALITY_INSUFFICIENT",
)


def link_observable_implication(hypothesis_id, observable_implication, candidate_indicator_ids,
                                 indicators=None):
    """Attaches candidate_indicator_ids to one observable implication of a hypothesis. Never
    auto-selects which indicator is "right" - all candidates are kept. Indicators not found in
    the registry are listed under `unresolved_indicator_ids`, never silently dropped."""
    indicators = indicators or {}
    resolved = [iid for iid in candidate_indicator_ids if iid in indicators]
    unresolved = [iid for iid in candidate_indicator_ids if iid not in indicators]
    return {
        "hypothesis_id": hypothesis_id,
        "observable_implication": observable_implication,
        "candidate_indicator_ids": resolved,
        "unresolved_indicator_ids": unresolved,
        "comparability_status": _cross_comparability(resolved, indicators),
    }


def _cross_comparability(indicator_ids, indicators):
    if len(indicator_ids) < 2:
        return "UNKNOWN" if not indicator_ids else "N_A_SINGLE_INDICATOR"
    a, b = indicators[indicator_ids[0]], indicators[indicator_ids[1]]
    return check_comparability(a, b)["status"]


def evaluate_hypothesis_against_observations(link, observations_by_indicator, direction_fn):
    """link: output of link_observable_implication(). observations_by_indicator:
    {indicator_id: [observation dicts]}. direction_fn(observation) -> "FOR" | "AGAINST" |
    "AMBIGUOUS" | None (None = no usable value, e.g. MISSING). Never lets a single
    favorable-direction indicator alone flip the result to a VERIFIED-like status - only the
    HYPOTHESIS_TEST_OUTCOMES vocabulary is ever returned, and supporting/counter/ambiguous
    indicators are ALL preserved, never dropped."""
    if not link["candidate_indicator_ids"]:
        return _test_result(link, "NOT_TESTABLE", [], [], [], "no candidate indicators linked")

    supporting, counter, ambiguous = [], [], []
    any_data = False
    for iid in link["candidate_indicator_ids"]:
        obs_list = observations_by_indicator.get(iid, [])
        for obs in obs_list:
            if obs.get("value") is MISSING or obs.get("value") is None:
                continue
            any_data = True
            d = direction_fn(obs)
            if d == "FOR":
                supporting.append({"indicator_id": iid, "observation_id": obs.get("observation_id")})
            elif d == "AGAINST":
                counter.append({"indicator_id": iid, "observation_id": obs.get("observation_id")})
            else:
                ambiguous.append({"indicator_id": iid, "observation_id": obs.get("observation_id")})

    if not any_data:
        return _test_result(link, "INSUFFICIENT_DATA", supporting, counter, ambiguous,
                             "linked indicators have no usable (non-missing) observations")
    if link["comparability_status"] in ("NOT_COMPARABLE",):
        return _test_result(link, "NOT_TESTABLE", supporting, counter, ambiguous,
                             "candidate indicators are NOT_COMPARABLE - cannot jointly test")
    if supporting and counter:
        return _test_result(link, "MIXED", supporting, counter, ambiguous,
                             "both supporting and counter observations found")
    if supporting and not counter:
        return _test_result(link, "CONSISTENT_WITH", supporting, counter, ambiguous, None)
    if counter and not supporting:
        return _test_result(link, "INCONSISTENT_WITH", supporting, counter, ambiguous, None)
    return _test_result(link, "NO_CLEAR_SIGNAL", supporting, counter, ambiguous,
                         "only ambiguous-direction observations found")


def _test_result(link, outcome, supporting, counter, ambiguous, reason):
    assert outcome in HYPOTHESIS_TEST_OUTCOMES, outcome
    return {
        "hypothesis_id": link["hypothesis_id"],
        "observable_implication": link["observable_implication"],
        "outcome": outcome,
        "reason": reason,
        "supporting_indicators": supporting,
        "counter_indicators": counter,
        "ambiguous_indicators": ambiguous,
        "comparability_status": link["comparability_status"],
    }


def build_alternative_explanations(observed_pattern, candidate_explanations, evidence_ids_by_explanation):
    """Reuses epistemic_layer's alternative-explanation vocabulary/shape (never a "winner" is
    picked - see epistemic_layer/alternative_explanation.py's own comment: no evidence-free
    explanation is ever generated here either)."""
    out = []
    for explanation in candidate_explanations:
        evidence_ids = evidence_ids_by_explanation.get(explanation, [])
        if not evidence_ids:
            continue  # never generate an evidence-free alternative explanation
        out.append({
            "observed_pattern": observed_pattern,
            "explanation": explanation,
            "evidence_ids": list(evidence_ids),
        })
    return out


# ---------------------------------------------------------------------------
# Reality <-> Structural-Change / View-Revision connection (Step 8). Read-only signal only -
# the existing epistemic contract / human view-revision approval stays authoritative. This
# function NEVER mutates an Operator View; it only returns a candidate signal a caller may
# offer to the existing View Revision Loop.
# ---------------------------------------------------------------------------
def assess_reality_signal_for_structural_change(structural_change_id, hypothesis_test_results):
    """hypothesis_test_results: list of evaluate_hypothesis_against_observations() outputs tied
    to this structural change candidate. Returns a REALITY_SIGNAL_STATUSES verdict plus the raw
    results (never summarized away) - this is offered to the View Revision Loop as a candidate
    signal, never applied automatically."""
    if not hypothesis_test_results:
        return {"structural_change_id": structural_change_id, "signal": "REALITY_INSUFFICIENT",
                "reason": "no hypothesis test results available", "results": []}
    outcomes = [r["outcome"] for r in hypothesis_test_results]
    if all(o in ("INSUFFICIENT_DATA", "NOT_TESTABLE") for o in outcomes):
        signal = "REALITY_INSUFFICIENT"
    elif any(o == "CONSISTENT_WITH" for o in outcomes) and any(o == "INCONSISTENT_WITH" for o in outcomes):
        signal = "REALITY_MIXED"
    elif any(o == "CONSISTENT_WITH" for o in outcomes):
        signal = "REALITY_SUPPORT"
    elif any(o == "INCONSISTENT_WITH" for o in outcomes):
        signal = "REALITY_COUNTEREVIDENCE"
    else:
        signal = "REALITY_INSUFFICIENT"
    return {
        "structural_change_id": structural_change_id,
        "signal": signal,
        "results": hypothesis_test_results,
        "note": "candidate signal only - does not approve/mutate any Operator View or "
                "structural change; the human View Revision Loop remains authoritative",
    }
