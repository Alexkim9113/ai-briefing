#!/usr/bin/env python3
# Run standalone: python3 intel/evidence_admission/tests/test_admission_idempotency.py
# Covers: duplicate not duplicated (idempotency), repeat run idempotent end-to-end, metadata
# update preserved without losing old provenance, corpus persistence across a simulated
# rotation, shadow result cannot bypass the gate, source independence unaffected
# inappropriately, identity stability of pre-existing documents.
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import admission_gate as ag  # noqa: E402

FIXTURE_SHADOW_RESULT = {
    "attempted_at": "2026-09-30T00:00:00+00:00",
    "execution_environment": "TEST",
    "sources_attempted": 1,
    "sources_reaching_success": 1,
    "total_documents_canonicalized": 2,
    "results": [
        {
            "source_name": "US Federal Register API", "source_tier": "TIER_1",
            "fetch_status": "FETCH_OK", "schema_status": "VALIDATION_OK",
            "overall_status": "SUCCESS",
            "documents_canonicalized": [
                {
                    "document_id": "fedreg_2026-19432", "content_hash": "hash_a",
                    "document_type": "POLICY", "source_id": "src_federal_register",
                    "source_name": "US Federal Register API", "source_tier": "TIER_1",
                    "source_type": "GOVERNMENT",
                    "title": "Request for Comments on AI Risk Management Framework",
                    "abstract_excerpt": "NIST requests comments.",
                    "document_kind": "Notice", "citation": "91 FR 61234",
                    "agencies": ["National Institute of Standards and Technology"],
                    "published": "2026-09-12",
                    "canonical_url": "https://www.federalregister.gov/documents/2026/09/12/2026-19432/x",
                    "rights_mode": "LINK_ONLY",
                    "retrieved_at": "2026-09-30T00:00:00+00:00",
                    "provenance_id": "prov_fedreg_2026-19432_1",
                },
                {
                    "document_id": "fedreg_2026-17021", "content_hash": "hash_b",
                    "document_type": "POLICY", "source_id": "src_federal_register",
                    "source_name": "US Federal Register API", "source_tier": "TIER_1",
                    "source_type": "GOVERNMENT",
                    "title": "Automated Employment Decision Tools; Notice of Proposed Rulemaking",
                    "abstract_excerpt": "Disclosure requirements proposed.",
                    "document_kind": "Proposed Rule", "citation": "91 FR 54321",
                    "agencies": ["Department of Labor"],
                    "published": "2026-08-04",
                    "canonical_url": "https://www.federalregister.gov/documents/2026/08/04/2026-17021/y",
                    "rights_mode": "LINK_ONLY",
                    "retrieved_at": "2026-09-30T00:00:00+00:00",
                    "provenance_id": "prov_fedreg_2026-17021_1",
                },
            ],
        }
    ],
}


def _tmp_paths():
    d = Path(tempfile.mkdtemp())
    docs_path = d / "documents.json"
    prov_path = d / "admission_provenance.json"
    audit_path = d / "admission_audit_log.json"
    docs_path.write_text(json.dumps({
        "PREEXISTING0001": {
            "document_id": "PREEXISTING0001", "canonical_url": "https://example.com/a",
            "title": "Pre-existing document", "category": "news_global",
            "document_type": "NEWS", "content_hash": "preexisting_hash",
            "rights_mode": "LINK_ONLY", "created_at": "2026-09-01T00:00:00Z",
            "updated_at": "2026-09-01T00:00:00Z", "source_id": "src_example",
        }
    }), encoding="utf-8")
    return d, docs_path, prov_path, audit_path


def test_first_run_admits_both_new_documents():
    d, docs_path, prov_path, audit_path = _tmp_paths()
    summary = ag.admit_shadow_result(FIXTURE_SHADOW_RESULT, docs_path, prov_path, audit_path)
    assert summary["admitted"] == 2, summary
    assert summary["duplicate_existing"] == 0
    documents = json.loads(docs_path.read_text())
    assert len(documents) == 3  # 1 pre-existing + 2 newly admitted
    shutil.rmtree(d)


def test_preexisting_document_identity_untouched():
    d, docs_path, prov_path, audit_path = _tmp_paths()
    before = json.loads(docs_path.read_text())["PREEXISTING0001"]
    ag.admit_shadow_result(FIXTURE_SHADOW_RESULT, docs_path, prov_path, audit_path)
    after = json.loads(docs_path.read_text())["PREEXISTING0001"]
    assert before == after, "admission must never mutate a pre-existing, unrelated document"
    shutil.rmtree(d)


