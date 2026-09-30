import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import energy_indicators as ei  # noqa: E402


def test_registry_has_real_named_sources_with_urls():
    assert len(ei.INDICATOR_SOURCE_REGISTRY) >= 1
    for source_id, entry in ei.INDICATOR_SOURCE_REGISTRY.items():
        assert entry["name"]
        assert entry["publisher"]
        assert entry["api_url_template"].startswith("https://")
        assert "{api_key}" in entry["api_url_template"] or "api_key" not in entry["api_url_template"]
        assert entry["citation"]


def test_get_indicator_source_known_and_unknown():
    known_id = next(iter(ei.INDICATOR_SOURCE_REGISTRY))
    assert ei.get_indicator_source(known_id) is not None
    assert ei.get_indicator_source("not_a_real_source_id") is None


def test_compute_series_direction_boundaries():
    assert ei.compute_series_direction(None) is None
    assert ei.compute_series_direction([]) is None
    assert ei.compute_series_direction([5]) is None  # single point -- insufficient
    assert ei.compute_series_direction([5, 5]) == "FLAT"
    assert ei.compute_series_direction([5, 10]) == "UP"
    assert ei.compute_series_direction([10, 5]) == "DOWN"
    assert ei.compute_series_direction([None, None]) is None


def test_infer_claim_direction():
    assert ei.infer_claim_direction("Electricity demand is rising sharply") == "UP"
    assert ei.infer_claim_direction("Demand is falling") == "DOWN"
    assert ei.infer_claim_direction("") == "AMBIGUOUS"
    assert ei.infer_claim_direction(None) == "AMBIGUOUS"
    assert ei.infer_claim_direction("Demand is rising then falling") == "AMBIGUOUS"
    assert ei.infer_claim_direction("Data centers are being built") == "AMBIGUOUS"


# Boundary coverage for all 6 RELATIONSHIP_STATUSES / HYPOTHESIS_TEST_OUTCOMES values.

def test_classify_insufficient_data_when_series_too_short():
    assert ei.classify_statistical_relationship([], "demand is rising") == "INSUFFICIENT_DATA"
    assert ei.classify_statistical_relationship([5], "demand is rising") == "INSUFFICIENT_DATA"
    assert ei.classify_statistical_relationship(None, "demand is rising") == "INSUFFICIENT_DATA"


def test_classify_not_testable_when_claim_ambiguous():
    assert ei.classify_statistical_relationship([1, 2, 3], "demand shifted somehow") == "NOT_TESTABLE"
    assert ei.classify_statistical_relationship([1, 2, 3], "") == "NOT_TESTABLE"


def test_classify_no_clear_signal_when_series_flat():
    assert ei.classify_statistical_relationship([5, 5, 5], "demand is rising") == "NO_CLEAR_SIGNAL"


def test_classify_consistent_with_matching_directions():
    assert ei.classify_statistical_relationship([1, 2, 3], "electricity demand is rising") == "CONSISTENT_WITH"
    assert ei.classify_statistical_relationship([9, 5, 1], "electricity demand is falling") == "CONSISTENT_WITH"


def test_classify_inconsistent_with_opposing_directions():
    assert ei.classify_statistical_relationship([1, 2, 3], "electricity demand is falling") == "INCONSISTENT_WITH"
    assert ei.classify_statistical_relationship([9, 5, 1], "electricity demand is rising") == "INCONSISTENT_WITH"


def test_classify_result_always_in_fixed_vocabulary():
    cases = [
        (None, None), ([], ""), ([1], "rising"), ([1, 1], "rising"),
        ([1, 2], "rising"), ([2, 1], "rising"), ([1, 2], "falling"), ([1, 2], "unclear"),
    ]
    for series, claim in cases:
        result = ei.classify_statistical_relationship(series, claim)
        assert result in ei.RELATIONSHIP_STATUSES


def test_relationship_statuses_matches_shared_hypothesis_vocabulary():
    sys.path.insert(0, str(PKG_DIR.parent / "foresight_engine"))
    import hypothesis_indicator_bridge as hib  # noqa: E402
    assert set(ei.RELATIONSHIP_STATUSES) == set(hib.HYPOTHESIS_TEST_OUTCOMES)


def test_run_connection_attempt_reports_honest_statistical_gap_not_fabricated_result():
    result = ei.run_connection_attempt()
    assert result["topic"] == "AI_ENERGY_INFRA"
    assert result["status"] == ei.STATISTICAL_GAP
    assert result["status"] not in ei.RELATIONSHIP_STATUSES
    assert len(result["candidate_sources_defined"]) >= 1
    assert "blocked" in result["reason"].lower() or "no live" in result["reason"].lower()


def main():
    tests = [v for k, v in globals().items() if k.startswith("test_")]
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
