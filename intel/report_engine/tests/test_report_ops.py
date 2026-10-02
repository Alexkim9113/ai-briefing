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
    # DYNAMIC CONTRACT (O-1E Part 1, Te spec 43-44): do not hardcode an expected
    # version number here -- the intelligence object legitimately advances over
    # time (v1->v2->v3->v4->...) as real evidence is linked in, which would make
    # a hardcoded "_v3" (or any other fixed literal) go stale again the next time
    # the corpus grows. Instead, independently discover "the latest valid report
    # file on disk for this topic" by globbing the same REPORTS_DIR the code under
    # test reads, parsing out the version integer from each filename, and taking
    # the max. The test then asserts build_or_no_change()'s result matches THAT
    # dynamically-discovered latest version, so it stays correct no matter which
    # version number is current.
    topic_id = "intel_87210a61730c22b9"
    existing = re_.REPORTS_DIR.glob(f"report_{topic_id}_v*.json")
    versions = []
    for p in existing:
        stem = p.stem  # report_intel_..._vN
        suffix = stem.rsplit("_v", 1)[-1]
        if suffix.isdigit():
            versions.append(int(suffix))
    assert versions, "expected at least one existing report file for this topic"
    latest_version = max(versions)
    expected_report_id = f"report_{topic_id}_v{latest_version}"

    result = ro.build_or_no_change(topic_id)
    assert result["status"] == "NO_CHANGE"
    assert result["report_id"] == expected_report_id


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
