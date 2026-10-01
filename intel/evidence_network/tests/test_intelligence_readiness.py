import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))
import intelligence_readiness as m  # noqa: E402

_VALUES = {"READY", "CONDITIONALLY_READY", "NOT_READY"}


def test_exactly_15_questions():
    result = m.build_readiness()
    assert len(result["questions"]) == 15


def test_every_question_value_is_valid():
    result = m.build_readiness()
    for q, v in result["questions"].items():
        assert v in _VALUES, f"{q} has invalid value {v!r}"


def test_7_final_verdicts_never_merged_into_one_field():
    result = m.build_readiness()
    verdicts = result["final_verdicts_7_independent"]
    assert len(verdicts) == 7
    assert "overall" not in verdicts
    assert "composite" not in verdicts


def test_m6_entry_is_go_conditional_go_or_no_go():
    result = m.build_readiness()
    assert result["final_verdicts_7_independent"]["M6_ENTRY"] in ("GO", "CONDITIONAL_GO", "NO_GO")


def test_every_verdict_has_reasoning():
    result = m.build_readiness()
    for key in result["final_verdicts_7_independent"]:
        assert key in result["final_verdicts_reasoning"], f"{key} missing reasoning"


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
