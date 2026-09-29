#!/usr/bin/env python3
# PHASE 5A — Synthetic Fixture Test. 운영자 명시적 지시: "Synthetic Change를 만들어 실제
# signals.json에 섞지 마세요. 필요하면 test fixture로만 별도 테스트하세요." 이 파일은 오직
# 격리된 임시 디렉터리에만 쓰고, intel/signal_layer/signals.json 등 실제 산출물은 절대
# 읽거나 쓰지 않는다. 순수 코드 검증(LLM 미사용).
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAYER_DIR = HERE.parent
sys.path.insert(0, str(LAYER_DIR))

from run_pilot import run  # noqa: E402
from detection import detect_signals_for_change  # noqa: E402


def _synthetic_change(change_id="chg_synthetic_0001", event_count=3, entity_diversity=2,
                       domain_diversity=1, direction="EXPANDING", status="STABLE",
                       contradicting=None, updated_at="2026-09-29T00:00:00+00:00"):
    return {
        "change_id": change_id, "change_name": "합성 테스트 변화", "direction": direction,
        "status": status, "override_status": "AUTO_CANDIDATE",
        "event_count": event_count, "entity_diversity": entity_diversity,
        "domain_diversity": domain_diversity, "evidence_strength": 5, "change_confidence": "MEDIUM",
        "supporting_event_ids": [f"evt_{i}" for i in range(event_count)],
        "contradicting_event_ids": contradicting or [],
        "entities": ["EntityA", "EntityB"], "domains": ["TECH"], "topics": ["TECH"],
        "first_seen": "2026-09-27", "last_seen": "2026-09-29", "updated_at": updated_at,
    }


def _isolated_dir():
    d = Path(tempfile.mkdtemp(prefix="signal_layer_fixture_"))
    return d


