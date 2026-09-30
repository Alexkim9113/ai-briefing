# PHASE M.5A Part 2 — Priority 5/11: gap_source_map tests. SYNTHETIC-SCHEMA-VERIFIED.
import importlib.util
import sys
from pathlib import Path

MOD_DIR = Path(__file__).resolve().parents[1]


def _load():
    key = "m5a_gap_source_map"
    if key in sys.modules:
        del sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, MOD_DIR / "gap_source_map.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


def test_all_gap_types_covered_no_keyerror():
    gm = _load()
    for gap in gm.GAP_TYPES:
        result = gm.candidates_for_gap(gap)
        assert isinstance(result, list)


def test_unknown_gap_type_raises_not_silently_empty():
    gm = _load()
    try:
        gm.candidates_for_gap("NOT_A_REAL_GAP_TYPE")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_missing_official_statistics_includes_world_bank_verified():
    gm = _load()
    result = gm.candidates_for_gap("MISSING_OFFICIAL_STATISTICS")
    names = [c["source_name"] for c in result]
    assert "World Bank Indicators API" in names
    wb = next(c for c in result if c["source_name"] == "World Bank Indicators API")
    assert wb["source_tier"] == "TIER_1"


def test_returned_candidates_are_copies_not_shared_mutable_state():
    gm = _load()
    a = gm.candidates_for_gap("MISSING_OFFICIAL_STATISTICS")
    a[0]["source_name"] = "MUTATED"
    b = gm.candidates_for_gap("MISSING_OFFICIAL_STATISTICS")
    assert b[0]["source_name"] != "MUTATED"


def test_no_candidate_claims_reachability_that_was_not_actually_verified():
    """Every candidate's network_status must be an honest, closed-vocabulary value -- never a
    free-text optimistic claim."""
    gm = _load()
    allowed = {"VERIFIED_REACHABLE_IN_GHA_M3", "SANDBOX_BLOCKED_CONFIRMED_403",
               "SCHEMA_CHANGED_NOT_THIS_PHASE", "NOT_APPLICABLE"}
    for gap in gm.GAP_TYPES:
        for c in gm.candidates_for_gap(gap):
            assert c["network_status"] in allowed, c


def run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {t.__name__}: {e!r}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return failed == 0


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)
