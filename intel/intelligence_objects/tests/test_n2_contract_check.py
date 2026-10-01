import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import n2_contract_check as m  # noqa: E402


def test_schema_contract_has_no_missing_fields():
    result = m.check_schema_contract()
    assert result["missing_fields"] == []
    assert result["status"] == "READY"


def test_report_skeleton_never_fabricates_missing_sections():
    obj = {"topic": "T", "current_state": "S", "supporting_evidence": [], "research_context": [],
           "statistics": [1], "counterevidence": [], "alternative_explanations": [],
           "uncertainties": [], "provenance": ["p1"]}
    skeleton = m.build_minimal_report_skeleton(obj)
    assert skeleton["Evidence"] == "insufficient evidence"
    assert skeleton["Statistics"] == [1]
    assert skeleton["Research"] == "insufficient evidence"


def test_report_engine_contract_runs_against_real_objects_only():
    result = m.run_report_engine_contract_test()
    assert result["status"] in ("READY", "NOT_TESTABLE")
    if result["status"] == "READY":
        for r in result["results"]:
            assert "intelligence_id" in r
            assert isinstance(r["sections_insufficient_evidence"], list)


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
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
