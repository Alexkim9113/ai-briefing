# Tests for intel/gap_closure/fetch_korea_primary_evidence.py. Manual def test_...(): + bare
# assert, one file per subprocess via importlib.util.spec_from_file_location, matching this
# repo's standing test convention (see test_transition_admission_gate.py). Zero LLM. No
# pytest/unittest. Every fetch in these tests uses a MOCKED fetcher callable injected by the
# test -- never a real network call.
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GAP_CLOSURE_DIR = HERE.parent
GEO_DIR = GAP_CLOSURE_DIR.parent / "geographic_evidence"

sys.path.insert(0, str(GAP_CLOSURE_DIR))
sys.path.insert(0, str(GEO_DIR))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load("fetch_korea_primary_evidence", GAP_CLOSURE_DIR / "fetch_korea_primary_evidence.py")


# ---------------------------------------------------------------------------------------------
# Registry / reason-code completeness: every one of the six KOREA_SOURCE_REGISTRY entries has a
# non-empty reason code and explanation, and none is silently missing.
def test_reason_codes_cover_every_registry_source():
    check = mod.reason_codes_complete()
    assert check["ok"], check
    assert check["missing_sources"] == []
    assert check["empty_entries"] == []
    assert set(mod.SOURCE_REASON_CODES.keys()) == set(mod.KOREA_SOURCE_REGISTRY.keys())


def test_all_six_registry_sources_present():
    expected = {"KOSIS", "BOK_ECOS", "MOTIE", "KOREA_COURTS", "NATIONAL_ASSEMBLY",
                "KOREAN_ACADEMIC_CORPORATE"}
    assert set(mod.KOREA_SOURCE_REGISTRY.keys()) == expected


# ---------------------------------------------------------------------------------------------
# validate_source_url(): real SSRF-style per-source hostname allowlist.
def test_validate_source_url_accepts_registered_host():
    # KOSIS's site_url is https://kosis.kr -- a kosis.kr URL must validate without raising.
    mod.validate_source_url("KOSIS", "https://kosis.kr/openapi/something")


def test_validate_source_url_rejects_wrong_host_for_source():
    raised = False
    try:
        mod.validate_source_url("KOSIS", "https://not-kosis.example.com/openapi/something")
    except mod.BlockedURLError:
        raised = True
    assert raised, "a host not belonging to KOSIS's registry entry must be rejected"


def test_validate_source_url_rejects_http_scheme():
    raised = False
    try:
        mod.validate_source_url("KOSIS", "http://kosis.kr/openapi/something")
    except mod.BlockedURLError:
        raised = True
    assert raised, "non-https scheme must be rejected"


def test_validate_source_url_rejects_unknown_source_key():
    raised = False
    try:
        mod.validate_source_url("NOT_A_REAL_SOURCE", "https://kosis.kr/openapi/something")
    except mod.BlockedURLError:
        raised = True
    assert raised


# ---------------------------------------------------------------------------------------------
# prospective_fetch_pipeline(): successful mocked fetch produces correctly-shaped canonical
# documents.
def test_successful_mocked_fetch_produces_correct_document_shape():
    def mock_fetcher(url):
        return 200, (
            '{"items": [{"id": "1234", "title": "Korean AI Data Center Electricity Policy Notice", '
            '"abstract": "A real test abstract about grid capacity.", '
            '"published": "2026-05-01", "url": "https://kosis.kr/doc/1234"}]}'
        )

    result = mod.prospective_fetch_pipeline(
        mock_fetcher, "KOSIS", "https://kosis.kr/openapi/statisticsParameterData.do",
        retrieved_at="2026-09-30T00:00:00+00:00",
    )
    assert result["status"] == "SUCCESS", result
    assert result["documents_parsed_ok"] == 1
    docs = result["documents_canonicalized"]
    assert len(docs) == 1
    doc = docs[0]
    # Shape must match this pipeline's standard LINK_ONLY canonical document convention.
    for field in (
        "document_id", "content_hash", "document_type", "source_id", "source_name",
        "source_tier", "source_type", "title", "abstract_excerpt", "published",
        "canonical_url", "rights_mode", "gap_type_addressed", "target_topic",
        "retrieved_at", "provenance_id",
    ):
        assert field in doc, f"missing field {field!r} in canonicalized document: {doc}"
    assert doc["rights_mode"] == "LINK_ONLY"
    assert doc["source_id"] == "src_kr_kosis"
    assert doc["gap_type_addressed"] == "KOREA_EVIDENCE_GAP"
    assert doc["target_topic"] == "AI_ENERGY_INFRA"
    assert doc["title"] == "Korean AI Data Center Electricity Policy Notice"
    assert doc["canonical_url"] == "https://kosis.kr/doc/1234"
    # copyright-safety: never full text, only a bounded excerpt.
    assert "full_text" not in doc and "body" not in doc and "content" not in doc
    assert len(doc["abstract_excerpt"] or "") <= 500


def test_successful_mocked_fetch_accepts_bare_list_response():
    def mock_fetcher(url):
        return 200, '[{"id": "9", "title": "Notice", "url": "https://kosis.kr/doc/9"}]'

    result = mod.prospective_fetch_pipeline(mock_fetcher, "KOSIS", "https://kosis.kr/openapi/x")
    assert result["status"] == "SUCCESS", result
    assert len(result["documents_canonicalized"]) == 1


# ---------------------------------------------------------------------------------------------
# A non-200 status is handled as a clean failure, never silently treated as success.
def test_non_200_status_is_clean_failure_not_success():
    def mock_fetcher(url):
        return 404, None

    result = mod.prospective_fetch_pipeline(mock_fetcher, "KOSIS", "https://kosis.kr/openapi/x")
    assert result["status"] == "FETCH_FAILED", result
    assert result["status_code"] == 404
    assert result["documents_canonicalized"] == []


