import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))
import corpus_quality_audit as m  # noqa: E402


def test_duplicate_content_hash_is_flagged():
    docs = {
        "d1": {"document_id": "d1", "content_hash": "abc", "title": "Real title here",
               "canonical_url": "https://x.example/1", "published": "2026-01-01", "field": "경제"},
        "d2": {"document_id": "d2", "content_hash": "abc", "title": "Another real title",
               "canonical_url": "https://x.example/2", "published": "2026-01-02", "field": "경제"},
    }
    result = m.build_quality_audit(docs)
    assert result["duplicate_content_hash_groups"] == 1
    assert result["bucket_counts"]["DUPLICATE_OR_DERIVATIVE"] == 2


def test_missing_metadata_is_flagged_poor():
    doc = {"document_id": "d1", "content_hash": "x", "title": None,
           "canonical_url": "https://x.example", "published": "2026-01-01"}
    buckets = [b["bucket"] for b in m.classify_document_quality(doc, set())]
    assert "METADATA_POOR" in buckets


def test_short_title_flagged_low_intelligence_value():
    doc = {"document_id": "d1", "content_hash": "x", "title": "속보",
           "canonical_url": "https://x.example", "published": "2026-01-01", "field": "경제"}
    buckets = [b["bucket"] for b in m.classify_document_quality(doc, set())]
    assert "LOW_INTELLIGENCE_VALUE" in buckets


def test_unclassified_but_otherwise_complete_is_useful_but_unclassified():
    doc = {"document_id": "d1", "content_hash": "x", "title": "A perfectly normal headline here",
           "canonical_url": "https://x.example", "published": "2026-01-01", "field": None,
           "source_id": "src_mystery"}
    buckets = [b["bucket"] for b in m.classify_document_quality(doc, set())]
    assert buckets == ["USEFUL_BUT_UNCLASSIFIED"]


def test_good_quality_document_has_no_issues():
    doc = {"document_id": "d1", "content_hash": "x", "title": "A perfectly normal headline here",
           "canonical_url": "https://x.example", "published": "2026-01-01", "field": "경제"}
    buckets = [b["bucket"] for b in m.classify_document_quality(doc, set())]
    assert buckets == ["GOOD_QUALITY_NO_ISSUE"]


def test_bucket_counts_can_exceed_total_documents_when_multi_bucket():
    doc = {"document_id": "d1", "content_hash": "x", "title": "짧다",
           "canonical_url": None, "published": "2026-01-01", "field": None, "source_id": "src_x"}
    buckets = [b["bucket"] for b in m.classify_document_quality(doc, set())]
    assert "METADATA_POOR" in buckets
    assert "LOW_INTELLIGENCE_VALUE" in buckets


def test_never_writes_documents_json():
    src = (PKG_DIR / "corpus_quality_audit.py").read_text(encoding="utf-8")
    assert 'open(DOCUMENTS_PATH, "w")' not in src
    assert "DOCUMENTS_PATH.write_text" not in src


def test_never_auto_deletes_anything():
    src = (PKG_DIR / "corpus_quality_audit.py").read_text(encoding="utf-8")
    assert "del documents" not in src
    assert ".pop(" not in src


def test_real_corpus_runs_without_crash_and_reports_honest_counts():
    result = m.build_quality_audit()
    assert result["total_documents"] > 500
    # Real-corpus baseline (M.5F Section 21): confirmed 0 duplicate content_hash groups and 0
    # missing title/url/date across this corpus -- an honest finding, not assumed.
    assert result["duplicate_content_hash_groups"] == 0
    assert "METADATA_POOR" not in result["bucket_counts"]


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
