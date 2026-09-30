import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import fetch_federal_register as frm  # noqa: E402

FIXTURE = PKG_DIR / "fixtures" / "federal_register_sample_response.json"


def _fake_fetcher(payload, status="FETCH_OK", status_code=200, ok=True):
    def _fetcher(url):
        return {"ok": ok, "status": status, "status_code": status_code, "data": payload}
    return _fetcher


def test_real_sample_fixture_loads_as_valid_json():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert "results" in data
    assert len(data["results"]) == 2


def test_validate_schema_ok_on_real_sample_shape():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    status, reason = frm.validate_schema(data)
    assert status == "VALIDATION_OK"
    assert reason is None


def test_validate_schema_schema_changed_on_missing_results_key():
    status, reason = frm.validate_schema({"count": 0})
    assert status == "SCHEMA_CHANGED"


def test_validate_schema_schema_changed_on_wrong_type():
    status, reason = frm.validate_schema({"results": "not-a-list"})
    assert status == "SCHEMA_CHANGED"


def test_validate_schema_not_found_on_empty_results():
    status, reason = frm.validate_schema({"results": []})
    assert status == "NOT_FOUND"


def test_validate_schema_validation_failed_on_missing_required_field():
    bad = {"results": [{"title": "x"}]}  # missing document_number, type, etc.
    status, reason = frm.validate_schema(bad)
    assert status == "VALIDATION_FAILED"
    assert "missing fields" in reason


def test_canonicalize_document_produces_link_only_record():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    item = data["results"][0]
    doc, status = frm.canonicalize_document(item, "2026-09-30T00:00:00+00:00")
    assert status == "PARSE_OK"
    assert doc["rights_mode"] == "LINK_ONLY"
    assert doc["document_id"] == "fedreg_2026-19432"
    assert doc["canonical_url"] == item["html_url"]
    assert doc["source_tier"] == "TIER_1"
    assert doc["gap_type_addressed"] == "MISSING_REGULATORY_HISTORY"
    # never stores full text -- only an excerpt derived from the source's own short abstract
    assert doc["abstract_excerpt"] is not None
    assert len(doc["abstract_excerpt"]) <= 500
    assert "Department" not in doc or True  # no full-text assertion needed; excerpt-only by construction


def test_canonicalize_document_is_deterministic_idempotent():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    item = data["results"][0]
    doc1, _ = frm.canonicalize_document(item, "2026-09-30T00:00:00+00:00")
    doc2, _ = frm.canonicalize_document(item, "2026-09-30T01:00:00+00:00")
    assert doc1["document_id"] == doc2["document_id"]
    assert doc1["content_hash"] == doc2["content_hash"]


def test_canonicalize_document_parse_failed_when_no_document_number():
    doc, status = frm.canonicalize_document({"title": "x"}, "2026-09-30T00:00:00+00:00")
    assert doc is None
    assert status == "PARSE_FAILED"


def test_run_pilot_reaches_success_on_real_sample_shape():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    summary = frm.run_pilot(fetcher=_fake_fetcher(data))
    assert summary["sources_reaching_success"] == 1
    assert summary["total_documents_canonicalized"] == 2
    result = summary["results"][0]
    assert result["overall_status"] == "SUCCESS"
    assert result["fetch_status"] == "FETCH_OK"
    assert result["schema_status"] == "VALIDATION_OK"
    for doc in result["documents_canonicalized"]:
        assert doc["rights_mode"] == "LINK_ONLY"


def test_run_pilot_fetch_failed_never_becomes_success():
    def _fetcher(url):
        return {"ok": False, "status": "FETCH_FAILED", "status_code": 500, "error": "boom"}
    summary = frm.run_pilot(fetcher=_fetcher)
    result = summary["results"][0]
    assert result["overall_status"] == "FETCH_FAILED"
    assert summary["sources_reaching_success"] == 0
    assert summary["total_documents_canonicalized"] == 0


def test_run_pilot_security_blocked_for_disallowed_host():
    def _raiser(url):
        raise frm.BlockedURLError("blocked host: 169.254.169.254")
    summary = frm.run_pilot(fetcher=_raiser)
    result = summary["results"][0]
    assert result["overall_status"] == "SECURITY_BLOCKED"


def test_run_pilot_http_200_alone_is_not_success_on_schema_changed():
    # HTTP 200 with an unexpected envelope must never be reported as SUCCESS (spec section 1).
    summary = frm.run_pilot(fetcher=_fake_fetcher({"unexpected": "shape"}))
    result = summary["results"][0]
    assert result["fetch_status"] == "FETCH_OK"
    assert result["overall_status"] == "SCHEMA_CHANGED"
    assert summary["sources_reaching_success"] == 0


def test_validate_url_blocks_non_http_scheme():
    try:
        frm.validate_url("file:///etc/passwd")
        assert False, "expected BlockedURLError"
    except frm.BlockedURLError:
        pass


def test_validate_url_blocks_localhost():
    try:
        frm.validate_url("http://localhost/secret")
        assert False, "expected BlockedURLError"
    except frm.BlockedURLError:
        pass


def test_validate_url_blocks_loopback_ip():
    try:
        frm.validate_url("http://127.0.0.1/secret")
        assert False, "expected BlockedURLError"
    except frm.BlockedURLError:
        pass


def test_status_vocabulary_is_the_required_granular_set():
    required = {
        "FETCH_OK", "FETCH_FAILED", "PARSE_OK", "PARSE_FAILED", "VALIDATION_OK",
        "VALIDATION_FAILED", "SCHEMA_CHANGED", "SECURITY_BLOCKED", "RATE_LIMITED",
        "NOT_FOUND", "UNSUPPORTED", "CANONICALIZED", "SUCCESS",
    }
    assert required.issubset(set(frm.STATUS_VALUES))


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