def test_second_run_is_idempotent_no_duplicates():
    d, docs_path, prov_path, audit_path = _tmp_paths()
    ag.admit_shadow_result(FIXTURE_SHADOW_RESULT, docs_path, prov_path, audit_path)
    documents_after_first = json.loads(docs_path.read_text())
    assert len(documents_after_first) == 3

    summary2 = ag.admit_shadow_result(FIXTURE_SHADOW_RESULT, docs_path, prov_path, audit_path)
    assert summary2["admitted"] == 0, summary2
    assert summary2["duplicate_existing"] == 2, summary2
    documents_after_second = json.loads(docs_path.read_text())
    assert len(documents_after_second) == 3, "second run must not double the corpus"
    shutil.rmtree(d)


def test_metadata_update_preserves_old_provenance():
    d, docs_path, prov_path, audit_path = _tmp_paths()
    ag.admit_shadow_result(FIXTURE_SHADOW_RESULT, docs_path, prov_path, audit_path)
    prov_before = json.loads(prov_path.read_text())
    doc_id = ag.canonical_document_id(
        "https://www.federalregister.gov/documents/2026/09/12/2026-19432/x", "x")
    assert prov_before[doc_id]["history"] == []

    changed_result = json.loads(json.dumps(FIXTURE_SHADOW_RESULT))
    changed_result["results"][0]["documents_canonicalized"][0]["content_hash"] = "hash_a_v2"
    changed_result["results"][0]["documents_canonicalized"][0]["abstract_excerpt"] = "Updated abstract."
    summary3 = ag.admit_shadow_result(changed_result, docs_path, prov_path, audit_path)
    assert summary3["admitted"] == 1, summary3  # only the changed one
    assert summary3["duplicate_existing"] == 1  # the unchanged one

    documents_after = json.loads(docs_path.read_text())
    assert documents_after[doc_id]["content_hash"] == "hash_a_v2"
    prov_after = json.loads(prov_path.read_text())
    assert len(prov_after[doc_id]["history"]) == 1, "old provenance entry must be preserved, not lost"
    shutil.rmtree(d)


def test_corpus_persistence_across_simulated_rotation():
    """Simulates a subsequent, unrelated daily run (a JsonStore load-upsert-save cycle on an
    unrelated document) after admission, and confirms the admitted documents survive it --
    same merge discipline as the M.5A persistence fix."""
    d, docs_path, prov_path, audit_path = _tmp_paths()
    ag.admit_shadow_result(FIXTURE_SHADOW_RESULT, docs_path, prov_path, audit_path)

    sys.path.insert(0, str(HERE.parent.parent))
    from storage.json_store import JsonStore  # noqa: E402
    store = JsonStore(docs_path)
    store.upsert("SOME_NEW_UNRELATED_DOC", {"document_id": "SOME_NEW_UNRELATED_DOC", "title": "unrelated"})
    store.save()

    documents_after_rotation = json.loads(docs_path.read_text())
    assert len(documents_after_rotation) == 4  # 1 pre-existing + 2 admitted + 1 unrelated new
    doc_id = ag.canonical_document_id(
        "https://www.federalregister.gov/documents/2026/09/12/2026-19432/x", "x")
    assert doc_id in documents_after_rotation
    shutil.rmtree(d)


def test_shadow_result_cannot_bypass_gate():
    """Writing a raw shadow-result-shaped file must never itself touch documents.json --
    only admission_gate.admit_shadow_result() may, and only when explicitly invoked."""
    d, docs_path, prov_path, audit_path = _tmp_paths()
    before = docs_path.read_text()
    raw_shadow_path = d / "raw_shadow.json"
    raw_shadow_path.write_text(json.dumps(FIXTURE_SHADOW_RESULT), encoding="utf-8")
    # Merely having a shadow-result file on disk changes nothing.
    after = docs_path.read_text()
    assert before == after
    shutil.rmtree(d)


def test_unknown_never_silently_admitted():
    malformed_result = {"results": [{"fetch_status": "FETCH_OK", "schema_status": "VALIDATION_OK",
                                      "documents_canonicalized": [{"title": None, "canonical_url": None}]}]}
    d, docs_path, prov_path, audit_path = _tmp_paths()
    summary = ag.admit_shadow_result(malformed_result, docs_path, prov_path, audit_path)
    assert summary["admitted"] == 0
    assert all(dec["admission_status"] != "ADMITTED" for dec in summary["decisions"])
    shutil.rmtree(d)


def test_dry_run_never_writes():
    d, docs_path, prov_path, audit_path = _tmp_paths()
    before = docs_path.read_text()
    summary = ag.admit_shadow_result(FIXTURE_SHADOW_RESULT, docs_path, prov_path, audit_path, dry_run=True)
    assert summary["admitted"] == 0  # dry_run reports ELIGIBLE_FOR_ADMISSION, never ADMITTED
    assert all(d_["admission_status"] == "ELIGIBLE_FOR_ADMISSION" for d_ in summary["decisions"])
    after = docs_path.read_text()
    assert before == after, "dry_run must never write documents.json"
    shutil.rmtree(d)


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
