import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import node_support_evaluator as nse  # noqa: E402


def test_real_evidence_with_document_id_is_supported():
    node = {"status": "REAL_EVIDENCE", "document_id": "abc123"}
    assert nse.evaluate_node_support(node) == nse.SUPPORTED


def test_real_evidence_without_document_id_is_not_supported():
    """Boundary case: a malformed REAL_EVIDENCE node with no document_id must never be scored
    SUPPORTED -- falls through to UNKNOWN rather than being trusted blindly."""
    node = {"status": "REAL_EVIDENCE", "document_id": None}
    assert nse.evaluate_node_support(node) == nse.UNKNOWN


def test_noted_is_partially_supported():
    node = {"status": "NOTED", "document_id": None}
    assert nse.evaluate_node_support(node) == nse.PARTIALLY_SUPPORTED


def test_statistical_gap_is_insufficient_evidence():
    node = {"status": "STATISTICAL_GAP", "document_id": None}
    assert nse.evaluate_node_support(node) == nse.INSUFFICIENT_EVIDENCE


def test_topic_scoped_gap_statuses_are_not_found():
    for status in ("SOURCE_GAP", "TEMPORAL_GAP", "RESEARCH_GAP", "HISTORY_GAP",
                   "COUNTEREVIDENCE_GAP", "GEOGRAPHIC_GAP"):
        node = {"status": status, "document_id": None}
        assert nse.evaluate_node_support(node) == nse.NOT_FOUND, status


def test_unknown_status_is_unknown():
    node = {"status": "UNKNOWN", "document_id": None}
    assert nse.evaluate_node_support(node) == nse.UNKNOWN


def test_explicit_applicable_false_overrides_everything_to_not_applicable():
    node = {"status": "REAL_EVIDENCE", "document_id": "abc123", "applicable": False}
    assert nse.evaluate_node_support(node) == nse.NOT_APPLICABLE


def test_unrecognized_status_defaults_to_unknown_never_supported():
    node = {"status": "SOMETHING_NEW_NOT_IN_ANY_LIST", "document_id": "abc"}
    assert nse.evaluate_node_support(node) == nse.UNKNOWN


def test_non_dict_input_is_unknown():
    assert nse.evaluate_node_support(None) == nse.UNKNOWN
    assert nse.evaluate_node_support("not a dict") == nse.UNKNOWN


def test_evaluate_chain_preserves_all_node_names():
    chain = {
        "A": {"status": "REAL_EVIDENCE", "document_id": "x"},
        "B": {"status": "SOURCE_GAP", "document_id": None},
    }
    labels = nse.evaluate_chain(chain)
    assert set(labels.keys()) == {"A", "B"}
    assert labels["A"] == nse.SUPPORTED
    assert labels["B"] == nse.NOT_FOUND


def test_support_distribution_sums_to_chain_length():
    chain = {
        "A": {"status": "REAL_EVIDENCE", "document_id": "x"},
        "B": {"status": "SOURCE_GAP", "document_id": None},
        "C": {"status": "NOTED", "document_id": None},
        "D": {"status": "STATISTICAL_GAP", "document_id": None},
    }
    dist = nse.support_distribution(chain)
    assert sum(dist.values()) == len(chain)
    assert dist[nse.SUPPORTED] == 1
    assert dist[nse.NOT_FOUND] == 1
    assert dist[nse.PARTIALLY_SUPPORTED] == 1
    assert dist[nse.INSUFFICIENT_EVIDENCE] == 1


def test_real_energy_chain_scores_expected_distribution():
    """Concrete, known-real check against the committed AI_ENERGY_INFRA chain: 4 REAL_EVIDENCE
    nodes with document_ids, 1 NOTED node, 1 STATISTICAL_GAP node, 4 topic-scoped gap nodes."""
    import deep_pilot as dp
    chain = dp.build_evidence_chain()
    dist = nse.support_distribution(chain)
    assert dist[nse.SUPPORTED] == 4
    assert dist[nse.PARTIALLY_SUPPORTED] == 1
    assert dist[nse.INSUFFICIENT_EVIDENCE] == 1
    assert dist[nse.NOT_FOUND] == 4
    assert dist[nse.NOT_APPLICABLE] == 0
    assert dist[nse.UNKNOWN] == 0


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
