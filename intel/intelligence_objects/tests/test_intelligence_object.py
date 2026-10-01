import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))
import intelligence_object as m  # noqa: E402


def _cleanup():
    if m.OBJECTS_PATH.exists():
        m.OBJECTS_PATH.unlink()


def test_identity_stable_for_same_topic_question():
    o1 = m.new_intelligence_object("AI_ENERGY_INFRA", "is AI driving electricity demand growth?")
    o2 = m.new_intelligence_object("AI_ENERGY_INFRA", "is AI driving electricity demand growth?")
    assert o1["intelligence_id"] == o2["intelligence_id"]


def test_revision_history_never_overwritten_only_appended():
    _cleanup()
    obj = m.new_intelligence_object("AI_ENERGY_INFRA", "q")
    obj["current_state"] = "v1 state"
    m.upsert_intelligence_object(obj)
    obj["current_state"] = "v2 state"
    m.upsert_intelligence_object(obj, trigger_evidence="ev1", changed_fields=["current_state"],
                                  change_reason="new evidence", impact_event="STATE_CHANGED")
    objects = m.load_intelligence_objects()
    stored = objects[obj["intelligence_id"]]
    assert stored["version"] == 2
    assert len(stored["revision_history"]) == 1
    assert stored["revision_history"][0]["snapshot_current_state"] == "v1 state"
    _cleanup()


def test_empty_evidence_arrays_stay_empty_not_backfilled():
    obj = m.new_intelligence_object("AI_LABOR", "q")
    assert obj["counterevidence"] == []
    assert obj["known_gaps"] == []


def test_impact_event_types_are_named_vocabulary():
    assert "STATE_CHANGED" in m.IMPACT_EVENT_TYPES
    assert "NEW_EVIDENCE_NO_CHANGE" in m.IMPACT_EVENT_TYPES


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
