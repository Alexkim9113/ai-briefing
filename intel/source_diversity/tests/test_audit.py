import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import audit  # noqa: E402


def _fixture_documents():
    return {
        "d1": {"document_id": "d1", "document_type": "NEWS", "source_id": "src_reuters",
               "canonical_url": "https://news.google.com/rss/articles/AAA"},
        "d2": {"document_id": "d2", "document_type": "POLICY", "source_id": "src_federal_register",
               "canonical_url": "https://www.federalregister.gov/documents/x",
               "country": "US", "jurisdiction": "US_FEDERAL"},
        "d3": {"document_id": "d3", "document_type": "RESEARCH", "source_id": "src_crossref",
               "canonical_url": "https://doi.org/10.1/abc"},
        "d4": {"document_id": "d4", "document_type": "NEWS", "source_id": "src_example",
               "canonical_url": "https://example.com/story"},
    }


def test_google_news_dependency_real_fraction():
    docs = _fixture_documents()
    r = audit.google_news_dependency(docs)
    assert r["count"] == 1
    assert r["total"] == 4
    assert r["ratio"] == 0.25


def test_direct_primary_source_ratio_uses_admission_gate_trusted_sources():
    docs = _fixture_documents()
    r = audit.direct_primary_source_ratio(docs)
    assert r["count"] == 2  # d2 (src_federal_register) + d3 (src_crossref)
    assert "src_federal_register" in r["trusted_source_ids"]
    assert "src_crossref" in r["trusted_source_ids"]


def test_academic_source_ratio_counts_research_doc_type():
    docs = _fixture_documents()
    r = audit.academic_source_ratio(docs)
    assert r["count"] == 1
    assert r["ratio"] == 0.25


def test_statistical_source_ratio_is_honest_zero_not_forced():
    docs = _fixture_documents()
    r = audit.statistical_source_ratio(docs)
    assert r["count"] == 0
    assert r["ratio"] == 0.0
    assert "note" in r


def test_geographic_distribution_only_uses_explicit_fields_never_infers_from_domain():
    docs = _fixture_documents()
    r = audit.geographic_distribution(docs)
    # d1's canonical_url is a Google News redirect and d4's is example.com -- neither has an
    # explicit country field, so both must be UNKNOWN, never guessed from TLD or language.
    assert r["by_country"]["US"] == 1
    assert r["by_country"]["UNKNOWN"] == 3
    assert r["unknown_country_count"] == 3


def test_source_family_never_exceeds_document_count():
    docs = _fixture_documents()
    result = audit.source_family_document_counts(docs)
    assert result["documents_considered"] == len(docs)
    assert 1 <= result["evidence_family_count"] <= len(docs)
    assert sum(result["family_sizes"]) == len(docs)


def test_ten_documents_same_origin_do_not_produce_ten_independent_families():
    """Failure mode 1 -- a minimal synthetic cluster mirroring the real Google-News-redirect
    shape: 10 documents that all share the exact same canonical_url (the real corpus's actual
    shared-origin signature -- see source_independence.pairwise_status()'s SHARED_ORIGIN check
    on identical canonical_url), so they must all collapse into ONE evidence family, not ten."""
    docs = {
        f"same{i}": {
            "document_id": f"same{i}",
            "document_type": "NEWS",
            "source_id": "src_various_outlets",
            "canonical_url": "https://news.google.com/rss/articles/SHARED_REDIRECT_TARGET",
        }
        for i in range(10)
    }
    result = audit.source_family_document_counts(docs)
    assert result["documents_considered"] == 10
    assert result["evidence_family_count"] == 1
    assert result["largest_family_size"] == 10


def test_unknown_origin_document_never_counted_as_independent_source():
    """Failure mode 2 -- a document with no canonical_url (this audit's UNKNOWN-origin signal)
    must never inflate the family count, and must never be silently merged into another
    document's family either (it gets its own found=False trail, never SHARED_ORIGIN/
    DERIVED_FROM_SAME_SOURCE with anything)."""
    docs = {
        "known_a": {"document_id": "known_a", "canonical_url": "https://a.example.com/1"},
        "known_b": {"document_id": "known_b", "canonical_url": "https://b.example.com/1"},
        "unknown_origin": {"document_id": "unknown_origin", "canonical_url": None},
    }
    result = audit.source_family_document_counts(docs)
    assert result["unresolved_origin_count"] == 1
    # 3 genuinely distinct documents (2 different domains + 1 unresolved) -> 3 families, never
    # merged down to fewer by the unresolved document being wrongly treated as "the same" as
    # either known document.
    assert result["evidence_family_count"] == 3


def test_source_diversity_report_shape_on_fixture():
    docs = _fixture_documents()
    report = audit.source_diversity_report(docs)
    for key in ("total_documents", "google_news_dependency", "direct_primary_source",
                "academic_source", "statistical_source", "geographic_distribution",
                "source_family"):
        assert key in report


def test_source_diversity_report_never_mutates_real_documents_json():
    real_docs_path = Path(__file__).resolve().parents[2] / "documents.json"
    before = real_docs_path.read_text(encoding="utf-8")
    audit.source_diversity_report()
    after = real_docs_path.read_text(encoding="utf-8")
    assert before == after


def test_source_diversity_report_on_real_corpus_has_at_least_597_documents():
    report = audit.source_diversity_report()
    assert report["total_documents"] >= 597
    gn = report["google_news_dependency"]
    assert 0 < gn["count"] <= gn["total"]
    stats = report["statistical_source"]
    assert stats["count"] == 0


def test_report_is_idempotent_on_real_corpus():
    r1 = audit.source_diversity_report()
    r2 = audit.source_diversity_report()
    assert r1 == r2


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
