import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import incremental_update as m  # noqa: E402


def test_find_affected_objects_filters_by_topic_only():
    objects = {
        "i1": {"topic": "AI_ENERGY_INFRA"},
        "i2": {"topic": "AI_LABOR"},
        "i3": {"topic": "AI_ENERGY_INFRA"},
    }
    affected = m.find_affected_objects("AI_ENERGY_INFRA", objects)
    assert set(affected.keys()) == {"i1", "i3"}


def test_classify_impact_state_changed():
    old = {"current_state": "v1", "counterevidence": [], "uncertainties": [], "known_gaps": []}
    new = {"current_state": "v2", "counterevidence": [], "uncertainties": [], "known_gaps": []}
    assert m.classify_impact(old, new) == "STATE_CHANGED"


def test_classify_impact_no_change():
    old = {"current_state": "v1", "counterevidence": [], "uncertainties": [], "known_gaps": []}
    new = {"current_state": "v1", "counterevidence": [], "uncertainties": [], "known_gaps": []}
    assert m.classify_impact(old, new) == "NEW_EVIDENCE_NO_CHANGE"


def test_classify_impact_gap_closed():
    old = {"current_state": "v1", "counterevidence": [], "uncertainties": [], "known_gaps": ["g1"]}
    new = {"current_state": "v1", "counterevidence": [], "uncertainties": [], "known_gaps": []}
    assert m.classify_impact(old, new) == "GAP_CLOSED"


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
