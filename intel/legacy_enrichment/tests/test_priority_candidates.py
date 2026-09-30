import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import priority_candidates as pc  # noqa: E402


def _fixture_documents():
    return {
        "d1": {"document_id": "d1", "document_type": "NEWS", "field": None,
               "title": "Nvidia launches new safety program after AI regulation uproar"},
        "d2": {"document_id": "d2", "document_type": "NEWS", "field": None,
               "title": "Nvidia launches new safety program after AI regulation backlash"},
        "d3": {"document_id": "d3", "document_type": "POLICY", "field": None,
               "title": "Request for Comments on Artificial Intelligence Risk Management"},
        "d4": {"document_id": "d4", "document_type": "NEWS", "field": "사회·노동",
               "title": "Local bakery announces new bread flavor"},
        "d5": {"document_id": "d5", "document_type": "NEWS", "field": None,
               "title": "Completely unrelated headline about weather patterns today"},
    }


def test_keyword_hits_uses_word_boundaries_not_substring():
    # "sues" must not match inside "issues"
    hits = pc._keyword_hits("apple issues a statement", ("sue", "sues"))
    assert hits == []
    hits2 = pc._keyword_hits("apple sues rival company", ("sue", "sues"))
    assert "sues" in hits2


def test_build_title_clusters_groups_near_duplicate_titles():
    docs = _fixture_documents()
    clusters = pc.build_title_clusters(docs)
    assert clusters.get("d1") == 2
    assert clusters.get("d2") == 2
    assert "d3" not in clusters  # unique title, no cluster
    assert "d5" not in clusters


def test_score_document_policy_gets_regulatory_points():
    docs = _fixture_documents()
    score, reasons = pc.score_document(docs["d3"], cluster_size=1)
    assert score >= 4
    assert any("POLICY_REGULATORY" in r for r in reasons)


def test_score_document_labor_field_scores_even_without_keyword():
    docs = _fixture_documents()
    score, reasons = pc.score_document(docs["d4"], cluster_size=1)
    assert score >= 3
    assert any("LABOR_MARKET_SHIFT" in r for r in reasons)


def test_score_document_zero_for_unrelated_headline():
    docs = _fixture_documents()
    score, reasons = pc.score_document(docs["d5"], cluster_size=1)
    assert score == 0
    assert reasons == []


def test_audit_corpus_never_returns_more_than_top_n():
    docs = _fixture_documents()
    report = pc.audit_corpus(docs, top_n=2)
    assert report["candidates_returned"] <= 2
    assert report["documents_examined"] == len(docs)


def test_audit_corpus_sorted_by_score_descending():
    docs = _fixture_documents()
    report = pc.audit_corpus(docs, top_n=10)
    scores = [c["score"] for c in report["candidates"]]
    assert scores == sorted(scores, reverse=True)


def test_audit_corpus_never_mutates_real_documents_json():
    real_docs_path = Path(__file__).resolve().parents[2] / "documents.json"
    before = real_docs_path.read_text(encoding="utf-8")
    pc.audit_corpus()
    after = real_docs_path.read_text(encoding="utf-8")
    assert before == after


def test_audit_corpus_on_real_corpus_returns_at_most_20_candidates():
    report = pc.audit_corpus()
    assert report["documents_examined"] >= 577
    assert report["candidates_returned"] <= 20
    assert all(c["score"] > 0 for c in report["candidates"])


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
