import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import primary_source_trace as pst  # noqa: E402


def _candidate(doc_id, title, url):
    return {"document_id": doc_id, "title": title, "canonical_url": url,
            "source_id": "src_test", "score": 5}


def test_opaque_google_news_redirect_is_insufficient_evidence():
    docs = {}
    cand = _candidate("c1", "Some AI headline", "https://news.google.com/rss/articles/XYZ?oc=5")
    outcome = pst.trace_candidate(cand, docs)
    assert outcome["status"] == "INSUFFICIENT_EVIDENCE"


def test_direct_news_domain_with_no_match_is_news_only():
    docs = {}
    cand = _candidate("c1", "Completely unrelated tech feature story", "https://techcrunch.com/x")
    outcome = pst.trace_candidate(cand, docs)
    assert outcome["status"] == "NEWS_ONLY"


def test_document_already_on_trusted_domain_is_primary_source_found():
    docs = {}
    cand = _candidate("c1", "AI Risk Management Framework update", "https://www.federalregister.gov/documents/x")
    outcome = pst.trace_candidate(cand, docs)
    assert outcome["status"] == "PRIMARY_SOURCE_FOUND"


def test_corpus_match_on_trusted_domain_is_primary_source_found():
    docs = {
        "other": {"document_id": "other", "title": "Automated Employment Decision Tools Notice of Proposed Rulemaking",
                   "canonical_url": "https://www.federalregister.gov/documents/2026/08/04/x"},
    }
    cand = _candidate("c1", "Automated Employment Decision Tools Notice of Proposed Rulemaking (report)",
                       "https://techcrunch.com/story")
    outcome = pst.trace_candidate(cand, docs)
    assert outcome["status"] == "PRIMARY_SOURCE_FOUND"
    assert outcome["primary_source_document_id"] == "other"


def test_regulator_hint_with_no_corpus_match_is_primary_source_not_found():
    docs = {}
    cand = _candidate("c1", "FTC opens investigation into AI chatbot privacy practices",
                       "https://techcrunch.com/story")
    outcome = pst.trace_candidate(cand, docs)
    assert outcome["status"] == "PRIMARY_SOURCE_NOT_FOUND"


def test_missing_url_is_insufficient_evidence():
    docs = {}
    cand = _candidate("c1", "Some headline", None)
    outcome = pst.trace_candidate(cand, docs)
    assert outcome["status"] == "INSUFFICIENT_EVIDENCE"


def test_run_trace_never_exceeds_limit():
    report = pst.run_trace(limit=3)
    assert report["candidates_traced"] <= 3


def test_run_trace_status_values_are_all_in_required_vocabulary():
    report = pst.run_trace(limit=5)
    for trace in report["traces"].values():
        assert trace["status"] in pst.STATUS_VALUES


def test_run_trace_never_mutates_real_documents_json():
    real_docs_path = Path(__file__).resolve().parents[2] / "documents.json"
    before = real_docs_path.read_text(encoding="utf-8")
    pst.run_trace(limit=5)
    after = real_docs_path.read_text(encoding="utf-8")
    assert before == after


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
