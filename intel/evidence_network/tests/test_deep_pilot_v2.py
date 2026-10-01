import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))
import deep_pilot_v2 as m  # noqa: E402


def test_all_13_nodes_present_for_both_pilots():
    for path, key in (("deep_pilot_result.json", "AI_ENERGY_INFRA"),
                       ("deep_pilot_ai_labor_result.json", "AI_LABOR")):
        result = m.build_deep_pilot_v2(key, path, key)
        assert set(result["nodes"].keys()) == set(m.NODES_13)


def test_every_node_status_is_in_the_named_vocabulary():
    result = m.build_deep_pilot_v2("AI_ENERGY_INFRA", "deep_pilot_result.json", "AI_ENERGY_INFRA")
    for name, node in result["nodes"].items():
        assert node["status"] in m.STATUSES, f"{name} has unknown status {node['status']!r}"


def test_supported_node_always_carries_real_document_id():
    for path, key in (("deep_pilot_result.json", "AI_ENERGY_INFRA"),
                       ("deep_pilot_ai_labor_result.json", "AI_LABOR")):
        result = m.build_deep_pilot_v2(key, path, key)
        for name, node in result["nodes"].items():
            if node["status"] == "SUPPORTED":
                assert node["document_id"], f"{name} SUPPORTED without document_id"


def test_not_found_node_always_carries_a_gap_type():
    result = m.build_deep_pilot_v2("AI_LABOR", "deep_pilot_ai_labor_result.json", "AI_LABOR")
    for name, node in result["nodes"].items():
        if node["status"] == "NOT_FOUND":
            assert "gap_type" in node, f"{name} is NOT_FOUND without a gap_type"
            assert node["gap_type"] in m._query_planner.NOT_FOUND_GAP_CLASSES


def test_policy_research_context_honestly_not_found_when_no_such_source_registered():
    result = m.build_deep_pilot_v2("AI_ENERGY_INFRA", "deep_pilot_result.json", "AI_ENERGY_INFRA")
    node = result["nodes"]["POLICY_RESEARCH_CONTEXT"]
    assert node["status"] == "NOT_FOUND"
    assert node["gap_type"] == "SOURCE_GAP"


def test_geographic_context_never_claims_event_location_from_publisher_language():
    result = m.build_deep_pilot_v2("AI_LABOR", "deep_pilot_ai_labor_result.json", "AI_LABOR")
    node = result["nodes"]["GEOGRAPHIC_CONTEXT"]
    assert node["status"] == "NOT_FOUND"
    assert "jurisdiction" in node["reason"]


def test_missing_old_pilot_file_raises_rather_than_fabricating():
    try:
        m.build_deep_pilot_v2("FAKE", "does_not_exist.json", "FAKE")
        assert False
    except FileNotFoundError:
        pass


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
