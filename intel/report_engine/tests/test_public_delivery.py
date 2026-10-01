# N-4B Sections 15-23 -- Public Intelligence Page delivery tests.
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import public_delivery as pd  # noqa: E402

BANNED_SENTENCES = (
    "AI 데이터센터 때문에 미국 전력 위기가 발생했다.",
    "AI가 노동참가율을 감소시켰다.",
)


def test_discover_real_reports_finds_both_real_reports():
    paths = pd.discover_real_reports()
    names = {p.name for p in paths}
    assert "report_intel_87210a61730c22b9_v1.json" in names
    assert "report_intel_dbab7b01963396b5_v1.json" in names


def test_report_index_has_no_full_body_duplication():
    index = pd.build_report_index()
    for entry in index:
        assert "sections" not in entry
        assert "content_blocks" not in json.dumps(entry)


def test_search_filters_by_topic_substring():
    index = pd.build_report_index()
    results = pd.search_report_index(index, query="energy")
    assert all("ENERGY" in r["topic"] for r in results)


def test_search_filters_by_readiness():
    index = pd.build_report_index()
    results = pd.search_report_index(index, readiness="CONDITIONALLY_READY")
    assert all(r["readiness"] == "CONDITIONALLY_READY" for r in results)


def test_build_public_intelligence_pages_writes_real_artifacts_without_errors():
    tmp = HERE.parent / "_test_site_tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        status = pd.build_public_intelligence_pages(tmp)
        assert status["errors"] == []
        assert len(status["pages_written"]) == 2
        assert (tmp / "intelligence" / "index.html").exists()
        for report_id in status["pages_written"]:
            page_html = (tmp / "intelligence" / report_id / "index.html").read_text(encoding="utf-8")
            for sentence in BANNED_SENTENCES:
                assert sentence not in page_html
            assert "claim_ids" not in page_html
            assert "full_text" not in page_html
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_build_public_intelligence_pages_never_raises_on_bad_site_dir():
    # a site_dir that is actually a file (not a directory) should be caught, not raised
    tmp_file = HERE.parent / "_test_site_as_file.tmp"
    tmp_file.write_text("x")
    try:
        status = pd.build_public_intelligence_pages(tmp_file)
        assert status["errors"] != []  # failure recorded, not raised
    finally:
        tmp_file.unlink(missing_ok=True)


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
