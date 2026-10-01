import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))
import domain_classifier as m  # noqa: E402


def test_existing_field_is_high_confidence_and_takes_priority():
    doc = {"document_id": "d1", "field": "에너지·환경", "source_id": "src_arxiv_eess_sy_에너지_환경",
           "title": "완전히 다른 내용의 제목"}
    result = m.classify_document(doc)
    assert result["basis"] == "EXISTING_FIELD"
    assert result["confidence"] == "HIGH"
    assert set(result["domains"]) == {"PLANET:ENERGY", "PLANET:ENVIRONMENT"}


def test_unknown_field_falls_through_to_source_topic_suffix():
    doc = {"document_id": "d2", "field": "존재하지않는분류", "source_id": "src_arxiv_cs_ma_에이전트",
           "title": "x"}
    result = m.classify_document(doc)
    assert result["basis"] == "SOURCE_TOPIC_SUFFIX"
    assert result["domains"] == ["TECHNOLOGY_INFRASTRUCTURE"]


def test_title_keyword_is_low_confidence_fallback():
    doc = {"document_id": "d3", "field": None, "source_id": "src_naver_news",
           "title": "Nvidia Thinks It Can Stop Rogue AI—Without All That Government Oversight"}
    result = m.classify_document(doc)
    assert result["basis"] == "TITLE_KEYWORD"
    assert result["confidence"] == "LOW"
    assert "TECHNOLOGY_INFRASTRUCTURE" in result["domains"]
    assert "POLICY_LAW_GOVERNANCE" in result["domains"]


def test_no_signal_is_honestly_unknown_never_guessed():
    doc = {"document_id": "d4", "field": None, "source_id": "src_mystery", "title": "조용한 하루"}
    result = m.classify_document(doc)
    assert result["domains"] == []
    assert result["basis"] == "NONE"
    assert result["confidence"] == "NONE"


def test_multi_label_never_forced_to_single():
    doc = {"document_id": "d5", "field": "환경·에너지·동물", "source_id": "src_x", "title": "x"}
    result = m.classify_document(doc)
    assert len(result["domains"]) == 3


def test_coverage_report_never_fabricates_a_domain_for_unknown():
    docs = {
        "d1": {"document_id": "d1", "field": "경제", "source_id": "src_x", "title": "x"},
        "d2": {"document_id": "d2", "field": None, "source_id": "src_mystery", "title": "조용한 하루"},
    }
    report = m.build_coverage_report(docs)
    assert report["total_documents"] == 2
    assert report["documents_unclassified"] == 1
    assert report["per_document"]["d2"]["domains"] == []


def test_coverage_report_reports_evidence_basis_distribution_honestly():
    docs = {
        "d1": {"document_id": "d1", "field": "경제", "source_id": "src_x", "title": "x"},
        "d2": {"document_id": "d2", "field": None, "source_id": "src_mystery", "title": "AI 규제 논의"},
    }
    report = m.build_coverage_report(docs)
    assert report["evidence_basis_distribution"]["EXISTING_FIELD"] == 1
    assert report["evidence_basis_distribution"]["TITLE_KEYWORD"] == 1


def test_never_writes_documents_json():
    src = (PKG_DIR / "domain_classifier.py").read_text(encoding="utf-8")
    assert 'open(DOCUMENTS_PATH, "w")' not in src
    assert "DOCUMENTS_PATH.write_text" not in src


def test_real_corpus_reduces_unclassified_fraction_below_m5e4_baseline():
    # M.5E-4 baseline was ~65% unclassified (field=None for all non-papers documents). This
    # module must show a real, honest improvement -- not just claim one.
    report = m.build_coverage_report()
    assert report["total_documents"] > 500
    assert report["documents_unclassified_fraction"] < 0.65


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
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
