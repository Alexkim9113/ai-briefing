# PHASE G-K CHECKPOINT REMEDIATION — item 1/3: Source Independence. Te 지시의 5개 케이스
# (A-E)를 실제 provenance trail 모양으로 재현한다.
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import source_independence as si  # noqa: E402


def _trail(document_id, canonical_url, found=True):
    return [{"document_id": document_id, "found": found, "canonical_url": canonical_url,
              "title": None, "source_url": canonical_url, "published_at": None}]


def test_case_a_same_document_is_shared_origin():
    trails = [("note_1", _trail("doc_1", "https://a.com/x")),
              ("note_2", _trail("doc_1", "https://a.com/x"))]
    result = si.assess_independence(trails)
    assert result["overall_status"] == "SHARED_ORIGIN"
    assert result["evidence_family_count"] == 1


def test_case_b_reports_on_linked_documents_are_derived_from_same_source():
    trails = [("note_1", _trail("doc_1", "https://a.com/x")),
              ("note_2", _trail("doc_2", "https://b.com/y"))]
    result = si.assess_independence(trails, reports_on_pairs={frozenset(("doc_1", "doc_2"))})
    assert result["overall_status"] == "DERIVED_FROM_SAME_SOURCE"
    assert result["evidence_family_count"] == 1


def test_case_c_same_domain_different_documents_is_derived_from_same_source():
    trails = [("note_1", _trail("doc_1", "https://reuters.com/x")),
              ("note_2", _trail("doc_2", "https://reuters.com/y"))]
    result = si.assess_independence(trails)
    assert result["overall_status"] == "DERIVED_FROM_SAME_SOURCE"


def test_case_d_different_resolved_domains_is_independent():
    trails = [("note_1", _trail("doc_1", "https://reuters.com/x")),
              ("note_2", _trail("doc_2", "https://apnews.com/y"))]
    result = si.assess_independence(trails)
    assert result["overall_status"] == "INDEPENDENT"
    assert result["evidence_family_count"] == 2


def test_case_e_missing_provenance_is_unknown_never_fabricated():
    trails = [("note_1", [{"document_id": "doc_1", "found": False}]),
              ("note_2", _trail("doc_2", "https://apnews.com/y"))]
    result = si.assess_independence(trails)
    assert result["overall_status"] == "UNKNOWN"
    # 정보가 없다고 INDEPENDENT나 SHARED_ORIGIN을 지어내지 않는다.
    assert "UNKNOWN" in result["pair_statuses"].values()


def test_single_note_independence_is_unknown_not_fabricated():
    result = si.assess_independence([("note_1", _trail("doc_1", "https://a.com/x"))])
    assert result["overall_status"] == "UNKNOWN"


def test_all_statuses_are_from_the_qualitative_vocabulary():
    for status in ("INDEPENDENT", "LIKELY_INDEPENDENT", "SHARED_ORIGIN",
                   "DERIVED_FROM_SAME_SOURCE", "UNKNOWN"):
        assert status in si.INDEPENDENCE_STATUSES
