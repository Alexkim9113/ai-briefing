#!/usr/bin/env python3
# PHASE M.5D -- admission-gate coverage for the NEW src_crossref trusted-source row. Reuses
# validate_candidate/decide_admission/admit_shadow_result AS-IS (no forked gate logic) --
# this file only proves the existing gate correctly admits/rejects real-shaped Crossref
# candidates and that the source-type/document-type generalization did not regress the
# Federal Register path (see test_admission_gate.py for that path's own suite).
#
# IMPORTANT: this test NEVER writes to the real intel/documents.json. admit_shadow_result() is
# only ever called here with dry_run=True or with explicit temp-file paths, exactly like
# test_admission_idempotency.py does for its own isolation.
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import admission_gate as ag  # noqa: E402


def _valid_crossref_candidate(**overrides):
    doc = {
        "document_id": "crossref_10.1000_example.agents.2026.001",
        "content_hash": "def456",
        "document_type": "RESEARCH",
        "source_id": "src_crossref",
        "source_name": "Crossref REST API",
        "source_tier": "TIER_1",
        "source_type": "RESEARCH_REPOSITORY",
        "title": "Autonomous AI Agents in Multi-Step Task Execution: A Survey",
        "authors": ["Jane Kim", "Alex Ruiz"],
        "doi": "10.1000/example.agents.2026.001",
        "abstract_excerpt": "We survey recent progress in autonomous AI agents.",
        "journal_or_venue": "Journal of Artificial Intelligence Research",
        "published": "2026-06-15",
        "canonical_url": "https://doi.org/10.1000/example.agents.2026.001",
        "rights_mode": "LINK_ONLY",
        "retrieved_at": "2026-09-30T00:00:00+00:00",
        "provenance_id": "prov_crossref_10.1000_example.agents.2026.001_x",
    }
    doc.update(overrides)
    return doc


def test_valid_crossref_document_admitted():
    result = ag.decide_admission(_valid_crossref_candidate(), {})
    assert result["admission_status"] == "ELIGIBLE_FOR_ADMISSION", result
    assert result["record"]["document_type"] == "RESEARCH"
    assert result["record"]["category"] == "research"
    assert result["record"]["doi"] == "10.1000/example.agents.2026.001"
    assert result["record"]["authors"] == ["Jane Kim", "Alex Ruiz"]


def test_crossref_record_never_stores_full_text():
    result = ag.decide_admission(_valid_crossref_candidate(), {})
    record = result["record"]
    assert record["rights_mode"] == "LINK_ONLY"
    assert "full_text" not in record and "body" not in record and "content" not in record
    assert len(record.get("abstract_excerpt") or "") <= 500


def test_crossref_wrong_url_host_rejected():
    bad = _valid_crossref_candidate(canonical_url="https://not-doi-or-crossref.example.com/x")
    result = ag.decide_admission(bad, {})
    assert result["admission_status"] == "REJECTED_SECURITY", result


def test_crossref_untrusted_source_id_rejected():
    bad = _valid_crossref_candidate(source_id="src_unknown_academic_site")
    result = ag.decide_admission(bad, {})
    assert result["admission_status"] == "REJECTED_INVALID_SOURCE", result


def test_crossref_missing_doi_still_requires_valid_url():
    # A candidate missing canonical_url entirely should fail CANONICAL_URL_VALID, never be
    # silently admitted with an empty link.
    bad = _valid_crossref_candidate(canonical_url=None)
    result = ag.decide_admission(bad, {})
    assert result["admission_status"] == "REJECTED_SECURITY", result


def test_federal_register_path_unregressed_by_document_type_generalization():
    fedreg_doc = {
        "document_id": "fedreg_2026-19432",
        "content_hash": "abc123",
        "document_type": "POLICY",
        "source_id": "src_federal_register",
        "source_name": "US Federal Register API",
        "source_tier": "TIER_1",
        "source_type": "GOVERNMENT",
        "title": "Request for Comments on AI Risk Management Framework",
        "abstract_excerpt": "NIST requests comments.",
        "document_kind": "Notice",
        "citation": "91 FR 61234",
        "agencies": ["NIST"],
        "published": "2026-09-12",
        "canonical_url": "https://www.federalregister.gov/documents/2026/09/12/x",
        "rights_mode": "LINK_ONLY",
        "retrieved_at": "2026-09-30T00:00:00+00:00",
        "provenance_id": "prov_fedreg_x",
    }
    result = ag.decide_admission(fedreg_doc, {})
    assert result["admission_status"] == "ELIGIBLE_FOR_ADMISSION", result
    assert result["record"]["document_type"] == "POLICY"
    assert result["record"]["category"] == "policy"


def test_admit_shadow_result_dry_run_never_writes_real_documents_json():
    """Proves dry_run=True (the ONLY mode this test uses for admission) touches no file at all
    -- this is the discipline the spec requires: never admit fixture/test data into the real
    corpus. Also demonstrates the full pipeline end-to-end for local review."""
    shadow_result = {
        "results": [{
            "fetch_status": "FETCH_OK",
            "schema_status": "VALIDATION_OK",
            "overall_status": "SUCCESS",
            "documents_canonicalized": [_valid_crossref_candidate()],
        }]
    }
    real_docs_path = Path(ag.DOCUMENTS_PATH)
    before = real_docs_path.read_text(encoding="utf-8") if real_docs_path.exists() else None

    with tempfile.TemporaryDirectory() as tmp:
        tmp_docs = Path(tmp) / "documents.json"
        summary = ag.admit_shadow_result(
            shadow_result, documents_path=tmp_docs,
            provenance_path=Path(tmp) / "prov.json",
            audit_log_path=Path(tmp) / "audit.json",
            dry_run=True,
        )
    assert summary["candidates_seen"] == 1
    assert summary["admitted"] == 0  # dry_run: decisions computed, nothing written
    assert summary["decisions"][0]["admission_status"] == "ELIGIBLE_FOR_ADMISSION"

    after = real_docs_path.read_text(encoding="utf-8") if real_docs_path.exists() else None
    assert before == after, "real intel/documents.json must be untouched by this test"


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
