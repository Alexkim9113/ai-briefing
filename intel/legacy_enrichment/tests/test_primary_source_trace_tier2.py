import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent

sys.path.insert(0, str(PKG_DIR))
import primary_source_trace_tier2 as tier2  # noqa: E402
import primary_source_trace as pst  # noqa: E402


def _fixture_candidates_report():
    return {
        "candidates": [
            {"document_id": "p1", "score": 7, "document_type": "POLICY",
             "title": "Policy One", "source_id": "src_federal_register",
             "canonical_url": "https://www.federalregister.gov/documents/p1"},
            {"document_id": "p2", "score": 7, "document_type": "POLICY",
             "title": "Policy Two", "source_id": "src_federal_register",
             "canonical_url": "https://www.federalregister.gov/documents/p2"},
            {"document_id": "n1", "score": 5, "document_type": "NEWS",
             "title": "News One", "source_id": "src_example",
             "canonical_url": "https://example.com/n1"},
            {"document_id": "n2", "score": 5, "document_type": "NEWS",
             "title": "News Two", "source_id": "src_example",
             "canonical_url": "https://example.com/n2"},
            {"document_id": "p3", "score": 4, "document_type": "POLICY",
             "title": "Policy Three", "source_id": "src_federal_register",
             "canonical_url": "https://www.federalregister.gov/documents/p3"},
        ],
    }


def _fixture_documents(report):
    return {c["document_id"]: {
        "document_id": c["document_id"], "title": c["title"],
        "document_type": c["document_type"], "source_id": c["source_id"],
        "canonical_url": c["canonical_url"],
    } for c in report["candidates"]}


def test_select_tier2_excludes_documents_tier1_already_traced():
    report = _fixture_candidates_report()
    tier2_candidates, tier1_ids, note = tier2.select_tier2_candidates(report, tier2_size=10)
    tier2_ids = {c["document_id"] for c in tier2_candidates}
    assert tier1_ids  # tier 1 (NEWS-only, first N) selected something
    assert tier2_ids.isdisjoint(tier1_ids)


def test_select_tier2_preserves_original_rank_order():
    report = _fixture_candidates_report()
    tier2_candidates, _, _ = tier2.select_tier2_candidates(report, tier2_size=10)
    ids = [c["document_id"] for c in tier2_candidates]
    all_ids = [c["document_id"] for c in report["candidates"]]
    filtered_all = [i for i in all_ids if i in ids]
    assert ids == filtered_all  # relative order preserved, never re-sorted


def test_run_tier2_trace_uses_only_primary_source_trace_status_vocabulary():
    report = _fixture_candidates_report()
    docs = _fixture_documents(report)
    result = tier2.run_tier2_trace(documents=docs, candidates_report=report, tier2_size=10)
    for status in result["status_breakdown"]:
        assert status in pst.STATUS_VALUES
    for trace in result["traces"].values():
        assert trace["status"] in pst.STATUS_VALUES


def test_run_tier2_trace_correctly_finds_primary_source_on_federal_register():
    report = _fixture_candidates_report()
    docs = _fixture_documents(report)
    result = tier2.run_tier2_trace(documents=docs, candidates_report=report, tier2_size=10)
    # p1/p2/p3 sit directly on federalregister.gov -> PRIMARY_SOURCE_FOUND
    for pid in ("p1", "p2", "p3"):
        if pid in result["traces"]:
            assert result["traces"][pid]["status"] == "PRIMARY_SOURCE_FOUND"


def test_run_tier2_trace_reports_relationship_vocabulary_finding():
    report = _fixture_candidates_report()
    docs = _fixture_documents(report)
    result = tier2.run_tier2_trace(documents=docs, candidates_report=report, tier2_size=10)
    note = result["relationship_vocabulary_note"]
    assert "REPORTS_ON" in note
    assert "does NOT exist as a single unified system" in note


def test_real_tier2_run_against_current_corpus_is_internally_consistent():
    """Sanity check against the real, current corpus and its real priority_candidates.json."""
    result = tier2.run_tier2_trace()
    assert result["candidates_traced"] == 10
    for status in result["status_breakdown"]:
        assert status in pst.STATUS_VALUES
    # every traced tier-2 id must be absent from the excluded (tier-1) set
    traced_ids = set(result["traces"].keys())
    assert traced_ids.isdisjoint(set(result["already_traced_excluded"]))


def run_all():
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"{len(tests)} tests passed")


if __name__ == "__main__":
    run_all()