def test_empty_state_zero_changes():
    """Change가 하나도 없으면 Signal도 0개여야 한다."""
    out_dir = _isolated_dir()
    try:
        metrics, signals = run(changes_override={}, out_dir=out_dir,
                                previous_snapshot_path=out_dir / "signals.json",
                                overrides_path=out_dir / "signal_overrides.json")
        assert metrics["signals_created"] == 0, "빈 Change 입력인데 Signal이 생성됨"
        assert signals == {}
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_new_change_produces_new_change_signal():
    """최초 관측된 Change 1개 → NEW_CHANGE Signal 1개."""
    out_dir = _isolated_dir()
    try:
        change = _synthetic_change()
        metrics, signals = run(changes_override={change["change_id"]: change}, out_dir=out_dir,
                                previous_snapshot_path=out_dir / "signals.json",
                                overrides_path=out_dir / "signal_overrides.json")
        assert metrics["signals_created"] == 1
        sig = next(iter(signals.values()))
        assert sig["signal_type"] == "NEW_CHANGE"
        assert sig["maturity"] == "WEAK"
        assert sig["change_ids"] == [change["change_id"]]
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_strengthening_requires_baseline_and_memory_upserts():
    """1차 실행(NEW_CHANGE) → 2차 실행에서 event_count 증가 → 같은 change_id가 새 signal_id로
    STRENGTHENING을 만들고, 재실행 시 새 signal_id를 또 만들지 않고 UPDATE(메모리 패턴)한다."""
    out_dir = _isolated_dir()
    try:
        change_id = "chg_synthetic_0002"
        signals_path = out_dir / "signals.json"
        overrides_path = out_dir / "signal_overrides.json"

        change_v1 = _synthetic_change(change_id=change_id, event_count=2)
        m1, signals_v1 = run(changes_override={change_id: change_v1}, out_dir=out_dir,
                              previous_snapshot_path=signals_path, overrides_path=overrides_path)
        assert m1["signals_created"] == 1
        assert any(s["signal_type"] == "NEW_CHANGE" for s in signals_v1.values())

        change_v2 = _synthetic_change(change_id=change_id, event_count=5,
                                       updated_at="2026-09-30T00:00:00+00:00")
        m2, signals_v2 = run(changes_override={change_id: change_v2}, out_dir=out_dir,
                              previous_snapshot_path=signals_path, overrides_path=overrides_path)
        types_v2 = {s["signal_type"] for s in signals_v2.values()}
        assert "STRENGTHENING" in types_v2, f"event_count 2->5인데 STRENGTHENING 미감지: {types_v2}"

        strengthening_sig = next(s for s in signals_v2.values() if s["signal_type"] == "STRENGTHENING")
        assert strengthening_sig["baseline"]["previous_state"]["event_count"] == 2
        assert strengthening_sig["baseline"]["current_state"]["event_count"] == 5

        # 3차 실행(동일 v2 재실행, idempotency) — 같은 signal_id가 새로 생기지 않고 status_history만
        # 늘어나야 한다(운영자 지시: 같은 Signal 재감지 시 UPDATE, 재생성 금지).
        sid_before = strengthening_sig["signal_id"]
        m3, signals_v3 = run(changes_override={change_id: change_v2}, out_dir=out_dir,
                              previous_snapshot_path=signals_path, overrides_path=overrides_path)
        assert sid_before in signals_v3, "재실행 시 동일 signal_id가 유지되지 않음(메모리 upsert 실패)"
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_counter_evidence_never_deletes_signal():
    """반대증거가 늘어나도 Signal이 삭제되지 않고 COUNTER_EVIDENCE_RISING으로 표현되어야 한다."""
    out_dir = _isolated_dir()
    try:
        change_id = "chg_synthetic_0003"
        signals_path = out_dir / "signals.json"
        overrides_path = out_dir / "signal_overrides.json"

        change_v1 = _synthetic_change(change_id=change_id, event_count=3, contradicting=[])
        run(changes_override={change_id: change_v1}, out_dir=out_dir,
            previous_snapshot_path=signals_path, overrides_path=overrides_path)

        change_v2 = _synthetic_change(change_id=change_id, event_count=3,
                                       contradicting=["evt_counter_1"],
                                       updated_at="2026-09-30T00:00:00+00:00")
        metrics, signals = run(changes_override={change_id: change_v2}, out_dir=out_dir,
                                previous_snapshot_path=signals_path, overrides_path=overrides_path)
        types = {s["signal_type"] for s in signals.values()}
        assert "COUNTER_EVIDENCE_RISING" in types
        assert metrics["signals_created"] >= 1, "반대증거 발생 시 Signal이 사라짐(금지된 동작)"
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_human_override_rejection_preserved_on_rerun():
    """HUMAN_REJECTED override는 자동 재실행이 덮어쓰지 않아야 한다."""
    out_dir = _isolated_dir()
    try:
        change_id = "chg_synthetic_0004"
        signals_path = out_dir / "signals.json"
        overrides_path = out_dir / "signal_overrides.json"

        change = _synthetic_change(change_id=change_id)
        _, signals_v1 = run(changes_override={change_id: change}, out_dir=out_dir,
                             previous_snapshot_path=signals_path, overrides_path=overrides_path)
        sid = next(iter(signals_v1.keys()))

        overrides_path.write_text(json.dumps({"human_confirmed": [], "human_rejected": [sid]}), encoding="utf-8")

        _, signals_v2 = run(changes_override={change_id: change}, out_dir=out_dir,
                             previous_snapshot_path=signals_path, overrides_path=overrides_path)
        assert signals_v2[sid]["override_status"] == "HUMAN_REJECTED"
        assert signals_v2[sid]["status"] == "REJECTED"
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_no_signal_generated_directly_from_event_or_volume():
    """detect_signals_for_change는 Change 딕셔너리만 입력받고, Event 리스트나 원문 기사 수를
    직접 받는 파라미터가 없다는 것을 구조적으로 확인(Acceptance 2,3번)."""
    import inspect
    sig = inspect.signature(detect_signals_for_change)
    params = list(sig.parameters.keys())
    assert params == ["change", "previous_snapshot"], f"예상 밖의 입력 파라미터: {params}"


def run_all():
    tests = [v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)]
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
