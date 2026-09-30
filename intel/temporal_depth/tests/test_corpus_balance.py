import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import corpus_balance as cb  # noqa: E402


def _fixture_documents():
    return {
        "d1": {"document_id": "d1", "document_type": "NEWS", "category": "news_ko",
               "field": "에이전트", "published": "2026-09-29T00:00:00+00:00",
               "canonical_url": "https://a.example.com/1"},
        "d2": {"document_id": "d2", "document_type": "POLICY", "category": "policy",
               "field": None, "published": "2026-08-15T00:00:00+00:00",
               "canonical_url": "https://federalregister.gov/x"},
        "d3": {"document_id": "d3", "document_type": "RESEARCH", "category": "papers",
               "field": "AI 일반", "published": "2020-01-01T00:00:00+00:00",
               "canonical_url": "https://arxiv.org/abs/1"},
        "d4": {"document_id": "d4", "document_type": "NEWS", "category": "news_global",
               "field": None, "published": None,
               "canonical_url": "https://b.example.com/1"},
    }


def test_temporal_bucket_classifies_relative_to_as_of():
    as_of = date(2026, 9, 30)
    assert cb.temporal_bucket("2026-09-29", as_of) == "CURRENT"
    assert cb.temporal_bucket("2026-08-01", as_of) == "SHORT_TERM"
    assert cb.temporal_bucket("2026-01-01", as_of) == "MEDIUM_TERM"
    assert cb.temporal_bucket("2023-01-01", as_of) == "LONG_TERM"
    assert cb.temporal_bucket("2010-01-01", as_of) == "HISTORICAL"
    assert cb.temporal_bucket(None, as_of) == "UNKNOWN"
    assert cb.temporal_bucket("not-a-date", as_of) == "UNKNOWN"


def test_temporal_bucket_never_guesses_a_future_date_into_a_bucket():
    as_of = date(2026, 9, 30)
    assert cb.temporal_bucket("2027-01-01", as_of) == "UNKNOWN"


def test_source_type_distribution_real_counts():
    docs = _fixture_documents()
    dist = cb.source_type_distribution(docs)
    assert dist == {"NEWS": 2, "POLICY": 1, "RESEARCH": 1}


def test_source_tier_distribution_maps_known_document_types():
    docs = _fixture_documents()
    dist = cb.source_tier_distribution(docs)
    assert dist["TIER_1_OFFICIAL"] == 1
    assert dist["TIER_1_ACADEMIC"] == 1
    assert dist["TIER_2_SECONDARY"] == 2


def test_domain_distribution_reports_category_and_field_without_hiding_unknowns():
    docs = _fixture_documents()
    dist = cb.domain_distribution(docs)
    assert dist["by_category"]["news_ko"] == 1
    assert dist["field_unknown_count"] == 2  # d2 (None) and d4 (None)


def test_temporal_bucket_distribution_covers_all_fixture_docs():
    docs = _fixture_documents()
    as_of = date(2026, 9, 30)
    dist = cb.temporal_bucket_distribution(docs, as_of)
    assert dist["CURRENT"] == 1
    assert dist["SHORT_TERM"] == 1
    assert dist["HISTORICAL"] == 1
    assert dist["UNKNOWN"] == 1
    assert sum(dist.values()) == len(docs)


def test_independent_source_family_count_never_exceeds_document_count():
    docs = _fixture_documents()
    result = cb.independent_source_family_count(docs)
    assert result["documents_considered"] == len(docs)
    assert 1 <= result["evidence_family_count"] <= len(docs)


def test_independent_source_family_count_single_document_is_trivial():
    docs = {"only": {"document_id": "only", "canonical_url": "https://a.example.com/x"}}
    result = cb.independent_source_family_count(docs)
    assert result["evidence_family_count"] == 1
    assert result["documents_considered"] == 1


def test_corpus_balance_report_shape_on_fixture():
    docs = _fixture_documents()
    report = cb.corpus_balance_report(docs, as_of=date(2026, 9, 30), independence_sample_limit=None)
    assert report["total_documents"] == 4
    assert "source_type_distribution" in report
    assert "source_tier_distribution" in report
    assert "domain_distribution" in report
    assert "temporal_bucket_distribution" in report
    assert "independent_source_family" in report


def test_corpus_balance_report_never_mutates_real_documents_json():
    real_docs_path = Path(__file__).resolve().parents[2] / "documents.json"
    before = real_docs_path.read_text(encoding="utf-8")
    cb.corpus_balance_report()
    after = real_docs_path.read_text(encoding="utf-8")
    assert before == after


def test_corpus_balance_report_on_real_corpus_has_at_least_577_documents():
    report = cb.corpus_balance_report()
    assert report["total_documents"] >= 577
    assert sum(report["temporal_bucket_distribution"].values()) == report["total_documents"]
    assert report["independent_source_family"]["evidence_family_count"] >= 1
    assert report["independent_source_family"]["evidence_family_count"] <= report["total_documents"]


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
