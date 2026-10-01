import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))
import evidence_yield_funnel as m  # noqa: E402


def test_all_9_funnel_stages_present():
    funnel = m.build_funnel()
    assert set(funnel["stages"].keys()) == set(m.FUNNEL_STAGES)


def test_uninstrumented_stages_report_none_not_a_fabricated_number():
    funnel = m.build_funnel()
    for stage in ("QUERY_PLANNED", "SOURCE_SELECTED", "REQUEST_ATTEMPTED", "RESPONSE_RECEIVED",
                  "EVIDENCE_CONNECTED"):
        s = funnel["stages"][stage]
        assert s["status"] == "UNINSTRUMENTED"
        assert s["count"] is None


def test_admission_passed_is_a_real_logged_count():
    funnel = m.build_funnel()
    s = funnel["stages"]["ADMISSION_PASSED"]
    assert s["status"] == "REAL_COUNT"
    assert s["count"] > 0


def test_source_family_yield_only_reports_instrumented_sources():
    funnel = m.build_funnel()
    assert "src_federal_register" in funnel["source_family_yield"]
    assert "src_crossref" in funnel["source_family_yield"]


def test_real_corpus_runs_without_crash():
    funnel = m.build_funnel()
    assert funnel["total_documents_in_canonical_corpus"] > 500


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
