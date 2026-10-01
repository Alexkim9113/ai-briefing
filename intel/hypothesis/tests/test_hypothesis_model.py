import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))
import hypothesis_model as m  # noqa: E402


def _cleanup():
    if m.HYPOTHESES_PATH.exists():
        m.HYPOTHESES_PATH.unlink()


def test_identity_stable():
    h1 = m.new_hypothesis("AI_ENERGY_INFRA", "AI data centers drive electricity demand growth")
    h2 = m.new_hypothesis("AI_ENERGY_INFRA", "AI data centers drive electricity demand growth")
    assert h1["hypothesis_id"] == h2["hypothesis_id"]


def test_no_evidence_is_insufficient_not_open():
    assert m.classify_status([], []) == "INSUFFICIENT_EVIDENCE"


def test_counterevidence_never_deleted_only_appended():
    _cleanup()
    h = m.new_hypothesis("AI_ENERGY_INFRA", "test hyp")
    h = m.upsert_hypothesis(h, new_support_id="ev1")
    assert h["status"] == "SUPPORTED"
    h = m.upsert_hypothesis(h, new_counterevidence_id="ev2")
    assert h["supporting_evidence"] == ["ev1"], "support must still be present, never dropped"
    assert h["contradicting_evidence"] == ["ev2"]
    assert h["status"] == "CONTESTED"
    _cleanup()


def test_status_is_named_vocabulary_only():
    for s in ("SUPPORTED", "WEAKENED", "REJECTED", "CONTESTED"):
        assert s in m.HYPOTHESIS_STATUSES


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
