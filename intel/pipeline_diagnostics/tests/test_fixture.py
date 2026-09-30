#!/usr/bin/env python3
# PHASE M.1 — pipeline_diagnostics tests. Mix of REAL CORPUS VERIFIED (reads the actual
# intel/*.json files as they exist right now, read-only) and SYNTHETIC checks of pure
# functions. No file under intel/ is ever written by this test.
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import diagnostics as d  # noqa: E402


# --- REAL CORPUS VERIFIED -----------------------------------------------------------------

def test_real_corpus_documents_total_is_569():
    docs = d.load_documents()
    assert len(docs) == 569


def test_real_corpus_ai_copyright_document_is_insufficient_evidence():
    # fcb6426185967686 = "News Outlets Ask Court to Ignore DOJ View in AI Copyright Suit"
    # (src_news_bloomberglaw_com, field="저작권·미디어"). Traced manually: its one claim is
    # claim_status=INSUFFICIENT_SOURCE, and its only event-matching candidate scored
    # LOW_CONFIDENCE with NO_SHARED_ENTITY / NO_SHARED_DISTINCTIVE_TERM - correctly never
    # merged into a production event.
    status = d.document_note_status("fcb6426185967686")
    assert status["has_note"] is False
    assert status["reason_code"] == "INSUFFICIENT_EVIDENCE"
    assert status["claim_statuses"] == ["INSUFFICIENT_SOURCE"]


def test_real_corpus_other_copyright_docs_are_insufficient_evidence():
    for doc_id in ["3e1b942251a7a23c", "61ee6443ac4c8835", "932e8b4711a1c5f3"]:
        status = d.document_note_status(doc_id)
        assert status["has_note"] is False
        assert status["reason_code"] == "INSUFFICIENT_EVIDENCE", (doc_id, status)


def test_real_corpus_nvidia_document_has_note_via_corroborated_event():
    # 003dea2169532db9 = "Nvidia Adds $150 Billion to Massive Stock Buyback..." - this document
    # was corroborated by a second document (57dbd0f7c4aa58cd), source_diversity=2, merged
    # into evtprod_003dea2169532db9 (CONFIRMED). Positive control vs. the copyright docs above.
    status = d.document_note_status("003dea2169532db9")
    # Whether it has a note depends on whether that event's fact/statement was also atomized;
    # what we assert here is the concrete behavioral difference vs. the copyright docs: this
    # document IS referenced by a real production event, so it must never be classified
    # INSUFFICIENT_EVIDENCE/NOT_ELIGIBLE the way the single-source copyright docs are.
    assert status["reason_code"] not in ("INSUFFICIENT_EVIDENCE", "NOT_ELIGIBLE", "PIPELINE_NOT_EXECUTED")


def test_real_corpus_unknown_document_id_is_pipeline_not_executed():
    status = d.document_note_status("does_not_exist_0000")
    assert status["reason_code"] == "PIPELINE_NOT_EXECUTED"


def test_real_corpus_audit_summary_is_internally_consistent():
    summary = d.pipeline_audit_summary()
    assert summary["documents_total"] == 569
    assert summary["documents_with_notes"] <= summary["documents_total"]
    assert summary["documents_with_notes"] + summary["documents_without_notes"] == summary["documents_total"]
    assert summary["changes_total"] >= summary["change_candidates_active"]
    assert isinstance(summary["notes_by_type"], dict)


def test_real_corpus_the_one_change_record_is_reachable_as_rejected():
    changes = d.load_changes()
    assert "chg_7f1ae8e6b9e33860" in changes
    assert changes["chg_7f1ae8e6b9e33860"]["status"] == "REJECTED"


def test_real_corpus_classify_gap_for_copyright_topic_is_corpus_gap():
    result = d.classify_gap(["fcb6426185967686", "3e1b942251a7a23c", "932e8b4711a1c5f3"])
    assert result["gap_class"] == "CORPUS_GAP"


# --- SYNTHETIC (pure function behavior, isolated from real files) -------------------------

def test_synthetic_note_change_status_unknown_note_id():
    status = d.note_change_status("note_does_not_exist")
    assert status["reason_code"] == "UNKNOWN_REASON"
    assert status["has_change"] is False


def test_synthetic_classify_gap_empty_input_is_search_gap():
    result = d.classify_gap([])
    assert result["gap_class"] == "SEARCH_GAP"


def test_synthetic_classify_gap_nonexistent_docs_is_search_gap():
    result = d.classify_gap(["totally_fake_id_1", "totally_fake_id_2"])
    assert result["gap_class"] == "SEARCH_GAP"


def test_synthetic_document_note_status_never_fabricates_has_note_for_missing_document():
    status = d.document_note_status("zzz_not_real")
    assert status["has_note"] is False
