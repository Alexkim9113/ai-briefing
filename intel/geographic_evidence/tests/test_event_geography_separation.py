import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))
import event_geography_separation as m  # noqa: E402


def test_federal_register_document_gets_real_event_jurisdiction():
    doc = {"document_id": "d1", "source_id": "src_federal_register", "country": "US",
           "canonical_url": "https://www.federalregister.gov/documents/x"}
    result = m.classify_document_geography(doc)
    assert result["event_country"] == "US"
    assert result["jurisdiction"] == "US"


def test_news_document_with_no_structured_field_is_honestly_unknown():
    doc = {"document_id": "d2", "source_id": "src_naver_news",
           "canonical_url": "https://naver.com/article-about-korea-policy"}
    result = m.classify_document_geography(doc)
    assert result["event_country"] == "UNKNOWN"
    assert result["jurisdiction"] == "UNKNOWN"


def test_publisher_and_event_are_structurally_distinct_fields():
    doc = {"document_id": "d3", "source_id": "src_naver_news",
           "canonical_url": "https://naver.com/x"}
    result = m.classify_document_geography(doc)
    assert "publisher_country" in result
    assert "event_country" in result
    assert result["publisher_and_event_conflated_in_source_data"] is False


def test_never_guesses_event_country_from_title_text():
    doc = {"document_id": "d4", "source_id": "src_naver_news",
           "title": "United States announces new AI energy policy",
           "canonical_url": "https://naver.com/x"}
    result = m.classify_document_geography(doc)
    # Even though "United States" appears in the title, this source_id has no real structured
    # jurisdiction field, so event_country must stay UNKNOWN -- never inferred from title text.
    assert result["event_country"] == "UNKNOWN"


def test_affected_region_is_always_unknown_this_phase():
    doc = {"document_id": "d5", "source_id": "src_federal_register", "country": "US"}
    result = m.classify_document_geography(doc)
    assert result["affected_region"] == "UNKNOWN"


def test_build_result_reports_conflation_and_distinctness_counts():
    docs = {
        "d1": {"document_id": "d1", "source_id": "src_federal_register", "country": "US",
               "canonical_url": "https://www.federalregister.gov/documents/x"},
        "d2": {"document_id": "d2", "source_id": "src_naver_news",
               "canonical_url": "https://naver.com/x"},
    }
    result = m.build_result(documents=docs)
    assert result["total_documents"] == 2
    assert result["documents_with_known_event_country"] == 1


def test_never_writes_documents_json():
    src = (PKG_DIR / "event_geography_separation.py").read_text(encoding="utf-8")
    assert 'open(DOCUMENTS_PATH, "w")' not in src
    assert "DOCUMENTS_PATH.write_text" not in src


def main():
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
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
