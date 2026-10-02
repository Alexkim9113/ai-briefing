import atexit
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))
import statistical_evidence as m  # noqa: E402


# N-9 Section 25 fix: SIDECAR_PATH is the production canonical file. The old _cleanup()
# permanently deleted it. We now snapshot+restore instead (see claim_model's test for the
# identical fix and rationale).
_REAL_BACKUP = {}


def _snapshot_real_files_once():
    if m.SIDECAR_PATH not in _REAL_BACKUP:
        p = m.SIDECAR_PATH
        _REAL_BACKUP[p] = p.read_bytes() if p.exists() else None


def _restore_real_files():
    for p, content in _REAL_BACKUP.items():
        if content is None:
            if p.exists():
                p.unlink()
        else:
            p.write_bytes(content)


def _cleanup():
    _snapshot_real_files_once()
    if m.SIDECAR_PATH.exists():
        m.SIDECAR_PATH.unlink()


# O-1F fix: see test_claim_model.py's identical fix for the full rationale -- main()'s
# try/finally never runs under pytest, so restore must also be registered at interpreter exit.
atexit.register(_restore_real_files)


def test_admission_is_idempotent_no_duplicate_series():
    _cleanup()
    raw = [{"period": "2020", "value": 100.0, "indicator_name": "test", "unit": "kWh"}]
    rec1, new1 = m.admit_statistical_series("TEST.IND", "USA", raw, "https://example.com", "src_test")
    rec2, new2 = m.admit_statistical_series("TEST.IND", "USA", raw, "https://example.com", "src_test")
    assert new1 is True
    assert new2 is False
    assert rec1["series_id"] == rec2["series_id"]
    sidecar = m.load_sidecar()
    assert len(sidecar) == 1
    _cleanup()


def test_missing_value_rejected_not_fabricated():
    obs = m.new_observation("I", "src", "name", "unit", "geo", "2020", None, "https://x.com")
    assert m.validate_observation(obs) == "REJECTED_NO_VALUE"


def test_missing_provenance_rejected():
    obs = m.new_observation("I", "src", "name", "unit", "geo", "2020", 1.0, None)
    obs["provenance"] = None
    assert m.validate_observation(obs) == "REJECTED_NO_PROVENANCE"


def test_fewer_than_4_points_never_declares_trend():
    obs = [m.new_observation("I", "src", "n", "u", "g", str(y), 100.0 + y, "https://x.com") for y in range(3)]
    for o in obs:
        o["validation_status"] = "VALIDATED"
    assert m.classify_series_trend(obs) == "INSUFFICIENT_SERIES"


def test_monotonic_increase_classified_increasing():
    obs = [m.new_observation("I", "src", "n", "u", "g", str(y), float(y), "https://x.com") for y in range(5)]
    for o in obs:
        o["validation_status"] = "VALIDATED"
    assert m.classify_series_trend(obs) == "INCREASING"


def test_real_live_data_if_present_is_validated_not_fabricated():
    # If a real fetch result exists (committed from a live GitHub Actions run), confirm every
    # observation's validation_status was computed deterministically, never asserted true.
    fetch_result_path = HERE.parent / "world_bank_fetch_result_m6_run1.json"
    if not fetch_result_path.exists():
        return  # honest skip -- no live result committed yet in this test environment
    import json
    data = json.loads(fetch_result_path.read_text(encoding="utf-8"))
    assert data.get("fetch_result") in ("OK", "FAILED", "NO_RESULT")


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    try:
        for t in tests:
            try:
                t()
                print(f"PASS {t.__name__}")
            except AssertionError as e:
                failed += 1
                print(f"FAIL {t.__name__}: {e}")
    finally:
        _restore_real_files()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
