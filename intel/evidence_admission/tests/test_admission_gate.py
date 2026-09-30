#!/usr/bin/env python3
# Run standalone: python3 intel/evidence_admission/tests/test_admission_gate.py
# Covers: valid document admitted, invalid schema rejected, missing provenance rejected,
# publication vs effective date not confused, unknown geography not invented, source
# tier/type preserved, copyright/LINK_ONLY boundary preserved, security/host check.
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import admission_gate as ag  # noqa: E402


def _valid_candidate(**overrides):
    doc = {
        "document_id": "fedreg_2026-19432",
        "content_hash": "abc123",
        "document_type": "POLICY",
        "source_id": "src_federal_register",
        "source_name": "US Federal Register API",
        "source_tier": "TIER_1",
        "source_type": "GOVERNMENT",
        "title": "Request for Comments on Artificial Intelligence Risk Management Framework",
        "abstract_excerpt": "NIST requests comments on updates to the AI RMF.",
        "document_kind": "Notice",
        "citation": "91 FR 61234",
        "agencies": ["National Institute of Standards and Technology"],
        "published": "2026-09-12",
        "canonical_url": "https://www.federalregister.gov/documents/2026/09/12/2026-19432/request-for-comments",
        "rights_mode": "LINK_ONLY",
        "retrieved_at": "2026-09-30T00:00:00+00:00",
        "provenance_id": "prov_fedreg_2026-19432_x",
    }
    doc.update(overrides)
    return doc


def test_valid_document_admitted():
    result = ag.decide_admission(_valid_candidate(), {})
    assert result["admission_status"] == "ELIGIBLE_FOR_ADMISSION", result
    assert result["update_kind"] == "NEW_DOCUMENT"
    assert result["record"]["document_type"] == "POLICY"


def test_invalid_schema_rejected_missing_url():
    result = ag.decide_admission(_valid_candidate(canonical_url=None), {})
    assert result["admission_status"] == "REJECTED_SECURITY", result


def test_invalid_schema_rejected_bad_date():
    result = ag.decide_admission(_valid_candidate(published="not-a-date"), {})
    assert result["admission_status"] == "REJECTED_INVALID_SCHEMA", result


def test_missing_provenance_rejected():
    result = ag.decide_admission(_valid_candidate(provenance_id=None), {})
    assert result["admission_status"] == "REJECTED_PROVENANCE_MISSING", result
    result2 = ag.decide_admission(_valid_candidate(retrieved_at=None), {})
    assert result2["admission_status"] == "REJECTED_PROVENANCE_MISSING", result2


def test_untrusted_source_rejected():
    result = ag.decide_admission(_valid_candidate(source_id="src_random_blog"), {})
    assert result["admission_status"] == "REJECTED_INVALID_SOURCE", result


def test_security_host_mismatch_rejected():
    result = ag.decide_admission(_valid_candidate(canonical_url="https://evil.example.com/doc"), {})
    assert result["admission_status"] == "REJECTED_SECURITY", result


def test_copyright_policy_boundary_preserved():
    result = ag.decide_admission(_valid_candidate(rights_mode="FULL_TEXT_OK"), {})
    assert result["admission_status"] == "REJECTED_COPYRIGHT_POLICY", result
    result2 = ag.decide_admission(_valid_candidate(full_text="the entire article body ..."), {})
    assert result2["admission_status"] == "REJECTED_COPYRIGHT_POLICY", result2


def test_source_tier_and_type_preserved_in_record():
    result = ag.decide_admission(_valid_candidate(), {})
    record = result["record"]
    assert record["government_document_kind"] == "Notice"
    assert record["agencies"] == ["National Institute of Standards and Technology"]
    assert record["citation"] == "91 FR 61234"


def test_geography_evidence_based_not_invented():
    result = ag.decide_admission(_valid_candidate(), {})
    record = result["record"]
    assert record["country"] == "US"
    assert record["jurisdiction"] == "US_FEDERAL"
    # A source not in the trusted registry must never get geography invented for it.
    unknown = ag.build_canonical_record(_valid_candidate(source_id="src_unregistered"), "2026-01-01T00:00:00Z")
    assert unknown["country"] is None
    assert unknown["jurisdiction"] is None


def test_publication_date_not_copied_into_effective_date():
    result = ag.decide_admission(_valid_candidate(), {})
    record = result["record"]
    assert record["published"] == "2026-09-12"
    assert record["effective_date"] is None


def test_link_only_no_full_text_stored():
    result = ag.decide_admission(_valid_candidate(), {})
    record = result["record"]
    assert record["rights_mode"] == "LINK_ONLY"
    assert "full_text" not in record and "body" not in record and "content" not in record
    assert len(record.get("abstract_excerpt") or "") <= 500


def test_entry_level_fetch_failure_never_admitted():
    doc = _valid_candidate()
    doc["_entry_fetch_status"] = "FETCH_FAILED"
    result = ag.decide_admission(doc, {})
    assert result["admission_status"] == "REJECTED_INVALID_SOURCE", result


def test_document_identity_matches_existing_scheme():
    link = "https://www.federalregister.gov/documents/2026/09/12/2026-19432/request-for-comments"
    expected = ag.canonical_document_id(link, "some title")
    # Same computation briefing.py's item_id()/norm_link() would produce: sha1 of the
    # normalized link (utm_ params stripped, trailing slash stripped, host lowercased),
    # truncated to 16 hex chars.
    import hashlib
    import urllib.parse
    u = urllib.parse.urlsplit(link)
    normalized = urllib.parse.urlunsplit((u.scheme, u.netloc.lower(), u.path.rstrip("/"), "", ""))
    assert expected == hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


if __name__ == "__main__":
    ok, failed = 0, 0
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                ok += 1
                print(f"PASS {name}")
            except AssertionError as e:
                failed += 1
                print(f"FAIL {name}: {e}")
    print(f"\n{ok} passed, {failed} failed")
    sys.exit(1 if failed else 0)
