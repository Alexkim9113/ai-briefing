# N-6 PRIORITIES 4-6 -- Policy Research / Counterevidence / Longitudinal live acquisition tests.
# These exercise the REAL network path (same as source_health_model's own tests) against the
# sandbox's actual (blocked) egress -- they assert the honest-failure contract, never a specific
# live-network outcome, since that outcome is environment-dependent and out of this session's
# control (and the spec never allows fabricating a different one).
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import policy_research_acquisition as pra  # noqa: E402
import counterevidence_live_acquisition as cla  # noqa: E402
import longitudinal_evidence_acquisition as lea  # noqa: E402

VALID_OUTCOMES = {"ACCESS_BLOCKED", "SEARCH_NOT_RUN", "SEARCH_RUN_NO_EVIDENCE", "NO_REGISTERED_SOURCE"}


def test_policy_research_every_result_has_a_valid_honest_outcome():
    results = pra.attempt_policy_research_acquisition()
    assert results, "no results produced"
    for r in results:
        assert r["acquisition_outcome"] in VALID_OUTCOMES


def test_policy_research_never_fabricates_a_healthy_or_supported_claim():
    results = pra.attempt_policy_research_acquisition()
    for r in results:
        assert r["acquisition_outcome"] not in ("SUPPORTED", "HEALTHY", "CLAIM_ADMITTED")


def test_policy_research_oecd_iea_kdi_recorded_as_no_registered_source_not_guessed():
    results = pra.attempt_policy_research_acquisition()
    by_inst = {r["institution"]: r for r in results}
    for inst in ("OECD", "IEA", "KDI"):
        assert by_inst[inst]["acquisition_outcome"] == "NO_REGISTERED_SOURCE"
        assert "source_url" not in by_inst[inst]


def test_policy_research_save_result_writes_valid_json():
    results = pra.attempt_policy_research_acquisition()
    path = pra.save_result(results)
    assert path.exists()
    import json
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["results"] == results


def test_counterevidence_every_result_has_a_valid_honest_outcome():
    results = cla.attempt_counterevidence_acquisition()
    assert results
    for r in results:
        assert r["acquisition_outcome"] in VALID_OUTCOMES


def test_counterevidence_never_renders_as_absence_of_counterevidence():
    """Section: SEARCH_RUN_NO_EVIDENCE / ACCESS_BLOCKED must never be reported as '반대 증거가
    없다' (no counterevidence exists) -- this module records only the machine-readable outcome
    enum, never a natural-language absence claim."""
    results = cla.attempt_counterevidence_acquisition()
    for r in results:
        assert "없다" not in json_dump_str(r)


def json_dump_str(d):
    import json
    return json.dumps(d, ensure_ascii=False)


def test_longitudinal_every_period_attempted():
    results = lea.attempt_longitudinal_acquisition()
    periods = {r["period"] for r in results}
    assert periods == {"BASELINE", "TRANSITION", "CURRENT"}


def test_longitudinal_never_constructs_structure_when_blocked():
    results = lea.attempt_longitudinal_acquisition()
    path = lea.save_result(results)
    import json
    data = json.loads(path.read_text(encoding="utf-8"))
    if data["all_periods_blocked"]:
        assert data["longitudinal_structure_constructed"] is False


def test_longitudinal_date_ranges_differ_per_period_same_indicator():
    results = lea.attempt_longitudinal_acquisition()
    date_ranges = [r["date_range"] for r in results]
    assert len(set(date_ranges)) == len(date_ranges)  # each period uses a distinct window
    indicators = {r["indicator"] for r in results}
    assert indicators == {"EG.USE.ELEC.KH.PC"}  # same already-registered indicator, no new one


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
        except Exception as e:
            failed += 1
            print(f"ERROR {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
