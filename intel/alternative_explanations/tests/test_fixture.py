# Manual tests for intel/alternative_explanations/energy_demand_alternatives.py.
# def test_...(): + bare assert, run standalone via importlib (no pytest/unittest).
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODULE_PATH = HERE.parent / "energy_demand_alternatives.py"


def _load():
    spec = importlib.util.spec_from_file_location("energy_demand_alternatives_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mod = _load()


def test_no_corpus_match_classifies_as_general_knowledge_label():
    label = mod.classify_evidence_strength([])
    assert label == mod.GENERAL_KNOWLEDGE_LABEL
    assert label not in mod.GRADED_EFFECT_VOCAB


def test_corpus_match_classifies_with_graded_vocabulary_only():
    label = mod.classify_evidence_strength([{"document_id": "fake1", "title": "x", "matched_keywords": ["ev"]}])
    assert label in mod.GRADED_EFFECT_VOCAB
    assert label != mod.GENERAL_KNOWLEDGE_LABEL


def test_graded_vocabulary_never_includes_expected_outcome():
    assert "EXPECTED_OUTCOME" not in mod.GRADED_EFFECT_VOCAB


def test_graded_vocabulary_is_the_four_standing_labels():
    assert set(mod.GRADED_EFFECT_VOCAB) == {
        "OBSERVED_EFFECT", "SUPPORTED_MECHANISM", "POSSIBLE_IMPLICATION", "SPECULATIVE_EXTENSION",
    }


def test_all_six_alternatives_are_real_non_fabricated():
    assert len(mod.ALTERNATIVE_EXPLANATIONS) == 6
    for alt in mod.ALTERNATIVE_EXPLANATIONS:
        assert alt["is_real_non_fabricated_alternative"] is True
        assert alt["search_keywords"], f"{alt['explanation_id']} has no search keywords"


def test_search_finds_planted_match_in_fixture_corpus():
    fixture_docs = {
        "planted_ev": {
            "document_id": "planted_ev",
            "title": "Electric vehicle charging demand surges nationwide",
            "abstract_excerpt": "",
        },
        "nonmatch": {
            "document_id": "nonmatch",
            "title": "Unrelated news about sports",
            "abstract_excerpt": "",
        },
    }
    hits = mod.search_alternative_in_corpus(["electric vehicle", "ev charging"], fixture_docs)
    hit_ids = {h["document_id"] for h in hits}
    assert hit_ids == {"planted_ev"}


def test_build_result_labels_no_corpus_match_as_general_knowledge_only():
    result = mod.build_result({})
    assert result["summary"]["graded_by_corpus_evidence"] == 0
    assert result["summary"]["general_knowledge_only"] == 6
    for entry in result["alternatives"]:
        assert entry["evidence_strength_label"] == mod.GENERAL_KNOWLEDGE_LABEL
        assert entry["corpus_search_result"]["status"] == "NOT_FOUND"


def test_build_result_labels_corpus_match_with_graded_vocab():
    fixture_docs = {
        "planted_ev": {
            "document_id": "planted_ev",
            "title": "Electric vehicle charging demand surges nationwide",
            "abstract_excerpt": "",
        },
    }
    result = mod.build_result(fixture_docs)
    ev_entry = next(e for e in result["alternatives"] if e["explanation_id"] == "EV_CHARGING_DEMAND_GROWTH")
    assert ev_entry["corpus_search_result"]["status"] == "REAL_EVIDENCE"
    assert ev_entry["evidence_strength_label"] in mod.GRADED_EFFECT_VOCAB
    assert result["summary"]["graded_by_corpus_evidence"] == 1
    assert result["summary"]["general_knowledge_only"] == 5


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)
