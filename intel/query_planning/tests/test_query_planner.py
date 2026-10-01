import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))
import query_planner as m  # noqa: E402


def test_every_evidence_type_has_a_distinct_source_class_routing():
    routings = {et: m.route_evidence_type_to_source_classes(et) for et in m.EVIDENCE_TYPES}
    # No two Evidence Types may route to the exact same source-class list -- that would mean
    # this module collapsed back into "one keyword set reused everywhere" (the failure mode
    # Te's spec exists to stop).
    seen = set()
    for et, classes in routings.items():
        key = tuple(classes)
        assert key not in seen, f"{et} duplicates another Evidence Type's routing"
        seen.add(key)


def test_route_unknown_evidence_type_raises_rather_than_defaulting():
    try:
        m.route_evidence_type_to_source_classes("NOT_A_REAL_TYPE")
        assert False, "should have raised"
    except ValueError:
        pass


def test_all_routed_source_classes_are_real_source_types():
    for et in m.EVIDENCE_TYPES:
        for cls in m.route_evidence_type_to_source_classes(et):
            assert cls in m.SOURCE_TYPES, f"{et} routes to unknown source class {cls!r}"


def test_transition_query_plan_has_explicit_temporal_structure():
    plan = m.build_query_plan("TRANSITION", ["AI energy demand"], date_range=("2023", "2026"))
    assert plan["evidence_type"] == "TRANSITION"
    assert any("2023" in q for q in plan["queries"])
    assert any("2026" in q for q in plan["queries"])


def test_counterevidence_query_plan_takes_hypothesis_as_input_not_guessed():
    plan = m.build_query_plan("COUNTEREVIDENCE", ["AI job losses are accelerating"])
    assert all("AI job losses are accelerating" in q for q in plan["queries"])


def test_build_query_plan_rejects_unknown_evidence_type():
    try:
        m.build_query_plan("MADE_UP", ["x"])
        assert False
    except ValueError:
        pass


def test_query_expansion_is_search_aid_only_registered_topics_only():
    terms = m.expand_query_terms("AI_ENERGY_INFRA")
    assert "data center electricity demand" in terms
    assert len(terms) > 5
    # Unregistered topic -> honestly empty, never auto-generated.
    assert m.expand_query_terms("TOTALLY_UNREGISTERED_TOPIC") == ()


def test_ai_labor_is_registered_as_coequal_pilot_expansion():
    terms = m.expand_query_terms("AI_LABOR")
    assert "job displacement" in terms
    assert "employment statistics" in terms


def test_entity_expansion_only_returns_entities_from_real_events_never_fabricated():
    events = {
        "e1": {"event_name": "Nvidia announces new chip", "entities": ["Nvidia"]},
        "e2": {"event_name": "Unrelated weather report", "entities": ["NOAA"]},
    }
    result = m.expand_entities_for_topic(["nvidia"], events=events)
    assert result == {"Nvidia": 1}


def test_entity_expansion_empty_when_no_matching_events_not_padded():
    events = {"e1": {"event_name": "Unrelated story", "entities": ["Someone"]}}
    result = m.expand_entities_for_topic(["totally unmatched topic string"], events=events)
    assert dict(result) == {}


def test_real_corpus_entity_expansion_runs_without_crash():
    result = m.expand_entities_for_topic(["ai"])
    assert isinstance(result, type(m.Counter()))


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
