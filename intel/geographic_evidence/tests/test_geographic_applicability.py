import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import geographic_applicability as ga  # noqa: E402


def test_pjm_evidence_not_matched_for_usa_as_a_whole():
    state, _ = ga.classify_hypothesis_region(["claim_5787125ab5f0110b"], "USA")
    assert state == ga.PARTIAL_MATCH
    assert state != ga.MATCHED


def test_us_evidence_not_applied_to_korea():
    state, _ = ga.classify_hypothesis_region(["claim_o1_lbnl_us_dc_2023"], "KOREA")
    assert state == ga.OUT_OF_SCOPE
    assert state not in (ga.MATCHED, ga.PARTIAL_MATCH)


def test_korea_evidence_not_applied_to_usa():
    state, _ = ga.classify_hypothesis_region(["claim_o1_korea_capital_region_dc_demand"], "USA")
    assert state == ga.OUT_OF_SCOPE
    assert state not in (ga.MATCHED, ga.PARTIAL_MATCH)


def test_ireland_style_country_figure_never_matched_as_eu_average():
    # EV claim carries an EU-specific forecast figure, not a country-level Ireland one, but
    # the same discipline applies: a sub-region/country figure is never MATCHED for the
    # larger region, only PARTIAL_MATCH at most.
    state, _ = ga.classify_hypothesis_region(["claim_f5842e6162c8fefc"], "EU")
    assert state == ga.PARTIAL_MATCH
    assert state != ga.MATCHED
    assert "IRELAND" in ga.REGIONS
    assert "never be used as an EU-wide average" in ga.IRELAND_DC_SHARE_NOTE


def test_china_derivative_estimate_never_promoted_to_official_observed_value():
    state, reasons = ga.classify_hypothesis_region(["claim_d170f52f567053e9"], "CHINA")
    assert state == ga.OUT_OF_SCOPE
    assert any("derivative" in r or "never be fabricated" in r for r in reasons)


def test_korea_contracted_capacity_flagged_not_consumption():
    state, reasons = ga.classify_hypothesis_region(
        ["claim_o1_korea_capital_region_dc_demand"], "SEOUL_METRO")
    assert state == ga.MATCHED
    assert any("CONTRACTED power capacity" in r and "not observed AI electricity consumption" in r
               for r in reasons)


def test_unknown_when_no_claims():
    state, reasons = ga.classify_hypothesis_region([], "USA")
    assert state == ga.UNKNOWN
    assert reasons


def test_build_result_covers_all_regions_for_every_hypothesis():
    result = ga.build_result()
    assert set(result["regions_considered"]) == set(ga.REGIONS)
    for code, entry in result["per_hypothesis"].items():
        assert set(entry["regions"].keys()) == set(ga.REGIONS)
        for region, info in entry["regions"].items():
            assert info["state"] in (ga.MATCHED, ga.PARTIAL_MATCH, ga.OUT_OF_SCOPE, ga.UNKNOWN)


def test_h4_korea_and_pjm_matched_but_not_national_us():
    result = ga.build_result()
    h4 = result["per_hypothesis"].get("H4")
    assert h4 is not None
    assert h4["regions"]["PJM"]["state"] == ga.MATCHED
    assert h4["regions"]["SEOUL_METRO"]["state"] == ga.MATCHED
    assert h4["regions"]["USA"]["state"] != ga.MATCHED
    assert h4["regions"]["CHINA"]["state"] in (ga.OUT_OF_SCOPE, ga.UNKNOWN)


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
