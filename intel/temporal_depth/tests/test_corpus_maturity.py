# PHASE M.5A Part 2 — Priority 10/11: corpus_maturity tests. Real-corpus smoke test only
# (this module reads real files by design -- it IS the maturity report), plus a fixture-style
# structural check that UNKNOWN fields stay UNKNOWN rather than silently becoming 0.
import importlib.util
import sys
from pathlib import Path

MOD_DIR = Path(__file__).resolve().parents[1]


def _load():
    key = "m5a_corpus_maturity"
    if key in sys.modules:
        del sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, MOD_DIR / "corpus_maturity.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


def test_real_corpus_maturity_computes_without_crash():
    cm = _load()
    m = cm.compute_corpus_maturity()
    assert m["total_documents"] > 500
    assert m["production_event_count"] == 28  # verified baseline (Part 1 report)
    assert m["change_count"] == 0
    assert m["signal_count"] == 0
    assert m["pattern_count"] == 0
    assert m["structural_analysis_count"] == 0


def test_unknown_fields_stay_unknown_not_zero():
    cm = _load()
    m = cm.compute_corpus_maturity()
    assert m["possible_duplicates"] == cm.UNKNOWN
    assert m["source_family_count"] == cm.UNKNOWN
    assert m["historical_evidence_count"] == cm.UNKNOWN
    assert m["knowledge_gap_count"] == cm.UNKNOWN


def test_primary_source_ratio_is_consistent_with_counts():
    cm = _load()
    m = cm.compute_corpus_maturity()
    expected = round((m["primary_source_count"]) / m["total_documents"], 4)
    assert m["primary_source_ratio"] == expected


def test_geography_known_plus_unknown_equals_total():
    cm = _load()
    m = cm.compute_corpus_maturity()
    assert m["geography_known"] + m["geography_unknown"] == m["total_documents"]


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
