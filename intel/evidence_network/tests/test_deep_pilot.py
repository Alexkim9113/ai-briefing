import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import deep_pilot as dp  # noqa: E402


def test_classify_document_uses_real_published_date_only():
    assert dp.classify_document({"published": "2025-06-01"}) == "BASELINE"
    assert dp.classify_document({"published": "2026-05-01"}) == "TRANSITION"
    assert dp.classify_document({"published": "2026-09-15"}) == "CURRENT"
    assert dp.classify_document({"published": None}) == "UNASSIGNED_GAP"
    assert dp.classify_document({"published": "not-a-date"}) == "UNASSIGNED_GAP"


def test_find_topic_policy_documents_requires_both_energy_and_ai_hint():
    docs = {
        "d1": {"document_type": "POLICY", "title": "Expanding Electricity Grid Capacity for the Artificial Intelligence Race"},
        "d2": {"document_type": "POLICY", "title": "Effluent Limitations for Steam Electric Power Plants"},  # energy, no AI
        "d3": {"document_type": "NEWS", "title": "AI power grid update"},  # not POLICY
    }
    matches = dp.find_topic_policy_documents(docs)
    assert "d1" in matches
    assert "d2" not in matches
    assert "d3" not in matches


def test_real_corpus_topic_is_ai_energy_infra_with_one_real_baseline_document():
    report = dp.deep_pilot_report()
    assert report["topic_name"] == "AI_ENERGY_INFRA"
    assert report["bucket_counts"]["BASELINE"] == 1
    assert report["bucket_document_ids"]["BASELINE"] == ["b8a4c2850d58bbd8"]


def test_evidence_chain_has_all_ten_nodes():
    chain = dp.build_evidence_chain()
    assert set(chain.keys()) == set(dp.CHAIN_NODES)


def test_evidence_chain_every_node_is_real_evidence_noted_or_a_defined_gap_status():
    chain = dp.build_evidence_chain()
    for name, node in chain.items():
        assert node["status"] in ("REAL_EVIDENCE", "NOTED") or node["status"] in dp.GAP_STATUSES, name
        if node["status"] == "REAL_EVIDENCE":
            assert node["document_id"] is not None
        if node["status"] in dp.GAP_STATUSES:
            assert node["document_id"] is None


def test_confirmed_change_is_honestly_a_gap_not_forced():
    """The real corpus has zero documents bridging the ~1 year gap between the BASELINE POLICY
    document and the CURRENT cluster -- this must surface as a real gap, never a fabricated
    bridge document."""
    chain = dp.build_evidence_chain()
    assert chain["CONFIRMED_CHANGE"]["status"] == "TEMPORAL_GAP"


def test_statistical_and_historical_context_are_honest_gaps():
    chain = dp.build_evidence_chain()
    assert chain["STATISTICAL_CONTEXT"]["status"] == "STATISTICAL_GAP"
    assert chain["HISTORICAL_CONTEXT"]["status"] == "HISTORY_GAP"
    assert chain["COUNTEREVIDENCE"]["status"] == "COUNTEREVIDENCE_GAP"


def test_cross_domain_effect_never_forces_an_ambiguous_word_match():
    """Regression for a real false positive caught while building this module: a robotics paper
    titled 'Collision-free Movement on Grids and Beyond' uses 'grid' in a graph-search sense
    unrelated to the power grid, and must NOT be reported as a real cross-domain link."""
    docs = {
        "robotics_doc": {"document_id": "robotics_doc", "field": "에이전트",
                          "document_type": "RESEARCH",
                          "title": "Collision-free Movement on Grids and Beyond"},
    }
    real_docs = dp.load_documents()
    combined = dict(real_docs)
    combined.update(docs)
    chain = dp.build_evidence_chain(combined)
    assert chain["CROSS_DOMAIN_EFFECT"]["document_id"] != "robotics_doc"


def test_deep_pilot_report_never_mutates_real_documents_json():
    real_docs_path = Path(__file__).resolve().parents[2] / "documents.json"
    before = real_docs_path.read_text(encoding="utf-8")
    dp.deep_pilot_report()
    after = real_docs_path.read_text(encoding="utf-8")
    assert before == after


def test_deep_pilot_report_is_idempotent():
    r1 = dp.deep_pilot_report()
    r2 = dp.deep_pilot_report()
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
