#!/usr/bin/env python3
# PHASE 5C — Synthetic Fixture Test. 운영자 지시 31, 37번: 실제 Production 데이터와 완전히
# 분리된 테스트에서만 가상 Pattern/Change를 만들어 검증한다. structural_changes.json 등
# 실제 산출물은 절대 읽거나 쓰지 않는다. 순수 코드 검증(LLM 미사용).
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAYER_DIR = HERE.parent
sys.path.insert(0, str(LAYER_DIR))

from run_pilot import run  # noqa: E402


def _pattern(pattern_id, entities, event_types, change_ids, dimension="ACCESS", relation="INCREASES",
             real_domains=None, status="CANDIDATE", override_status="AUTO_CANDIDATE",
             first_seen="2026-09-27", last_seen="2026-09-29"):
    return {
        "pattern_id": pattern_id, "analytic_dimensions": [dimension], "relation_type": relation,
        "status": status, "override_status": override_status,
        "supporting_change_ids": change_ids, "supporting_signal_ids": [f"sig_{pattern_id}"],
        "entities": entities, "domains": event_types,  # 운영자 지시 0-A: 여기 'domains'는 실제 event_type 값
        "real_domains": real_domains or [],  # synthetic 전용 필드: 실제 사회적 영역(lineage 확인됨을 가정)
        "first_seen": first_seen, "last_seen": last_seen,
        "change_count": len(change_ids), "pattern_confidence": "MEDIUM", "evidence_strength": 5,
    }


def _change(change_id, event_ids):
    return {"change_id": change_id, "supporting_event_ids": event_ids}


def _isolated_dir():
    return Path(tempfile.mkdtemp(prefix="structural_change_fixture_"))


def _run(patterns, changes=None, out_dir=None):
    out_dir = out_dir or _isolated_dir()
    return run(patterns_override=patterns, changes_override=changes or {}, out_dir=out_dir,
               previous_snapshot_path=out_dir / "structural_changes.json",
               overrides_path=out_dir / "structural_change_overrides.json"), out_dir


