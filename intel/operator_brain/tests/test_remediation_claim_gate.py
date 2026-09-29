# SOURCE INTELLIGENCE CORRECTION Phase I — claim_status/confidence를 evidence_sufficiency
# 가 실제로 반영하는지(장식용 metadata가 아니라 기능적 gate인지) 확인.
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import evidence_sufficiency  # noqa: E402


def _result(note_id, confidence, document_id="doc_1"):
    return {"note_id": note_id, "note_type": "FACT", "statement": "s", "concepts": [], "entities": [],
            "provenance": [{"document_id": document_id, "found": True, "canonical_url": f"https://a.com/{document_id}"}],
            "confidence": confidence}


def test_all_weak_confidence_never_reaches_full_hypothesis_sufficiency():
    results = [_result("n1", "SUMMARY_DERIVED", "doc_1"), _result("n2", "SUMMARY_DERIVED", "doc_2")]
    counter = [_result("n3", "SUMMARY_DERIVED", "doc_3")]
    r = evidence_sufficiency.assess(results, "HYPOTHESIS_TEST", counter_evidence_results=counter)
    assert r["state"] != "SUFFICIENT_FOR_HYPOTHESIS_TEST"
    assert r["dimensions"]["source_quality"] == "WEAK"


def test_strong_confidence_can_reach_full_hypothesis_sufficiency():
    results = [_result("n1", "SOURCE_LOCATED", "doc_1"), _result("n2", "SOURCE_VERIFIED", "doc_2")]
    counter = [_result("n3", "SOURCE_LOCATED", "doc_3")]
    r = evidence_sufficiency.assess(results, "HYPOTHESIS_TEST", counter_evidence_results=counter)
    assert r["state"] == "SUFFICIENT_FOR_HYPOTHESIS_TEST"
    assert r["dimensions"]["source_quality"] == "STRONG"


def test_no_confidence_field_is_unknown_not_fabricated():
    results = [{"note_id": "n1", "note_type": "FACT", "statement": "s", "concepts": [], "entities": [],
                "provenance": []}]
    r = evidence_sufficiency.assess(results, "FACT_LOOKUP")
    assert r["dimensions"]["source_quality"] == "UNKNOWN"


def test_mixed_confidence_is_labeled_mixed():
    results = [_result("n1", "SOURCE_LOCATED", "doc_1"), _result("n2", "SUMMARY_DERIVED", "doc_2")]
    r = evidence_sufficiency.assess(results, "HYPOTHESIS_TEST", counter_evidence_results=[_result("n3", "SOURCE_LOCATED", "doc_3")])
    assert r["dimensions"]["source_quality"] == "MIXED"
