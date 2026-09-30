import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import fetch_crossref as fcr  # noqa: E402

FIXTURE = PKG_DIR / "fixtures" / "crossref_sample_response.json"


def _fake_fetcher(payload, status="FETCH_OK", status_code=200, ok=True):
    def _fetcher(url):
        return {"ok": ok, "status": status, "status_code": status_code, "data": payload}
    return _fetcher


def test_real_sample_fixture_loads_as_valid_json():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert data["message"]["items"]
    assert len(data["message"]["items"]) == 2


def test_validate_schema_ok_on_real_sample_shape():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    status, reason = fcr.validate_schema(data)
    assert status == "VALIDATION_OK"
    assert reason is None


def test_validate_schema_schema_changed_on_missing_message_key():
    status, reason = fcr.validate_schema({"status": "ok"})
    assert status == "SCHEMA_CHANGED"


def test_validate_schema_schema_changed_on_missing_items_key():
    status, reason = fcr.validate_schema({"message": {"total-results": 0}})
    assert status == "SCHEMA_CHANGED"


def test_validate_schema_not_found_on_empty_items():
    status, reason = fcr.validate_schema({"message": {"items": []}})
    assert status == "NOT_FOUND"


def test_validate_schema_validation_failed_on_missing_required_field():
    bad = {"message": {"items": [{"title": ["x"]}]}}  # missing DOI
    status, reason = fcr.validate_schema(bad)
    assert status == "VALIDATION_FAILED"
    assert "missing fields" in reason


def test_canonicalize_document_produces_link_only_record():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    item = data["message"]["items"][0]
    doc, status = fcr.canonicalize_document(item, "2026-09-30T00:00:00+00:00")
    assert status == "PARSE_OK"
    assert doc["rights_mode"] == "LINK_ONLY"
    assert doc["document_id"] == "crossref_10.1000_example.agents.2026.001"
    assert doc["doi"] == "10.1000/example.agents.2026.001"
    assert doc["authors"] == ["Jane Kim", "Alex Ruiz"]
    assert doc["source_tier"] == "TIER_1"
    assert doc["gap_type_addressed"] == "MISSING_ACADEMIC_EVIDENCE"
    assert doc["published"] == "2026-06-15"
    # abstract is a short excerpt, JATS tags stripped, never full text
    assert doc["abstract_excerpt"] is not None
    assert "<jats:p>" not in doc["abstract_excerpt"]
    assert len(doc["abstract_excerpt"]) <= 500


def test_canonicalize_document_handles_partial_date_parts():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    item = data["message"]["items"][1]  # only [year, month]
    doc, status = fcr.canonicalize_document(item, "2026-09-30T00:00:00+00:00")
    assert status == "PARSE_OK"
    assert doc["published"] == "2026-03-01"
    assert doc["abstract_excerpt"] is None  # no abstract in this item -- never fabricated


def test_canonicalize_document_is_deterministic_idempotent():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    item = data["message"]["items"][0]
    doc1, _ = fcr.canonicalize_document(item, "2026-09-30T00:00:00+00:00")
    doc2, _ = fcr.canonicalize_document(item, "2026-09-30T01:00:00+00:00")
    assert doc1["document_id"] == doc2["document_id"]
    assert doc1["content_hash"] == doc2["content_hash"]


def test_canonicalize_document_parse_failed_when_no_doi():
    doc, status = fcr.canonicalize_document({"title": ["x"]}, "2026-09-30T00:00:00+00:00")
    assert doc is None
    assert status == "PARSE_FAILED"


def test_run_pilot_reaches_success_on_real_sample_shape():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    summary = fcr.run_pilot(fetcher=_fake_fetcher(data))
    assert summary["sources_reaching_success"] == 1
    assert summary["total_documents_canonicalized"] == 2
    result = summary["results"][0]
    assert result["overall_status"] == "SUCCESS"
    assert result["fetch_status"] == "FETCH_OK"
    assert result["schema_status"] == "VALIDATION_OK"
    for doc in result["documents_canonicalized"]:
        assert doc["rights_mode"] == "LINK_ONLY"


def test_run_pilot_fetch_failed_never_becomes_success():
    summary = fcr.run_pilot(fetcher=_fake_fetcher(None, status="FETCH_FAILED", ok=False))
    assert summary["sources_reaching_success"] == 0
    assert summary["results"][0]["overall_status"] == "FETCH_FAILED"
    assert summary["results"][0]["documents_canonicalized"] == []


def test_run_pilot_schema_changed_on_bad_envelope():
    summary = fcr.run_pilot(fetcher=_fake_fetcher({"unexpected": True}))
    assert summary["results"][0]["overall_status"] == "SCHEMA_CHANGED"
    assert summary["sources_reaching_success"] == 0


def test_security_blocks_private_host():
    try:
        fcr.validate_url("http://127.0.0.1/works")
        assert False, "expected BlockedURLError"
    except fcr.BlockedURLError:
        pass


def test_validate_url_rejects_bad_scheme():
    try:
        fcr.validate_url("ftp://api.crossref.org/works")
        assert False, "expected BlockedURLError"
    except fcr.BlockedURLError:
        pass


def test_status_vocabulary_matches_federal_register_convention():
    import fetch_federal_register as frm
    assert fcr.STATUS_VALUES == frm.STATUS_VALUES


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
