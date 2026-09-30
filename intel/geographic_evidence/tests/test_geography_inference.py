import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent

sys.path.insert(0, str(PKG_DIR))
import geography_inference as gi  # noqa: E402


def _fixture_documents():
    return {
        # TLD signal: Korean ccTLD -> should be classified KR.
        "kr_tld": {
            "document_id": "kr_tld", "source_id": "src_some_kr_outlet_not_in_registry",
            "canonical_url": "https://www.example.co.kr/article/1",
            "title": "무제",
        },
        # TLD signal: US .gov -> should be classified US/US_FEDERAL (even without a registry hit).
        "us_gov_tld": {
            "document_id": "us_gov_tld", "source_id": "src_some_agency",
            "canonical_url": "https://www.someagency.gov/notice/1",
            "title": "Notice",
        },
        # source_id registry signal: Yonhap, masked behind a Google News redirect (no TLD signal
        # available from canonical_url) -- must still resolve via the registry.
        "kr_registry": {
            "document_id": "kr_registry", "source_id": "src_yna_co_kr",
            "canonical_url": "https://news.google.com/rss/articles/XYZ",
            "title": "some Yonhap story",
        },
        # already resolved by admission_gate (country already set) -- must be LEFT ALONE, never
        # re-touched by this module, even though its own source_id isn't in our registry.
        "already_known": {
            "document_id": "already_known", "source_id": "src_federal_register",
            "canonical_url": "https://www.federalregister.gov/documents/x",
            "country": "US", "jurisdiction": "US_FEDERAL",
        },
        # arXiv source_id containing Korean-script CATEGORY LABEL text -- must stay UNKNOWN. This
        # is the "don't over-infer" negative case: a naive Hangul-substring check would wrongly
        # classify this as Korean.
        "arxiv_should_stay_unknown": {
            "document_id": "arxiv_should_stay_unknown",
            "source_id": "src_arxiv_eess_sy_에너지_환경",
            "canonical_url": "https://arxiv.org/abs/2609.30460",
            "title": "A paper about power systems",
        },
        # a plain .com news article mentioning "China" in the title -- must stay UNKNOWN: the
        # SUBJECT of an article is never evidence of the document's own origin.
        "mentions_country_should_stay_unknown": {
            "document_id": "mentions_country_should_stay_unknown",
            "source_id": "src_example_outlet",
            "canonical_url": "https://www.example.com/china-ai-policy",
            "title": "How China is regulating AI",
        },
        # aggregator source_id explicitly excluded from the registry -- must stay UNKNOWN even
        # though its title has Hangul.
        "aggregator_should_stay_unknown": {
            "document_id": "aggregator_should_stay_unknown",
            "source_id": "src_구글뉴스_ai_정책",
            "canonical_url": "https://news.google.com/rss/articles/ABC",
            "title": "한국 AI 정책",
        },
    }


def test_tld_rule_classifies_kr_ccTLD():
    doc = _fixture_documents()["kr_tld"]
    result = gi.infer_document_geography(doc)
    assert result is not None
    assert result["country"] == "KR"
    assert result["signal"] == "TLD"


def test_tld_rule_classifies_us_gov():
    doc = _fixture_documents()["us_gov_tld"]
    result = gi.infer_document_geography(doc)
    assert result is not None
    assert result["country"] == "US"
    assert result["jurisdiction"] == "US_FEDERAL"


def test_source_id_registry_resolves_behind_aggregator_redirect():
    doc = _fixture_documents()["kr_registry"]
    result = gi.infer_document_geography(doc)
    assert result is not None
    assert result["country"] == "KR"
    assert result["signal"] == "SOURCE_ID_REGISTRY"


def test_arxiv_source_never_inferred_despite_hangul_in_source_id():
    doc = _fixture_documents()["arxiv_should_stay_unknown"]
    assert gi.infer_document_geography(doc) is None


def test_country_named_in_title_is_not_a_geography_signal():
    doc = _fixture_documents()["mentions_country_should_stay_unknown"]
    assert gi.infer_document_geography(doc) is None


def test_aggregator_source_id_excluded_even_with_hangul_title():
    doc = _fixture_documents()["aggregator_should_stay_unknown"]
    assert gi.infer_document_geography(doc) is None


def test_run_inference_never_touches_already_classified_documents():
    docs = _fixture_documents()
    report = gi.run_inference(docs)
    newly_ids = {r["document_id"] for r in report["newly_classified_documents"]}
    assert "already_known" not in newly_ids


def test_run_inference_before_after_counts_are_consistent():
    docs = _fixture_documents()
    report = gi.run_inference(docs)
    assert report["total_documents"] == len(docs)
    # 3 real documents should get newly classified: kr_tld, us_gov_tld, kr_registry.
    assert report["newly_classified_count"] == 3
    assert report["before_unknown_country_count"] - report["after_unknown_country_count"] == 3


def test_run_inference_reports_signal_breakdown():
    docs = _fixture_documents()
    report = gi.run_inference(docs)
    assert report["newly_classified_by_signal"]["TLD"] == 2
    assert report["newly_classified_by_signal"]["SOURCE_ID_REGISTRY"] == 1


def test_real_corpus_produces_a_defensible_nonzero_result():
    """Sanity check against the REAL corpus (not a fixture) -- proves this module runs against
    the real 597-document file and produces a plausible, non-fabricated result: some documents
    get classified, but the corpus stays majority UNKNOWN (never fully resolved by a handful of
    transparent rules)."""
    report = gi.run_inference()
    assert report["total_documents"] >= 590
    assert report["newly_classified_count"] > 0
    assert report["after_unknown_country_count"] < report["before_unknown_country_count"]
    assert report["after_unknown_country_count"] > 0  # never claim full resolution


def run_all():
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"{len(tests)} tests passed")


if __name__ == "__main__":
    run_all()
