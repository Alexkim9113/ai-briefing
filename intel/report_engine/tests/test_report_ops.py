# N-4B Sections 24-33 -- Report Operations tests: NO_CHANGE idempotency, incremental build
# scoping, and PDF-failure isolation.
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import report_ops as ro  # noqa: E402
import report_engine as re_  # noqa: E402
import pdf_pipeline as pp  # noqa: E402


def test_build_or_no_change_returns_no_change_for_unaltered_corpus():
    result = ro.build_or_no_change("intel_87210a61730c22b9")
    assert result["status"] == "NO_CHANGE"
    assert result["report_id"] == "report_intel_87210a61730c22b9_v1"


def test_build_or_no_change_never_creates_a_file_on_no_change():
    before = set(re_.REPORTS_DIR.glob("report_intel_87210a61730c22b9_v*.json"))
    ro.build_or_no_change("intel_87210a61730c22b9")
    after = set(re_.REPORTS_DIR.glob("report_intel_87210a61730c22b9_v*.json"))
    assert before == after


def test_build_or_no_change_not_found_for_unknown_id():
    result = ro.build_or_no_change("intel_does_not_exist")
    assert result["status"] == "NOT_FOUND"


def test_rebuild_affected_only_touches_matching_topic():
    affected = ro.rebuild_affected("AI_ENERGY_INFRA")
    assert "intel_87210a61730c22b9" in affected
    assert "intel_dbab7b01963396b5" not in affected


def test_rebuild_affected_other_topic_does_not_touch_energy_infra():
    affected = ro.rebuild_affected("AI_LABOR")
    assert "intel_dbab7b01963396b5" in affected
    assert "intel_87210a61730c22b9" not in affected


def test_rebuild_affected_unknown_topic_touches_nothing():
    affected = ro.rebuild_affected("SOME_TOPIC_NOT_IN_CORPUS")
    assert affected == {}


def test_build_artifacts_succeeds_end_to_end_on_real_report():
    r = re_.build_report("intel_87210a61730c22b9")
    docs = re_._load(re_.DOCUMENTS_PATH)
    status = ro.build_artifacts_with_failure_isolation(r, docs, view="PUBLIC")
    assert status["report_json"] == "REPORT_JSON_READY"
    assert status["html"] == "HTML_READY"
    assert status["pdf"] == "PDF_READY"


def test_pdf_failure_never_blocks_report_json_or_html():
    original_chrome = pp.CHROME_BIN
    pp.CHROME_BIN = "/nonexistent/chrome-binary"
    try:
        r = re_.build_report("intel_dbab7b01963396b5")
        docs = re_._load(re_.DOCUMENTS_PATH)
        status = ro.build_artifacts_with_failure_isolation(r, docs, view="PUBLIC")
        assert status["report_json"] == "REPORT_JSON_READY"
        assert status["html"] == "HTML_READY"
        assert status["pdf"] == "PDF_FAILED"
    finally:
        pp.CHROME_BIN = original_chrome


def test_pdf_failure_leaves_no_temp_files_behind():
    original_chrome = pp.CHROME_BIN
    pp.CHROME_BIN = "/nonexistent/chrome-binary"
    try:
        r = re_.build_report("intel_87210a61730c22b9")
        docs = re_._load(re_.DOCUMENTS_PATH)
        ro.build_artifacts_with_failure_isolation(r, docs, view="PUBLIC")
        leftovers = list(re_.REPORTS_DIR.glob("*_tmp_print.html")) + list(re_.REPORTS_DIR.glob("*_tmp.pdf"))
        assert leftovers == []
    finally:
        pp.CHROME_BIN = original_chrome


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
