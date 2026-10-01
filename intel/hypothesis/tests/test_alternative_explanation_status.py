import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import alternative_explanation_status as m  # noqa: E402


def test_no_evidence_is_unsupported_not_fabricated():
    r = m.new_alternative_explanation_record("hyp1", "manufacturing reshoring", evidence_ids=[])
    assert r["status"] == "UNSUPPORTED_ALTERNATIVE"


def test_with_evidence_is_evidence_connected():
    r = m.new_alternative_explanation_record("hyp1", "EV adoption", evidence_ids=["ev1"])
    assert r["status"] == "EVIDENCE_CONNECTED"


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
