#!/usr/bin/env python3
# PHASE 5B — Synthetic Fixture Test. 운영자 지시 24번: 실제 데이터와 완전히 분리된 테스트에서만
# 가상 Change/Signal을 만들어 검증한다. 이 파일은 격리된 임시 디렉터리에만 쓰고,
# intel/pattern_layer/patterns.json 등 실제 산출물은 절대 읽거나 쓰지 않는다.
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAYER_DIR = HERE.parent
sys.path.insert(0, str(LAYER_DIR))

from run_pilot import run  # noqa: E402


def _change(change_id, entities, domains, direction="EXPANDING", status="STABLE",
            event_count=3, first_seen="2026-09-27", last_seen="2026-09-29"):
    return {
        "change_id": change_id, "change_name": f"{change_id} 변화", "direction": direction,
        "status": status, "override_status": "AUTO_CANDIDATE",
        "event_count": event_count, "entity_diversity": len(entities),
        "domain_diversity": len(domains), "evidence_strength": 5, "change_confidence": "MEDIUM",
        "supporting_event_ids": [f"evt_{change_id}_{i}" for i in range(event_count)],
        "contradicting_event_ids": [],
        "entities": entities, "domains": domains, "topics": domains,
        "first_seen": first_seen, "last_seen": last_seen,
        "updated_at": "2026-09-29T00:00:00+00:00",
    }


def _signal(signal_id, change_ids, signal_type="STRENGTHENING", status="CANDIDATE"):
    return {
        "signal_id": signal_id, "signal_type": signal_type, "change_ids": change_ids,
        "status": status, "override_status": "AUTO_DETECTED",
    }


def _isolated_dir():
    return Path(tempfile.mkdtemp(prefix="pattern_layer_fixture_"))


def _run(changes, signals=None, out_dir=None):
    out_dir = out_dir or _isolated_dir()
    return run(changes_override=changes, signals_override=signals or {}, out_dir=out_dir,
               previous_snapshot_path=out_dir / "patterns.json",
               overrides_path=out_dir / "pattern_overrides.json"), out_dir


