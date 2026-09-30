import json
import sys
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import fetch_transition_evidence_energy as fte  # noqa: E402

FIXTURE = PKG_DIR.parent / "historical_acquisition" / "fixtures" / "federal_register_sample_response.json"


def _fake_fetcher(payload, ok=True, status="FETCH_OK", status_code=200):
    def _fetcher(url):
        return {"ok": ok, "status": status, "status_code": status_code, "data": payload}
    return _fetcher


def test_build_url_uses_transition_window_matching_deep_pilot_cutoffs():
    url = fte.build_transition_fetch_url()
    assert "conditions%5Bpublication_date%5D%5Bgte%5D=2026-01-01" in url
    assert "conditions%5Bpublication_date%5D%5Blte%5D=2026-09-01" in url
    assert fte.TRANSITION_WINDOW_START == "2026-01-01"
    assert fte.TRANSITION_WINDOW_END == "2026-09-01"


def test_build_url_encodes_all_search_terms():
    url = fte.build_transition_fetch_url()
    query = urllib.parse.parse_qs(url.split("?", 1)[1])
    term_value = query["conditions[term]"][0]
    for term in fte.SEARCH_TERMS:
        assert term in term_value


def test_build_url_custom_window_and_terms():
    url = fte.build_transition_fetch_url(window_start="2026-02-01", window_end="2026-03-01",
                                          terms=("solar",))
    assert "2026-02-01" in url
    assert "2026-03-01" in url
    query = urllib.parse.parse_qs(url.split("?", 1)[1])
    assert query["conditions[term]"][0] == "solar"


def test_run_pilot_reuses_base_canonicalization_and_tags_gap_type_and_topic():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    summary = fte.run_pilot(fetcher=_fake_fetcher(data))
    assert summary["gap_type"] == "TRANSITION_GAP"
    assert summary["target_topic"] == "AI_ENERGY_INFRA"
    assert summary["sources_reaching_success"] == 1
    result = summary["results"][0]
    assert result["overall_status"] == "SUCCESS"
    assert result["gap_type"] == "TRANSITION_GAP"
    assert result["target_topic"] == "AI_ENERGY_INFRA"
    for doc in result["documents_canonicalized"]:
        assert doc["gap_type_addressed"] == "TRANSITION_GAP"
        assert doc["rights_mode"] == "LINK_ONLY"
        assert doc["source_id"] == "src_federal_register"


def test_run_pilot_fetch_failed_never_becomes_success():
    def _fetcher(url):
        return {"ok": False, "status": "FETCH_FAILED", "status_code": 500, "error": "boom"}
    summary = fte.run_pilot(fetcher=_fetcher)
    result = summary["results"][0]
    assert result["overall_status"] == "FETCH_FAILED"
    assert summary["sources_reaching_success"] == 0


def test_run_pilot_custom_url_still_reuses_base_pipeline():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    custom_url = "https://www.federalregister.gov/api/v1/documents.json?custom=1"
    summary = fte.run_pilot(fetcher=_fake_fetcher(data), url=custom_url)
    assert summary["sources_reaching_success"] == 1
    assert summary["results"][0]["url"] == custom_url


def test_query_window_metadata_present():
    summary = fte.run_pilot(fetcher=lambda u: {"ok": False, "status": "FETCH_FAILED", "error": "x"})
    assert summary["query_window"]["start"] == fte.TRANSITION_WINDOW_START
    assert summary["query_window"]["end"] == fte.TRANSITION_WINDOW_END
    assert summary["query_window"]["terms"] == list(fte.SEARCH_TERMS)


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
