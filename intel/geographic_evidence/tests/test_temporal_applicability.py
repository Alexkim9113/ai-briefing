import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import temporal_applicability as ta  # noqa: E402


def test_lbnl_claim_kept_partial_not_collapsed_to_current():
    entry = ta.classify_claim("claim_o1_lbnl_us_dc_2023")
    assert entry["classification"] == ta.PARTIAL_TEMPORAL_MATCH


def test_korea_contracted_capacity_is_forecast_only_not_current_match():
    entry = ta.classify_claim("claim_o1_korea_capital_region_dc_demand")
    assert entry["classification"] == ta.FORECAST_ONLY
    assert entry["classification"] != ta.CURRENT_MATCH


def test_heatwave_claim_out_of_range_vs_annual_trend():
    entry = ta.classify_claim("claim_d641fb1790c3ef53")
    assert entry["classification"] == ta.OUT_OF_RANGE


def test_jevons_claim_historical_context_not_current():
    entry = ta.classify_claim("claim_d170f52f567053e9")
    assert entry["classification"] == ta.HISTORICAL_CONTEXT
    assert entry["classification"] != ta.CURRENT_MATCH


def test_ev_claim_separates_observed_and_forecast():
    entry = ta.classify_claim("claim_f5842e6162c8fefc")
    assert entry["classification"] == ta.PARTIAL_TEMPORAL_MATCH
    assert "2024" in entry["observation_period"]
    assert "2030" in entry["forecast_horizon"]


def test_unknown_claim_id():
    entry = ta.classify_claim("claim_does_not_exist")
    assert entry["classification"] == ta.UNKNOWN


def test_build_result_audit_reports_no_merged_observation_forecast_claims():
    result = ta.build_result()
    assert result["observation_forecast_audit"]["findings"]
    assert "No corrective edit was required" in result["observation_forecast_audit"]["conclusion"]


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return failed


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
