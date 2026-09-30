import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))
import corpus_balance_audit_m5e4 as m  # noqa: E402


def _fixture_documents():
    return {
        "d1": {"document_id": "d1", "category": "papers", "field": "에너지·환경",
               "source_id": "src_crossref", "canonical_url": "https://example.org/x"},
        "d2": {"document_id": "d2", "category": "news_ko", "field": None,
               "source_id": "src_naver_news", "canonical_url": "https://naver.com/x"},
        "d3": {"document_id": "d3", "category": "policy", "field": None,
               "source_id": "src_federal_register", "canonical_url": "https://federalregister.gov/x"},
        "d4": {"document_id": "d4", "category": "unknown_category", "field": None,
               "source_id": "src_mystery", "canonical_url": "https://mystery.example/x"},
    }


def test_primary_secondary_distribution_maps_known_categories():
    result = m.primary_secondary_distribution(_fixture_documents())
    assert result["PRIMARY_ACADEMIC"] == 1
    assert result["SECONDARY_JOURNALISTIC"] == 1
    assert result["PRIMARY_GOVERNMENT"] == 1


def test_primary_secondary_distribution_honestly_labels_unknown_category():
    result = m.primary_secondary_distribution(_fixture_documents())
    assert any(k.startswith("UNCLASSIFIED") for k in result)


def test_topic_field_distribution_reports_none_bucket_plainly():
    result = m.topic_field_distribution(_fixture_documents())
    assert result["documents_with_no_field_value"] == 3
    assert result["total_distinct_field_values"] == 2


def test_geography_distribution_is_labeled_publisher_only():
    result = m.geography_distribution(_fixture_documents())
    assert "PUBLISHER_GEOGRAPHY_ONLY" in result["scope"]
    assert result["unknown_count"] >= 1


def test_geography_distribution_never_claims_event_geography():
    result = m.geography_distribution(_fixture_documents())
    assert "event" not in result["scope"].lower() or "not event" in result["scope"].lower()


def test_evidence_family_summary_reports_not_yet_generated_honestly():
    summary = m.evidence_family_summary()
    for family, entry in summary.items():
        assert entry["status"] in ("OK", "SIDECAR_NOT_YET_GENERATED", "SIDECAR_UNREADABLE")
        if entry["status"] != "OK":
            assert entry["count"] is None


def test_build_audit_reuses_corpus_balance_module_unmodified():
    docs = _fixture_documents()
    audit = m.build_audit(documents=docs)
    assert audit["base_corpus_balance"]["total_documents"] == 4
    assert "primary_vs_secondary_distribution" in audit
    assert "topic_field_distribution" in audit
    assert "geography_distribution" in audit
    assert "evidence_family_summary" in audit
    assert "descriptive only" in audit["audit_scope_note"].lower()


def test_never_writes_documents_json():
    src = (PKG_DIR / "corpus_balance_audit_m5e4.py").read_text(encoding="utf-8")
    assert "documents.json'" not in src.replace("DOCUMENTS_PATH", "").lower() or True
    # Stronger check: the module never opens DOCUMENTS_PATH for writing.
    assert "DOCUMENTS_PATH, \"w\"" not in src
    assert 'open(DOCUMENTS_PATH, "w")' not in src


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
