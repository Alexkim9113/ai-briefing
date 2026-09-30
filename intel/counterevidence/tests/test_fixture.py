# Manual tests for intel/counterevidence/energy_infra_counterevidence.py.
# def test_...(): + bare assert, run standalone via importlib (no pytest/unittest). Uses a small
# fixture/mock corpus with known planted matches and known non-matches -- never touches the real
# intel/documents.json.
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODULE_PATH = HERE.parent / "energy_infra_counterevidence.py"


def _load():
    spec = importlib.util.spec_from_file_location("energy_infra_counterevidence_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mod = _load()


def _fixture_corpus():
    return {
        "planted_efficiency": {
            "document_id": "planted_efficiency",
            "title": "AI data center reports major PUE improvement after chip upgrade",
            "abstract_excerpt": "",
        },
        "planted_workload": {
            "document_id": "planted_workload",
            "title": "AI data centers adopt demand response to shift electricity load off-peak",
            "abstract_excerpt": "",
        },
        "planted_renewable": {
            "document_id": "planted_renewable",
            "title": "Tech company signs solar power purchase agreement for AI data center power grid needs",
            "abstract_excerpt": "",
        },
        "planted_overestimate": {
            "document_id": "planted_overestimate",
            "title": "Utility says AI energy demand projections too high, grid capacity forecast revised down",
            "abstract_excerpt": "",
        },
        "nonmatch_unrelated": {
            "document_id": "nonmatch_unrelated",
            "title": "City council votes on new zoning rules",
            "abstract_excerpt": "",
        },
        "nonmatch_offtopic_efficiency": {
            "document_id": "nonmatch_offtopic_efficiency",
            "title": "New car model boasts fuel efficiency gains",
            "abstract_excerpt": "",
        },
    }


def test_each_direction_finds_its_planted_match():
    docs = _fixture_corpus()
    results = mod.run_counterevidence_search(docs)
    assert results["EFFICIENCY_IMPROVEMENTS"]["status"] == "REAL_EVIDENCE"
    assert any(m["document_id"] == "planted_efficiency" for m in results["EFFICIENCY_IMPROVEMENTS"]["matches"])

    assert results["WORKLOAD_SHIFTING"]["status"] == "REAL_EVIDENCE"
    assert any(m["document_id"] == "planted_workload" for m in results["WORKLOAD_SHIFTING"]["matches"])

    assert results["RENEWABLE_PROCUREMENT"]["status"] == "REAL_EVIDENCE"
    assert any(m["document_id"] == "planted_renewable" for m in results["RENEWABLE_PROCUREMENT"]["matches"])

    assert results["DEMAND_OVERESTIMATION"]["status"] == "REAL_EVIDENCE"
    assert any(m["document_id"] == "planted_overestimate" for m in results["DEMAND_OVERESTIMATION"]["matches"])


def test_unrelated_document_never_matches_any_direction():
    docs = _fixture_corpus()
    results = mod.run_counterevidence_search(docs)
    for direction_result in results.values():
        all_ids = {m["document_id"] for m in direction_result["matches"]} | \
                  {m["document_id"] for m in direction_result["rejected_near_misses"]}
        assert "nonmatch_unrelated" not in all_ids


def test_off_topic_keyword_hit_is_rejected_not_counted_as_evidence():
    docs = _fixture_corpus()
    results = mod.run_counterevidence_search(docs)
    eff = results["EFFICIENCY_IMPROVEMENTS"]
    matched_ids = {m["document_id"] for m in eff["matches"]}
    rejected_ids = {m["document_id"] for m in eff["rejected_near_misses"]}
    assert "nonmatch_offtopic_efficiency" not in matched_ids
    assert "nonmatch_offtopic_efficiency" in rejected_ids


def test_empty_corpus_reports_honest_gap_for_all_directions():
    results = mod.run_counterevidence_search({})
    for direction, result in results.items():
        assert result["status"] == "COUNTEREVIDENCE_GAP", direction
        assert result["matches"] == []


def test_build_result_summary_counts_match_directions():
    docs = _fixture_corpus()
    result = mod.build_result(docs)
    assert result["summary"]["directions_with_real_evidence"] == 4
    assert result["summary"]["directions_with_gap"] == 0
    assert result["summary"]["overall_counterevidence_status"] == "PARTIAL_REAL_EVIDENCE"


def test_build_result_all_gap_when_no_matches():
    result = mod.build_result({"x": {"document_id": "x", "title": "irrelevant", "abstract_excerpt": ""}})
    assert result["summary"]["directions_with_real_evidence"] == 0
    assert result["summary"]["overall_counterevidence_status"] == "COUNTEREVIDENCE_GAP"


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
