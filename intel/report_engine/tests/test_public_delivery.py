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
        # O-1D: a detail page is written for EVERY version on disk for each intelligence_id
        # (historical pages stay reachable), not just the latest -- see latest_report_paths().
        assert len(status["pages_written"]) == len(pd.discover_real_reports())
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


def test_report_index_lists_only_latest_version_per_intelligence_id():
    # O-1D fix: public_delivery previously listed every version file as its own Public Index
    # row (discover_real_reports() is append-only across all versions). With v2/v3/v4 now on
    # disk for AI_ENERGY_INFRA, the index must show that topic exactly once, at its highest
    # version, while still leaving the older version files and their detail pages untouched.
    index = pd.build_report_index()
    energy_rows = [e for e in index if e["intelligence_id"] == "intel_87210a61730c22b9"]
    assert len(energy_rows) == 1
    assert energy_rows[0]["version"] == 4
    assert energy_rows[0]["report_id"] == "report_intel_87210a61730c22b9_v4"
    labor_rows = [e for e in index if e["intelligence_id"] == "intel_dbab7b01963396b5"]
    assert len(labor_rows) == 1
    assert labor_rows[0]["version"] == 1


def test_latest_report_paths_picks_highest_version_per_prefix():
    paths = pd.latest_report_paths()
    names = {p.name for p in paths}
    assert "report_intel_87210a61730c22b9_v4.json" in names
    assert "report_intel_87210a61730c22b9_v1.json" not in names
    assert "report_intel_87210a61730c22b9_v2.json" not in names
    assert "report_intel_87210a61730c22b9_v3.json" not in names
    assert "report_intel_dbab7b01963396b5_v1.json" in names


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
