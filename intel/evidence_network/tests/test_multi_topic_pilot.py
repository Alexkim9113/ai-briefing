import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import deep_pilot as dp  # noqa: E402
import multi_topic_pilot as mtp  # noqa: E402


def test_generalized_energy_chain_matches_original_status_and_document_id_per_node():
    """Regression-safety: the generalized pipeline, run with AI_ENERGY_INFRA's own topic
    definition, must reproduce deep_pilot.build_evidence_chain()'s exact status and document_id
    for every one of the 10 nodes -- proving generalization did not change AI_ENERGY_INFRA's
    real result. (Reason-string wording is intentionally more generic in the generalized version
    and is not compared here -- only the load-bearing status/document_id fields are.)"""
    original = dp.build_evidence_chain()
    generalized = mtp.build_evidence_chain(mtp.TOPIC_AI_ENERGY_INFRA)
    assert set(original.keys()) == set(generalized.keys()) == set(dp.CHAIN_NODES)
    for node_name in dp.CHAIN_NODES:
        assert original[node_name]["status"] == generalized[node_name]["status"], node_name
        assert original[node_name].get("document_id") == generalized[node_name].get("document_id"), node_name


def test_generalized_energy_report_matches_original_bucket_counts():
    original_report = dp.deep_pilot_report()
    generalized_report = mtp.topic_report(mtp.TOPIC_AI_ENERGY_INFRA)
    assert original_report["bucket_counts"] == generalized_report["bucket_counts"]
    assert original_report["total_topic_documents"] == generalized_report["total_topic_documents"]
    assert original_report["chain_summary"] == generalized_report["chain_summary"]


def test_ai_agents_and_ai_labor_reports_are_schema_valid():
    for topic_def in (mtp.TOPIC_AI_AGENTS, mtp.TOPIC_AI_LABOR):
        report = mtp.topic_report(topic_def)
        assert report["topic_name"] == topic_def.name
        chain = report["evidence_chain"]
        assert set(chain.keys()) == set(dp.CHAIN_NODES)
        for name, node in chain.items():
            assert node["status"] in ("REAL_EVIDENCE", "NOTED") or node["status"] in dp.GAP_STATUSES, name
            if node["status"] == "REAL_EVIDENCE":
                assert node["document_id"] is not None
            if node["status"] in dp.GAP_STATUSES:
                assert node["document_id"] is None
        counts = report["chain_summary"]
        assert counts["total_nodes"] == 10
        assert counts["real_evidence_or_noted_nodes"] + counts["gap_nodes"] == 10


def test_ai_agents_real_field_document_count_matches_known_corpus_audit():
    """Known real count from pilot_topic_coverage.py's own comment: 12 real field-tagged
    AI_AGENTS documents exist in the corpus (before adding any POLICY title-matches)."""
    docs = dp.load_documents()
    field_tagged = [d for d in docs.values() if d.get("field") == mtp.TOPIC_AI_AGENTS.field_value]
    assert len(field_tagged) == 12


def test_ai_labor_real_field_document_count_matches_known_corpus_audit():
    docs = dp.load_documents()
    field_tagged = [d for d in docs.values() if d.get("field") == mtp.TOPIC_AI_LABOR.field_value]
    assert len(field_tagged) == 11


def test_cross_domain_phrase_matching_never_crosses_into_the_topics_own_field():
    """A topic's cross-domain check must only search OTHER topics' field-tagged documents, never
    its own -- otherwise a topic could 'discover' a cross-domain link to itself."""
    for topic_def in mtp.ALL_TOPICS:
        assert topic_def.field_value not in topic_def.other_field_values


def test_topic_pipeline_never_mutates_real_documents_json():
    real_docs_path = Path(__file__).resolve().parents[2] / "documents.json"
    before = real_docs_path.read_text(encoding="utf-8")
    for topic_def in mtp.ALL_TOPICS:
        mtp.topic_report(topic_def)
    after = real_docs_path.read_text(encoding="utf-8")
    assert before == after


def test_topic_pipeline_is_idempotent():
    for topic_def in mtp.ALL_TOPICS:
        r1 = mtp.topic_report(topic_def)
        r2 = mtp.topic_report(topic_def)
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