def test_1_three_independent_changes_same_mechanism_creates_pattern():
    """서로 다른 Change 3개에서 ACCESS 구조(동일 relation+dimension) 반복 → Pattern candidate 생성."""
    changes = {
        "chg_a": _change("chg_a", ["CompanyA"], ["PRODUCT_RELEASE"]),
        "chg_b": _change("chg_b", ["CompanyB"], ["PRODUCT_RELEASE"]),
        "chg_c": _change("chg_c", ["CompanyC"], ["PRODUCT_RELEASE"]),
    }
    (metrics, patterns), out_dir = _run(changes)
    try:
        assert metrics["patterns_total"] == 1, f"3개 독립 Change 동일 mechanism인데 Pattern 미생성: {metrics}"
        pat = next(iter(patterns.values()))
        assert pat["change_count"] == 3
        assert set(pat["supporting_change_ids"]) == {"chg_a", "chg_b", "chg_c"}
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_2_same_change_multiple_signals_no_pattern():
    """동일 Change에서 파생된 Signal 3개 → 독립 Change가 1개뿐이므로 Pattern 생성 금지."""
    changes = {"chg_a": _change("chg_a", ["CompanyA"], ["PRODUCT_RELEASE"])}
    signals = {
        "sig_1": _signal("sig_1", ["chg_a"], "STRENGTHENING"),
        "sig_2": _signal("sig_2", ["chg_a"], "ENTITY_SPREAD"),
        "sig_3": _signal("sig_3", ["chg_a"], "CROSS_DOMAIN_SPREAD"),
    }
    (metrics, patterns), out_dir = _run(changes, signals)
    try:
        assert metrics["patterns_total"] == 0, f"단일 Change에서 Pattern이 생성됨(금지): {metrics}"
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_3_same_topic_different_mechanism_no_pattern():
    """동일 Topic(domain)이지만 방향(mechanism/relation)이 다르면 Pattern 생성 금지."""
    changes = {
        "chg_a": _change("chg_a", ["CompanyA"], ["PRODUCT_RELEASE"], direction="EXPANDING"),
        "chg_b": _change("chg_b", ["CompanyB"], ["PRODUCT_RELEASE"], direction="CONTRACTING"),
    }
    (metrics, patterns), out_dir = _run(changes)
    try:
        assert metrics["patterns_total"] == 0, f"mechanism이 다른데 Pattern 생성됨: {metrics}"
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_4_cross_domain_same_mechanism_creates_pattern():
    """서로 다른 Domain(MODEL_RELEASE / REGULATORY_ACTION)이지만 같은 dimension(CONTROL)+relation
    이면 Cross-domain Pattern이 가능해야 한다."""
    changes = {
        "chg_a": _change("chg_a", ["CompanyA"], ["MODEL_RELEASE"], direction="EXPANDING"),
        "chg_b": _change("chg_b", ["GovX"], ["REGULATORY_ACTION"], direction="EXPANDING"),
    }
    (metrics, patterns), out_dir = _run(changes)
    try:
        assert metrics["patterns_total"] == 1
        pat = next(iter(patterns.values()))
        assert pat["pattern_type"] == "CROSS_DOMAIN_MECHANISM"
        assert pat["domain_diversity"] == 2
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_5_counter_evidence_preserved_not_deleted():
    """반대증거(opposite relation, 같은 dimension)가 나타나도 Pattern이 삭제되지 않고
    contradicting_change_ids에 기록되어야 한다."""
    changes = {
        "chg_a": _change("chg_a", ["CompanyA"], ["PRODUCT_RELEASE"], direction="EXPANDING"),
        "chg_b": _change("chg_b", ["CompanyB"], ["PRODUCT_RELEASE"], direction="EXPANDING"),
        "chg_c": _change("chg_c", ["CompanyC"], ["PRODUCT_RELEASE"], direction="EXPANDING"),
        "chg_counter": _change("chg_counter", ["CompanyD"], ["PRODUCT_RELEASE"], direction="CONTRACTING"),
    }
    (metrics, patterns), out_dir = _run(changes)
    try:
        assert metrics["patterns_total"] == 1
        pat = next(iter(patterns.values()))
        assert pat["status"] != "REJECTED"
        assert "chg_counter" in pat["contradicting_change_ids"], "반대증거가 기록되지 않음"
        assert pat["change_count"] == 3, "반대증거가 supporting evidence로 잘못 섞임"
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_6_human_reject_preserved_on_rerun():
    """Human reject 이후 재실행해도 REJECTED 상태가 유지되어야 한다."""
    out_dir = _isolated_dir()
    try:
        changes = {
            "chg_a": _change("chg_a", ["CompanyA"], ["PRODUCT_RELEASE"]),
            "chg_b": _change("chg_b", ["CompanyB"], ["PRODUCT_RELEASE"]),
        }
        signals_path = out_dir / "patterns.json"
        overrides_path = out_dir / "pattern_overrides.json"
        metrics1, patterns1 = run(changes_override=changes, signals_override={}, out_dir=out_dir,
                                   previous_snapshot_path=signals_path, overrides_path=overrides_path)
        pid = next(iter(patterns1.keys()))

        overrides_path.write_text(json.dumps({"human_confirmed": [], "human_rejected": [pid]}), encoding="utf-8")
        metrics2, patterns2 = run(changes_override=changes, signals_override={}, out_dir=out_dir,
                                   previous_snapshot_path=signals_path, overrides_path=overrides_path)
        assert patterns2[pid]["override_status"] == "HUMAN_REJECTED"
        assert patterns2[pid]["status"] == "REJECTED"

        # 3차 재실행(자동 재계산)에서도 REJECTED가 자동으로 뒤집히면 안 된다.
        metrics3, patterns3 = run(changes_override=changes, signals_override={}, out_dir=out_dir,
                                   previous_snapshot_path=signals_path, overrides_path=overrides_path)
        assert patterns3[pid]["status"] == "REJECTED", "자동 재실행이 Human Reject를 덮어씀"
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_7_empty_input_zero_patterns():
    """Change/Signal이 없으면 Pattern도 0개여야 한다(가짜 생성 금지)."""
    (metrics, patterns), out_dir = _run({}, {})
    try:
        assert metrics["patterns_total"] == 0
        assert patterns == {}
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_8_rerun_idempotent():
    """동일 입력으로 재실행해도 Pattern 개수와 change_count가 동일해야 한다(멱등성)."""
    out_dir = _isolated_dir()
    try:
        changes = {
            "chg_a": _change("chg_a", ["CompanyA"], ["PRODUCT_RELEASE"]),
            "chg_b": _change("chg_b", ["CompanyB"], ["PRODUCT_RELEASE"]),
            "chg_c": _change("chg_c", ["CompanyC"], ["PRODUCT_RELEASE"]),
        }
        signals_path = out_dir / "patterns.json"
        overrides_path = out_dir / "pattern_overrides.json"
        m1, p1 = run(changes_override=changes, signals_override={}, out_dir=out_dir,
                     previous_snapshot_path=signals_path, overrides_path=overrides_path)
        m2, p2 = run(changes_override=changes, signals_override={}, out_dir=out_dir,
                     previous_snapshot_path=signals_path, overrides_path=overrides_path)
        assert m1["patterns_total"] == m2["patterns_total"]
        pid = next(iter(p1.keys()))
        assert pid in p2, "재실행 시 동일 pattern_id가 유지되지 않음"
        assert p1[pid]["change_count"] == p2[pid]["change_count"]
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


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
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return failed == 0


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)
