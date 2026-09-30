# PHASE M.5E-4 -- Te explicitly flagged that AI_LABOR's Deep Pilot result (1 SUPPORTED / 7
# NOT_FOUND chain nodes) might reveal corpus bias rather than genuine topic weakness, and asked
# for at least one real acquisition attempt targeting AI_LABOR's official labor-statistics/
# policy sources -- mirroring ai_energy_infra_statistical_link.py's TOPIC -> CLAIM/HYPOTHESIS ->
# INDICATOR -> OBSERVATIONS -> OFFICIAL SOURCE link, built for AI_ENERGY_INFRA in this same
# phase.
#
# Reuses (never forks) intel/foresight_engine/hypothesis_indicator_bridge.py's existing
# link_observable_implication()/evaluate_hypothesis_against_observations() and the same
# HYPOTHESIS_TEST_OUTCOMES vocabulary (CONSISTENT_WITH/INCONSISTENT_WITH/MIXED/NO_CLEAR_SIGNAL/
# INSUFFICIENT_DATA/NOT_TESTABLE). Statistics are NOT written into documents.json as fake
# articles -- this stays a separate sidecar file, per Te's explicit instruction.
#
# Real live source: intel/foresight_engine/reality_pilot_result.json's
# worldbank_unemployment_rate_kr row (World Bank SL.UEM.TOTL.ZS, Korea unemployment rate, ILO
# modeled estimate), fetched for real by reality_shadow's GitHub Actions run. As with the
# AI_ENERGY_INFRA link, only ONE real period is expected to be retained per run, so no trend can
# be honestly computed from this alone -- and even where a second period eventually appears,
# a bare change in the national unemployment rate has no established causal-attribution method
# tying it to AI specifically (labor markets move for many reasons). The honest expected outcome
# is therefore NO_CLEAR_SIGNAL (single ambiguous point) or NOT_TESTABLE (source not yet present
# in a given pilot run) -- this module must never fabricate CONSISTENT_WITH/INCONSISTENT_WITH
# from an unemployment-rate move alone.
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FORESIGHT_DIR = HERE.parent / "foresight_engine"
sys.path.insert(0, str(FORESIGHT_DIR))
import hypothesis_indicator_bridge as bridge  # noqa: E402

REALITY_PILOT_PATH = FORESIGHT_DIR / "reality_pilot_result.json"
OUT_PATH = HERE / "ai_labor_statistical_link_result.json"

HYPOTHESIS_ID = "hyp_ai_labor_kr_unemployment_effect"
OBSERVABLE_IMPLICATION = (
    "AI-driven automation/job displacement in Korea should be reflected in a detectable shift "
    "in the national unemployment rate"
)
TARGET_SOURCE_ID = "worldbank_unemployment_rate_kr"


def _no_trend_direction_fn(obs):
    """Only one real data point exists for this indicator so far -- no second period to compare
    against, and even a real trend in the aggregate unemployment rate has no established method
    for attributing it specifically to AI (versus the many other drivers of labor-market
    movement). Returning None is the correct, honest answer; it must never be guessed as
    FOR/AGAINST from a single value or an uncontrolled aggregate move."""
    return None


def build_link(reality_pilot_result, direction_fn=_no_trend_direction_fn,
                target_source_id=TARGET_SOURCE_ID):
    row = next((r for r in reality_pilot_result.get("results", [])
                if r.get("source_id") == target_source_id), None)
    if row is None or not row.get("observation"):
        return {
            "hypothesis_id": HYPOTHESIS_ID,
            "observable_implication": OBSERVABLE_IMPLICATION,
            "outcome": "NOT_TESTABLE",
            "reason": f"no real observation found for source_id={target_source_id!r} in the "
                      f"reality pilot result -- nothing fabricated",
        }
    indicator = row["indicator"]
    observation = row["observation"]
    indicators = {indicator["indicator_id"]: indicator}
    observations_by_indicator = {indicator["indicator_id"]: [observation]}

    link = bridge.link_observable_implication(
        HYPOTHESIS_ID, OBSERVABLE_IMPLICATION,
        candidate_indicator_ids=[indicator["indicator_id"]],
        indicators=indicators,
    )
    result = bridge.evaluate_hypothesis_against_observations(link, observations_by_indicator, direction_fn)
    result["real_observation_used"] = observation
    result["real_indicator_used"] = indicator
    return result


def main():
    if not REALITY_PILOT_PATH.exists():
        print(f"[statistical-link] no reality pilot result at {REALITY_PILOT_PATH} -- nothing to "
              f"link yet (honest, not an error)")
        return 0
    reality_pilot_result = json.loads(REALITY_PILOT_PATH.read_text(encoding="utf-8"))
    result = build_link(reality_pilot_result)
    OUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[statistical-link] outcome={result.get('outcome')} wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
