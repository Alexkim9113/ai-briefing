# N-5 Section 30-31 -- PDF Internal Validation tests.
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import pdf_internal_validation as piv  # noqa: E402


def test_validate_all_covers_both_real_reports():
    results = piv.validate_all()
    assert len(results) == 2
    ids = {r["intelligence_id"] for r in results}
    assert ids == set(piv.REAL_REPORT_IDS)


def test_both_pdfs_pass_binary_validity():
    results = piv.validate_all()
    for r in results:
        assert r["pdf_binary_validity"]["ok"] is True


def test_both_pdfs_pass_source_html_content_checks():
    results = piv.validate_all()
    for r in results:
        assert r["all_source_html_checks_passed"] is True
        assert all(r["content_checks_on_source_html"].values())


def test_pdf_text_extraction_honestly_not_testable_not_claimed_ready():
    results = piv.validate_all()
    for r in results:
        assert r["pdf_text_extraction"] == "NOT_TESTABLE"


def test_source_html_hash_is_deterministic_for_same_canonical_report():
    r1 = piv.validate_one("intel_87210a61730c22b9")
    r2 = piv.validate_one("intel_87210a61730c22b9")
    assert r1["source_html_hash"] == r2["source_html_hash"]


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
