# PHASE M.5E-4 -- item 4/5: the first real TOPIC -> CLAIM/HYPOTHESIS -> INDICATOR ->
# OBSERVATIONS -> OFFICIAL SOURCE link for AI_ENERGY_INFRA's STATISTICAL_CONTEXT node.
#
# Reuses (never forks) intel/foresight_engine/hypothesis_indicator_bridge.py's existing
# link_observable_implication()/evaluate_hypothesis_against_observations() -- the
# Indicator/Observation structure Te's spec explicitly asks to reuse rather than inventing a
# new one, and the same HYPOTHESIS_TEST_OUTCOMES vocabulary
# (CONSISTENT_WITH/INCONSISTENT_WITH/MIXED/NO_CLEAR_SIGNAL/INSUFFICIENT_DATA/NOT_TESTABLE)
# already used throughout this project. Statistics are NOT written into documents.json as
# fake articles -- this stays a separate sidecar file, per Te's explicit instruction.
#
# Real live source: intel/foresight_engine/reality_pilot_result.json's
# worldbank_electric_power_consumption_kr row, fetched for real by reality_shadow's GitHub
# Actions run (HTTP 200, World Bank API, real 2024 Korea kWh-per-capita value). Only ONE real
# period was retained by that pilot, so no trend can be computed -- the honest outcome is
# NO_CLEAR_SIGNAL (an ambiguous single point), never fabricated as CONSISTENT_WITH.
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FORESIGHT_DIR = HERE.parent / "foresight_engine"
sys.path.insert(0, str(FORESIGHT_DIR))
import hypothesis_indicator_bridge as bridge  # noqa: E402

REALITY_PILOT_PATH = FORESIGHT_DIR / "reality_pilot_result.json"
OUT_PATH = HERE / "ai_energy_infra_statistical_link_result.json"

HYPOTHESIS_ID = "hyp_ai_energy_infra_kr_electricity_demand"
OBSERVABLE_IMPLICATION = (
    "AI-driven data-center growth in Korea should be reflected in rising national "
    "per-capita electricity consumption"
)
TARGET_SOURCE_ID = "worldbank_electric_power_consumption_kr"


def _no_trend_direction_fn(obs):
    """Only one real data point exists for this indicator so far -- no second period to compare
    against, so no direction can be honestly computed. Returning None is the correct, honest
    answer; it must never be guessed as FOR/AGAINST from a single value."""
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
