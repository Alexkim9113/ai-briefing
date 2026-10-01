import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import uncertainty_model as m  # noqa: E402


def test_rejects_unknown_cause():
    try:
        m.new_uncertainty("MADE_UP_CAUSE", "x")
        assert False
    except AssertionError:
        pass


def test_valid_cause_accepted():
    u = m.new_uncertainty("ATTRIBUTION_UNCERTAINTY", "cannot decompose by sector")
    assert u["cause"] == "ATTRIBUTION_UNCERTAINTY"


def test_summarize_never_fabricates_empty_stays_empty():
    obj = {"statistics": [], "key_claims": [], "uncertainties": [], "known_gaps": []}
    s = m.summarize_known_unknown_missing(obj)
    assert s["what_is_known"] == []
    assert s["what_is_uncertain"] == []
    assert s["what_is_missing"] == []


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