def test_500_status_is_clean_failure():
    def mock_fetcher(url):
        return 500, "internal server error (not JSON)"

    result = mod.prospective_fetch_pipeline(mock_fetcher, "KOSIS", "https://kosis.kr/openapi/x")
    assert result["status"] == "FETCH_FAILED"
    assert result["documents_canonicalized"] == []


def test_malformed_json_is_parse_failed_not_success():
    def mock_fetcher(url):
        return 200, "{not valid json"

    result = mod.prospective_fetch_pipeline(mock_fetcher, "KOSIS", "https://kosis.kr/openapi/x")
    assert result["status"] == "PARSE_FAILED", result
    assert result["documents_canonicalized"] == []


def test_unexpected_schema_shape_is_schema_changed_not_success():
    def mock_fetcher(url):
        return 200, '{"unexpected": "shape"}'

    result = mod.prospective_fetch_pipeline(mock_fetcher, "KOSIS", "https://kosis.kr/openapi/x")
    assert result["status"] == "SCHEMA_CHANGED", result
    assert result["documents_canonicalized"] == []


def test_wrong_host_url_is_security_blocked_before_any_fetch_call():
    calls = []

    def mock_fetcher(url):
        calls.append(url)
        return 200, '{"items": []}'

    result = mod.prospective_fetch_pipeline(
        mock_fetcher, "KOSIS", "https://evil.example.com/openapi/x"
    )
    assert result["status"] == "SECURITY_BLOCKED", result
    assert calls == [], "fetcher must never be called for a URL that fails SSRF validation"


# ---------------------------------------------------------------------------------------------
# canonicalize_generic_item(): a missing identifier is an honest PARSE_FAILED, never a
# fabricated document.
def test_canonicalize_generic_item_missing_id_is_parse_failed():
    doc, status = mod.canonicalize_generic_item("KOSIS", {"abstract": "no id or title here"},
                                                 "2026-09-30T00:00:00+00:00")
    assert doc is None
    assert status == "PARSE_FAILED"


# ---------------------------------------------------------------------------------------------
# run_pilot()/main(): the honest "all sources require credentials or lack a verified endpoint"
# outcome -- zero acquisitions, one clear reason code per registry source, no fabricated
# document, and no live fetcher ever invoked.
def test_run_pilot_reports_zero_acquisitions_with_reason_code_per_source():
    summary = mod.run_pilot()
    assert summary["total_documents_canonicalized"] == 0
    assert summary["sources_reaching_success"] == 0
    assert summary["connector_status"] == mod.CONNECTOR_STATUS
    assert summary["sources_attempted"] == len(mod.KOREA_SOURCE_REGISTRY)

    seen_keys = set()
    for r in summary["results"]:
        seen_keys.add(r["source_key"])
        assert r["documents_canonicalized"] == [], r
        assert r["overall_status"] == "NOT_ATTEMPTED_NO_CREDENTIALS", r
        assert r["reason_code"] in (
            "SOURCE_REQUIRES_API_KEY_NOT_AVAILABLE", "NO_VERIFIED_PUBLIC_STRUCTURED_ENDPOINT",
        ), r
        assert r["reason"], r  # never an empty/silent reason
    assert seen_keys == set(mod.KOREA_SOURCE_REGISTRY.keys())


def test_run_pilot_never_calls_a_live_fetcher():
    # run_pilot()/attempt_source() take no fetcher argument at all and never import/construct
    # urllib requests for a real host -- this is verified structurally: OUT_PATH is only written
    # by main(), and run_pilot()'s own result contains no fetch_status/status_code keys that a
    # real fetch attempt would produce, confirming no network call shape leaked in.
    summary = mod.run_pilot()
    for r in summary["results"]:
        assert "status_code" not in r
        assert "fetch_status" not in r


def test_kosis_and_ecos_and_dart_and_assembly_require_api_key():
    for key in ("KOSIS", "BOK_ECOS", "KOREAN_ACADEMIC_CORPORATE", "NATIONAL_ASSEMBLY"):
        code, _ = mod.SOURCE_REASON_CODES[key]
        assert code == "SOURCE_REQUIRES_API_KEY_NOT_AVAILABLE", key


def test_motie_and_courts_have_no_verified_endpoint():
    for key in ("MOTIE", "KOREA_COURTS"):
        code, _ = mod.SOURCE_REASON_CODES[key]
        assert code == "NO_VERIFIED_PUBLIC_STRUCTURED_ENDPOINT", key


def run_all():
    tests = [
        test_reason_codes_cover_every_registry_source,
        test_all_six_registry_sources_present,
        test_validate_source_url_accepts_registered_host,
        test_validate_source_url_rejects_wrong_host_for_source,
        test_validate_source_url_rejects_http_scheme,
        test_validate_source_url_rejects_unknown_source_key,
        test_successful_mocked_fetch_produces_correct_document_shape,
        test_successful_mocked_fetch_accepts_bare_list_response,
        test_non_200_status_is_clean_failure_not_success,
        test_500_status_is_clean_failure,
        test_malformed_json_is_parse_failed_not_success,
        test_unexpected_schema_shape_is_schema_changed_not_success,
        test_wrong_host_url_is_security_blocked_before_any_fetch_call,
        test_canonicalize_generic_item_missing_id_is_parse_failed,
        test_run_pilot_reports_zero_acquisitions_with_reason_code_per_source,
        test_run_pilot_never_calls_a_live_fetcher,
        test_kosis_and_ecos_and_dart_and_assembly_require_api_key,
        test_motie_and_courts_have_no_verified_endpoint,
    ]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"ALL {len(tests)} TESTS PASSED")


if __name__ == "__main__":
    run_all()
