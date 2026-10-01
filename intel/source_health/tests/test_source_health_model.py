# N-5 Section 20-29 -- Source Health tests. This sandbox's egress policy blocks essentially all
# external hosts (confirmed in prior-phase memory and re-confirmed live here), so every real check
# is expected to come back BLOCKED -- these tests assert the MODEL behaves honestly under that
# real condition, not that it magically reaches the network.
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import source_health_model as sh  # noqa: E402


def test_check_one_source_never_raises_on_network_failure():
    candidate = {"source_id": "src_test_unreachable", "name": "test",
                "url": "https://this-domain-should-not-resolve.invalid", "origin": "test"}
    result = sh.check_one_source(candidate, timeout_seconds=2, max_retries=1)
    assert result["status"] in sh.SOURCE_HEALTH_STATES
    assert result["last_success"] is False


def test_check_one_source_never_claims_healthy_on_failure():
    candidate = {"source_id": "src_test_unreachable", "name": "test",
                "url": "https://this-domain-should-not-resolve.invalid", "origin": "test"}
    result = sh.check_one_source(candidate, timeout_seconds=2, max_retries=1)
    assert result["status"] != "HEALTHY"


def test_check_one_source_bounded_retries_never_infinite():
    candidate = {"source_id": "src_test_unreachable", "name": "test",
                "url": "https://this-domain-should-not-resolve.invalid", "origin": "test"}
    start = time.time()
    sh.check_one_source(candidate, timeout_seconds=2, max_retries=2)
    elapsed = time.time() - start
    assert elapsed < 30  # bounded -- not an infinite retry loop


def test_run_tier1_pilot_checks_every_candidate_honestly():
    result = sh.run_tier1_pilot()
    ids_checked = {r["source_id"] for r in result["results"]}
    expected = {c["source_id"] for c in sh.TIER1_CANDIDATES}
    assert ids_checked == expected
    for r in result["results"]:
        assert r["status"] in sh.SOURCE_HEALTH_STATES


def test_mark_stale_flags_old_timestamp():
    import datetime
    old = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=2)).isoformat()
    records = [{"source_id": "x", "last_checked": old, "status": "HEALTHY"}]
    out = sh.mark_stale(records)
    assert out[0]["is_stale"] is True
    assert out[0]["status"] == "HEALTHY"  # staleness is separate from status, never overwrites it


def test_mark_stale_leaves_recent_timestamp_fresh():
    import datetime
    recent = datetime.datetime.now(datetime.timezone.utc).isoformat()
    records = [{"source_id": "x", "last_checked": recent, "status": "HEALTHY"}]
    out = sh.mark_stale(records)
    assert out[0]["is_stale"] is False


def test_mark_stale_handles_missing_timestamp_honestly():
    records = [{"source_id": "x", "status": "UNKNOWN"}]
    out = sh.mark_stale(records)
    assert out[0]["is_stale"] is True


def test_save_and_load_result_roundtrip():
    original_path = sh.RESULT_PATH
    tmp_path = sh.HERE / "_test_result_tmp.json"
    sh.RESULT_PATH = tmp_path
    try:
        result = {"checked_at": "2026-01-01T00:00:00+00:00", "results": []}
        sh.save_result(result)
        loaded = sh.load_result()
        assert loaded == result
    finally:
        sh.RESULT_PATH = original_path
        tmp_path.unlink(missing_ok=True)


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
