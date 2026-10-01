import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))
import gap_closure_matrix as m  # noqa: E402


def test_all_19_gaps_covered_none_merged_or_dropped():
    matrix = m.build_gap_closure_matrix()
    assert matrix["total_gaps"] == 19


def test_every_status_is_valid():
    matrix = m.build_gap_closure_matrix()
    for gap_id, closure in matrix["closures"].items():
        assert closure["status"] in m._VALID_STATUSES


def test_closed_or_partially_closed_or_refined_has_evidence_reference():
    matrix = m.build_gap_closure_matrix()
    for gap_id, closure in matrix["closures"].items():
        if closure["status"] in ("CLOSED", "PARTIALLY_CLOSED", "REFINED"):
            assert closure.get("evidence_reference"), f"{gap_id} ({closure['status']}) missing evidence_reference"


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
