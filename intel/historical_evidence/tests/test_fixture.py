# Manual tests for intel/historical_evidence/energy_infra_analogies.py.
# def test_...(): + bare assert, run standalone via importlib (no pytest/unittest).
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODULE_PATH = HERE.parent / "energy_infra_analogies.py"


def _load():
    spec = importlib.util.spec_from_file_location("energy_infra_analogies_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mod = _load()


def test_all_general_analogies_have_required_six_fields():
    validation = mod.validate_all_analogies()
    assert len(validation) == len(mod.GENERAL_HISTORICAL_ANALOGIES)
    for analogy_id, missing in validation.items():
        assert missing == [], f"{analogy_id} missing fields: {missing}"


def test_validator_flags_missing_field():
    incomplete = {
        "analogy_id": "INCOMPLETE_TEST",
        "HISTORICAL_CONDITION": "x",
        "MECHANISM": "x",
        "OBSERVED_CONSEQUENCE": "x",
        "DIFFERENCE_FROM_PRESENT": "x",
        "BOUNDARY_CONDITION": "x",
        # PRESENT_RELEVANCE deliberately omitted
    }
    missing = mod.validate_analogy_structure(incomplete)
    assert missing == ["PRESENT_RELEVANCE"]


def test_validator_flags_blank_field_as_missing():
    incomplete = {f: "x" for f in mod.REQUIRED_ANALOGY_FIELDS}
    incomplete["MECHANISM"] = "   "
    missing = mod.validate_analogy_structure(incomplete)
    assert missing == ["MECHANISM"]


def test_validator_accepts_fully_populated_analogy():
    complete = {f: f"content for {f}" for f in mod.REQUIRED_ANALOGY_FIELDS}
    assert mod.validate_analogy_structure(complete) == []


def test_all_analogies_are_general_historical_knowledge_not_corpus_backed():
    for analogy in mod.GENERAL_HISTORICAL_ANALOGIES:
        assert analogy["evidence_type"] == "GENERAL_HISTORICAL_KNOWLEDGE"
        assert "document_id" not in analogy


def test_corpus_search_uses_planted_fixture_no_real_documents_touched():
    fixture_docs = {
        "fake001": {
            "document_id": "fake001",
            "title": "AI data centers echo the dot-com internet buildout of the 1990s",
            "abstract_excerpt": "",
        },
        "fake002": {
            "document_id": "fake002",
            "title": "Historically, city council meetings are held on Tuesdays",
            "abstract_excerpt": "",
        },
        "fake003": {
            "document_id": "fake003",
            "title": "Unrelated document about tax policy",
            "abstract_excerpt": "",
        },
    }
    qualifying, rejected = mod.search_corpus_for_historical_comparisons(fixture_docs)
    qualifying_ids = {h["document_id"] for h in qualifying}
    assert qualifying_ids == {"fake001"}
    assert all(h["document_id"] != "fake003" for h in qualifying + rejected)


def test_corpus_search_rejects_off_topic_keyword_hits():
    fixture_docs = {
        "fake_offtopic": {
            "document_id": "fake_offtopic",
            "title": "A history museum reopens after renovation, echoes of the past",
            "abstract_excerpt": "",
        },
    }
    qualifying, rejected = mod.search_corpus_for_historical_comparisons(fixture_docs)
    assert qualifying == []
    assert len(rejected) == 1
    assert rejected[0]["document_id"] == "fake_offtopic"


def test_build_result_separates_two_parts_clearly():
    fixture_docs = {}
    result = mod.build_result(fixture_docs)
    assert "general_historical_knowledge" in result
    assert "corpus_historical_evidence_search" in result
    assert result["general_historical_knowledge"]["evidence_type"] == "GENERAL_HISTORICAL_KNOWLEDGE"
    assert result["corpus_historical_evidence_search"]["evidence_type"] == "CORPUS_SEARCH_RESULT"
    assert result["corpus_historical_evidence_search"]["status"] == "HISTORY_GAP"


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
