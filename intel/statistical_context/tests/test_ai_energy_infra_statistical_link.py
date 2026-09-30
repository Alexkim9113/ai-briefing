import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))
import ai_energy_infra_statistical_link as link_mod  # noqa: E402


def _fixture_pilot_result(period="2024", value=11350.16):
    indicator = {
        "indicator_id": "ind_worldbank_kr_electric_power_consumption_pc",
        "canonical_name": "KR_ELECTRIC_POWER_CONSUMPTION_KWH_PC",
        "domain": "ENERGY",
        "unit": "KWH_PER_CAPITA",
        "source_organization": "World Bank",
    }
    observation = {
        "observation_id": f"obs_test_{period}",
        "indicator_id": indicator["indicator_id"],
        "period": period,
        "value": value,
        "unit": "KWH_PER_CAPITA",
        "status": "OFFICIAL_REPORTED",
    }
    return {
        "results": [
            {
                "source_id": "worldbank_electric_power_consumption_kr",
                "organization": "World Bank",
                "indicator": indicator,
                "observation": observation,
            }
        ]
    }


def test_real_source_present_but_single_point_is_honestly_ambiguous():
    result = link_mod.build_link(_fixture_pilot_result())
    assert result["outcome"] in link_mod.bridge.HYPOTHESIS_TEST_OUTCOMES
    # A single data point with no comparison direction must never be fabricated as
    # CONSISTENT_WITH/INCONSISTENT_WITH.
    assert result["outcome"] not in ("CONSISTENT_WITH", "INCONSISTENT_WITH")
    assert result["real_observation_used"]["value"] == 11350.16


def test_missing_source_is_not_testable_not_fabricated():
    empty = {"results": []}
    result = link_mod.build_link(empty)
    assert result["outcome"] == "NOT_TESTABLE"
    assert "real_observation_used" not in result


def test_direction_fn_wiring_can_detect_a_real_trend_if_given_one():
    # Proves the machinery CAN detect a real trend once a direction_fn has something to compare
    # against -- this uses a synthetic direction_fn (not fabricated data) purely to verify the
    # wiring correctly propagates CONSISTENT_WITH when a supporting signal exists.
    pilot = _fixture_pilot_result()
    result = link_mod.build_link(pilot, direction_fn=lambda obs: "FOR")
    assert result["outcome"] == "CONSISTENT_WITH"
    result_against = link_mod.build_link(pilot, direction_fn=lambda obs: "AGAINST")
    assert result_against["outcome"] == "INCONSISTENT_WITH"


def main():
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
