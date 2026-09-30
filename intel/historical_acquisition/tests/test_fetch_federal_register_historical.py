import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import fetch_federal_register_historical as frh  # noqa: E402

FIXTURE = PKG_DIR / "fixtures" / "federal_register_sample_response.json"


def _fake_fetcher(payload, status="FETCH_OK", status_code=200, ok=True):
    def _fetcher(url):
        return {"ok": ok, "status": status, "status_code": status_code, "data": payload}
    return _fetcher


def test_build_url_uses_date_range_params_not_bare_newest():
    url, start, end = frh.build_historical_fetch_url(window_days=365, offset_days=30,
                                                       as_of=date(2026, 9, 30))
    assert "conditions%5Bpublication_date%5D%5Bgte%5D=" in url
    assert "conditions%5Bpublication_date%5D%5Blte%5D=" in url
    assert "order=oldest" in url
    assert start < end
    assert end == "2026-08-31"


def test_build_url_window_is_older_than_current_8_day_corpus_span():
    # The real corpus span is 2026-09-22 to 2026-09-30 (8 days). A useful historical window
    # must end before that span starts, or it cannot possibly extend it.
    url, start, end = frh.build_historical_fetch_url(as_of=date(2026, 9, 30))
    assert end < "2026-09-22"


def test_run_pilot_reuses_base_canonicalization_and_tags_gap_type():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    summary = frh.run_pilot(fetcher=_fake_fetcher(data), as_of=date(2026, 9, 30))
    assert summary["gap_type"] == "INSUFFICIENT_TIME_DEPTH"
    assert summary["sources_reaching_success"] == 1
    result = summary["results"][0]
    assert result["overall_status"] == "SUCCESS"
    assert result["gap_type"] == "INSUFFICIENT_TIME_DEPTH"
    for doc in result["documents_canonicalized"]:
        assert doc["gap_type_addressed"] == "INSUFFICIENT_TIME_DEPTH"
        assert doc["rights_mode"] == "LINK_ONLY"
        assert doc["source_id"] == "src_federal_register"  # unchanged -- same trusted source row


def test_run_pilot_fetch_failed_never_becomes_success():
    def _fetcher(url):
        return {"ok": False, "status": "FETCH_FAILED", "status_code": 500, "error": "boom"}
    summary = frh.run_pilot(fetcher=_fetcher, as_of=date(2026, 9, 30))
    result = summary["results"][0]
    assert result["overall_status"] == "FETCH_FAILED"
    assert summary["sources_reaching_success"] == 0


def test_run_pilot_custom_url_still_reuses_base_pipeline():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    summary = frh.run_pilot(fetcher=_fake_fetcher(data), url="https://www.federalregister.gov/api/v1/documents.json?custom=1")
    assert summary["sources_reaching_success"] == 1
    assert summary["results"][0]["url"] == "https://www.federalregister.gov/api/v1/documents.json?custom=1"


def test_query_window_metadata_present_and_ordered():
    url, start, end = frh.build_historical_fetch_url(as_of=date(2026, 9, 30))
    summary = frh.run_pilot(fetcher=lambda u: {"ok": False, "status": "FETCH_FAILED", "error": "x"},
                             as_of=date(2026, 9, 30))
    assert summary["query_window"]["start"] == start
    assert summary["query_window"]["end"] == end
    assert summary["query_window"]["start"] < summary["query_window"]["end"]


def main():
    tests = [v for k, v in globals().items() if k.startswith("test_")]
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