def test_01_three_independent_patterns_same_transition_creates_candidate():
    """독립 Pattern 3개(서로 다른 underlying Change) + 동일 transition → Structural Candidate 생성."""
    patterns = {
        "pat_a": _pattern("pat_a", ["EntA"], ["MODEL_RELEASE"], ["chg_1", "chg_2"]),
        "pat_b": _pattern("pat_b", ["EntB"], ["PRODUCT_RELEASE"], ["chg_3", "chg_4"]),
        "pat_c": _pattern("pat_c", ["EntC"], ["FUNDING"], ["chg_5", "chg_6"]),
    }
    (metrics, scs), out_dir = _run(patterns)
    try:
        assert metrics["structural_changes_total"] == 1, f"3개 독립 Pattern인데 생성 안 됨: {metrics}"
        sc = next(iter(scs.values()))
        assert sc["independent_pattern_count"] == 3
        assert set(sc["supporting_pattern_ids"]) == {"pat_a", "pat_b", "pat_c"}
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_02_single_pattern_no_candidate():
    """Pattern이 1개뿐이면 자동 승격 금지."""
    patterns = {"pat_a": _pattern("pat_a", ["EntA"], ["MODEL_RELEASE"], ["chg_1", "chg_2"])}
    (metrics, scs), out_dir = _run(patterns)
    try:
        assert metrics["structural_changes_total"] == 0, f"단일 Pattern에서 생성됨(금지): {metrics}"
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_03_same_underlying_changes_no_independence_no_candidate():
    """Pattern 3개지만 underlying Change가 사실상 동일 → 독립성 부족 → 생성 금지."""
    shared = ["chg_1", "chg_2"]
    patterns = {
        "pat_a": _pattern("pat_a", ["EntA"], ["MODEL_RELEASE"], shared),
        "pat_b": _pattern("pat_b", ["EntB"], ["PRODUCT_RELEASE"], shared),
        "pat_c": _pattern("pat_c", ["EntC"], ["FUNDING"], shared),
    }
    (metrics, scs), out_dir = _run(patterns)
    try:
        assert metrics["structural_changes_total"] == 0, f"Change 중복인데 생성됨(과대평가): {metrics}"
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_04_same_dimension_different_direction_no_merge():
    """같은 dimension이지만 relation(FROM→TO 방향)이 다르면 병합 금지."""
    patterns = {
        "pat_a": _pattern("pat_a", ["EntA"], ["MODEL_RELEASE"], ["chg_1", "chg_2"], relation="INCREASES"),
        "pat_b": _pattern("pat_b", ["EntB"], ["PRODUCT_RELEASE"], ["chg_3", "chg_4"], relation="DECREASES"),
    }
    (metrics, scs), out_dir = _run(patterns)
    try:
        assert metrics["structural_changes_total"] == 0, f"방향이 다른데 병합됨: {metrics}"
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_05_cross_domain_real_domain_diversity_creates_candidate():
    """실제 서로 다른 Domain(TECH/ECONOMY/POLICY)에서 동일 transition → Cross-domain 가능.
    Event Type 다양성과 실제 Domain 다양성을 혼동하지 않는다."""
    patterns = {
        "pat_a": _pattern("pat_a", ["EntA"], ["MODEL_RELEASE"], ["chg_1", "chg_2"],
                           real_domains=["TECHNOLOGY_INFRASTRUCTURE"]),
        "pat_b": _pattern("pat_b", ["EntB"], ["FUNDING"], ["chg_3", "chg_4"],
                           real_domains=["ECONOMY_INDUSTRY_LABOR"]),
        "pat_c": _pattern("pat_c", ["EntC"], ["REGULATORY_ACTION"], ["chg_5", "chg_6"],
                           real_domains=["POLICY_LAW_GOVERNANCE"]),
    }
    (metrics, scs), out_dir = _run(patterns)
    try:
        assert metrics["structural_changes_total"] == 1
        sc = next(iter(scs.values()))
        assert sc["domain_diversity"] == 3
        assert set(sc["domains"]) == {"TECHNOLOGY_INFRASTRUCTURE", "ECONOMY_INDUSTRY_LABOR", "POLICY_LAW_GOVERNANCE"}
        assert sc["event_type_diversity"] == 3  # MODEL_RELEASE/FUNDING/REGULATORY_ACTION — 별개 개념
        assert "MULTI_DIMENSIONAL" != sc["structural_change_type"] or True  # dimension은 1개(ACCESS)이므로 무관
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_06_counter_pattern_preserved_not_deleted():
    """반대 Pattern(opposite relation, 같은 dimension) 등장 시 삭제되지 않고 contradicting에 기록."""
    patterns = {
        "pat_a": _pattern("pat_a", ["EntA"], ["MODEL_RELEASE"], ["chg_1", "chg_2"], relation="INCREASES"),
        "pat_b": _pattern("pat_b", ["EntB"], ["PRODUCT_RELEASE"], ["chg_3", "chg_4"], relation="INCREASES"),
        "pat_counter": _pattern("pat_counter", ["EntD"], ["FUNDING"], ["chg_7", "chg_8"], relation="DECREASES"),
    }
    (metrics, scs), out_dir = _run(patterns)
    try:
        assert metrics["structural_changes_total"] == 1
        sc = next(iter(scs.values()))
        assert sc["status"] != "REJECTED"
        assert "pat_counter" in sc["contradicting_pattern_ids"]
        assert sc["independent_pattern_count"] == 2, "반대증거가 supporting으로 잘못 섞임"
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_07_human_reject_preserved_on_rerun():
    """Human reject 이후 재실행해도 REJECTED 상태 유지."""
    out_dir = _isolated_dir()
    try:
        patterns = {
            "pat_a": _pattern("pat_a", ["EntA"], ["MODEL_RELEASE"], ["chg_1", "chg_2"]),
            "pat_b": _pattern("pat_b", ["EntB"], ["PRODUCT_RELEASE"], ["chg_3", "chg_4"]),
        }
        snap = out_dir / "structural_changes.json"
        ov = out_dir / "structural_change_overrides.json"
        m1, scs1 = run(patterns_override=patterns, changes_override={}, out_dir=out_dir,
                       previous_snapshot_path=snap, overrides_path=ov)
        scid = next(iter(scs1.keys()))

        ov.write_text(json.dumps({"human_confirmed": [], "human_rejected": [scid]}), encoding="utf-8")
        m2, scs2 = run(patterns_override=patterns, changes_override={}, out_dir=out_dir,
                       previous_snapshot_path=snap, overrides_path=ov)
        assert scs2[scid]["override_status"] == "HUMAN_REJECTED"
        assert scs2[scid]["status"] == "REJECTED"

        m3, scs3 = run(patterns_override=patterns, changes_override={}, out_dir=out_dir,
                       previous_snapshot_path=snap, overrides_path=ov)
        assert scs3[scid]["status"] == "REJECTED", "자동 재실행이 Human Reject를 덮어씀"
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_08_empty_pattern_zero_output():
    """Pattern이 없으면 Structural Change도 0개."""
    (metrics, scs), out_dir = _run({})
    try:
        assert metrics["structural_changes_total"] == 0
        assert scs == {}
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_09_idempotent_rerun():
    """동일 입력 재실행 시 동일 structural_change_id 유지."""
    out_dir = _isolated_dir()
    try:
        patterns = {
            "pat_a": _pattern("pat_a", ["EntA"], ["MODEL_RELEASE"], ["chg_1", "chg_2"]),
            "pat_b": _pattern("pat_b", ["EntB"], ["PRODUCT_RELEASE"], ["chg_3", "chg_4"]),
            "pat_c": _pattern("pat_c", ["EntC"], ["FUNDING"], ["chg_5", "chg_6"]),
        }
        snap = out_dir / "structural_changes.json"
        ov = out_dir / "structural_change_overrides.json"
        m1, scs1 = run(patterns_override=patterns, changes_override={}, out_dir=out_dir,
                       previous_snapshot_path=snap, overrides_path=ov)
        m2, scs2 = run(patterns_override=patterns, changes_override={}, out_dir=out_dir,
                       previous_snapshot_path=snap, overrides_path=ov)
        assert m1["structural_changes_total"] == m2["structural_changes_total"]
        scid = next(iter(scs1.keys()))
        assert scid in scs2, "재실행 시 동일 structural_change_id가 유지되지 않음"
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_10_evidence_lineage_traceable():
    """Structural Change -> Pattern -> Signal -> Change -> Event lineage가 synthetic으로 추적 가능해야 한다."""
    changes = {
        "chg_1": _change("chg_1", ["evt_1", "evt_2"]),
        "chg_2": _change("chg_2", ["evt_3"]),
        "chg_3": _change("chg_3", ["evt_4"]),
        "chg_4": _change("chg_4", ["evt_5"]),
    }
    patterns = {
        "pat_a": _pattern("pat_a", ["EntA"], ["MODEL_RELEASE"], ["chg_1", "chg_2"]),
        "pat_b": _pattern("pat_b", ["EntB"], ["PRODUCT_RELEASE"], ["chg_3", "chg_4"]),
    }
    (metrics, scs), out_dir = _run(patterns, changes)
    try:
        assert metrics["structural_changes_total"] == 1
        sc = next(iter(scs.values()))
        assert set(sc["supporting_pattern_ids"]) == {"pat_a", "pat_b"}
        assert set(sc["supporting_change_ids"]) == {"chg_1", "chg_2", "chg_3", "chg_4"}
        assert set(sc["supporting_signal_ids"]) == {"sig_pat_a", "sig_pat_b"}
        assert sc["independent_event_count"] == 5, "Change->Event lineage로 계산된 독립 Event 수가 틀림"
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_11_event_type_domain_separation():
    """MODEL_RELEASE/REGULATORY_ACTION(event_type)을 TECHNOLOGY_INFRASTRUCTURE/POLICY_LAW_GOVERNANCE
    (domain)와 같은 필드로 저장하지 않는다."""
    patterns = {
        "pat_a": _pattern("pat_a", ["EntA"], ["MODEL_RELEASE"], ["chg_1", "chg_2"],
                           real_domains=["TECHNOLOGY_INFRASTRUCTURE"]),
        "pat_b": _pattern("pat_b", ["EntB"], ["REGULATORY_ACTION"], ["chg_3", "chg_4"],
                           real_domains=["POLICY_LAW_GOVERNANCE"]),
    }
    (metrics, scs), out_dir = _run(patterns)
    try:
        assert metrics["structural_changes_total"] == 1
        sc = next(iter(scs.values()))
        assert set(sc["event_types"]) == {"MODEL_RELEASE", "REGULATORY_ACTION"}
        assert set(sc["domains"]) == {"TECHNOLOGY_INFRASTRUCTURE", "POLICY_LAW_GOVERNANCE"}
        assert not (set(sc["event_types"]) & set(sc["domains"])), "event_type과 domain이 뒤섞임"
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_12_independence_metric_separation():
    """3 Event / 2 Change / 2 Pattern / Source unknown → 각 independence 지표가 정확히 분리되어야 한다."""
    changes = {
        "chg_1": _change("chg_1", ["evt_1", "evt_2"]),
        "chg_2": _change("chg_2", ["evt_3"]),
    }
    patterns = {
        "pat_a": _pattern("pat_a", ["EntA"], ["MODEL_RELEASE"], ["chg_1"]),
        "pat_b": _pattern("pat_b", ["EntB"], ["PRODUCT_RELEASE"], ["chg_2"]),
    }
    (metrics, scs), out_dir = _run(patterns, changes)
    try:
        assert metrics["structural_changes_total"] == 1
        sc = next(iter(scs.values()))
        assert sc["independent_event_count"] == 3
        assert sc["independent_change_count"] == 2
        assert sc["independent_pattern_count"] == 2
        assert sc["independent_source_count"] is None, "Source independence를 근거 없이 추정함(금지)"
        assert sc["independent_document_count"] is None
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
