# PHASE M.5D -- tests for pilot_topic_coverage.py against the REAL corpus (intel/documents.json,
# read-only). Proves the matrix reflects real counts, and that it never mutates documents.json.
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
sys.path.insert(0, str(PKG))

import pilot_topic_coverage as ptc  # noqa: E402


def test_pilot_topics_have_real_nonzero_volume():
    result = ptc.all_pilot_topics_coverage()
    for name, matrix in result.items():
        assert matrix["total_documents"] > 0, name


def test_agents_topic_matches_known_real_count():
    matrix = ptc.topic_coverage(ptc.PILOT_TOPICS["AI_AGENTS"])
    assert matrix["total_documents"] == 12
    assert matrix["domain_by_document_type"].get("RESEARCH", 0) == 5
    assert matrix["domain_by_document_type"].get("NEWS", 0) == 7


def test_labor_topic_is_all_news_no_official_or_academic():
    matrix = ptc.topic_coverage(ptc.PILOT_TOPICS["AI_LABOR"])
    assert matrix["total_documents"] == 11
    assert matrix["domain_by_document_type"].get("NEWS", 0) == 11
    assert matrix["source_tier_distribution"].get("OFFICIAL", 0) == 0
    assert matrix["source_tier_distribution"].get("ACADEMIC", 0) == 0


def test_energy_topic_has_research_majority():
    matrix = ptc.topic_coverage(ptc.PILOT_TOPICS["AI_ENERGY_INFRA"])
    assert matrix["total_documents"] == 11
    assert matrix["domain_by_document_type"].get("RESEARCH", 0) == 7


def test_matrix_never_mutates_real_documents_json():
    real_docs_path = Path(__file__).resolve().parents[2] / "documents.json"
    before = real_docs_path.read_text(encoding="utf-8")
    ptc.all_pilot_topics_coverage()
    after = real_docs_path.read_text(encoding="utf-8")
    assert before == after


def test_overall_bias_summary_reports_real_ratios_not_hidden():
    summary = ptc.overall_corpus_bias_summary()
    assert summary["total_documents"] == 577
    assert 0 < summary["news_heavy"]["ratio"] <= 1
    assert summary["recent_heavy"]["span_days"] is not None


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
