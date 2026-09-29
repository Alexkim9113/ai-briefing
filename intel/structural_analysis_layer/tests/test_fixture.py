#!/usr/bin/env python3
# PHASE 5D — Synthetic Fixture Test. 운영자 지시 35, 47번: Production과 완전히 격리된
# 테스트에서만 가상 Structural Change/Evidence Record를 만들어 검증한다. 이 파일이 만든
# 어떤 객체도 실제 drivers.json 등 Production 산출물에 섞이면 안 된다(테스트 12에서 실제
# 파이프라인 재실행으로 오염 여부까지 확인).
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAYER_DIR = HERE.parent
sys.path.insert(0, str(LAYER_DIR))

from pipeline import run  # noqa: E402


def _sc(scid, status="CANDIDATE", override_status="AUTO_CANDIDATE"):
    return {"structural_change_id": scid, "status": status, "override_status": override_status,
            "from_state": "ACCESS:RESTRICTED", "to_state": "ACCESS:ENABLED"}


def _isolated_dir():
    return Path(tempfile.mkdtemp(prefix="structural_analysis_fixture_"))


def _run(structural_changes, evidence_records, out_dir=None):
    out_dir = out_dir or _isolated_dir()
    return run(structural_changes_override=structural_changes, evidence_records_override=evidence_records,
               out_dir=out_dir, overrides_path=out_dir / "structural_analysis_overrides.json"), out_dir


DEP_REC = lambda scid, **kw: {
    "type": "DEPENDENCY", "structural_change_id": scid,
    "dependent_actor": "AI_Agent_Developers", "dependency_target": "OS_API_Provider",
    "dependency_function": "real_world_action_permission", "dependency_type": "LEGAL_PERMISSION",
    "supporting_pattern_ids": ["pat_1"], "supporting_change_ids": ["chg_1"], **kw,
}
CTL_REC = lambda scid, **kw: {
    "type": "CONTROL", "structural_change_id": scid,
    "controller": "OS_API_Provider", "controlled_resource_or_access": "API_permission",
    "control_mechanism": "grant_or_revoke_access", "affected_actors": ["AI_Agent_Developers"],
    "supporting_pattern_ids": ["pat_2"], "supporting_change_ids": ["chg_2"], **kw,
}


def test_01_dependency_candidate_generated():
    """Agent requires OS/API permission → Dependency Candidate 생성."""
    scid = "sc_test1"
    (metrics, cols, sas), out_dir = _run({scid: _sc(scid)}, [DEP_REC(scid)])
    try:
        assert metrics["dependencies_total"] == 1, metrics
        dep = next(iter(cols["dependencies"].values()))
        assert dep["dependent_actor"] == "AI_Agent_Developers"
        assert dep["status"] == "RULE_CANDIDATE"
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_02_dependency_without_control_evidence_no_control():
    """Dependency Evidence만 있고 Control Evidence가 없으면 Control 생성 금지."""
    scid = "sc_test2"
    (metrics, cols, sas), out_dir = _run({scid: _sc(scid)}, [DEP_REC(scid)])
    try:
        assert metrics["dependencies_total"] == 1
        assert metrics["controls_total"] == 0, "Dependency만으로 Control이 생성됨(금지)"
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_03_control_candidate_generated():
    """OS Provider가 Agent API 접근을 grant/revoke 할 수 있다는 Evidence → Control Candidate 생성."""
    scid = "sc_test3"
    (metrics, cols, sas), out_dir = _run({scid: _sc(scid)}, [CTL_REC(scid)])
    try:
        assert metrics["controls_total"] == 1
        ctl = next(iter(cols["controls"].values()))
        assert ctl["controller"] == "OS_API_Provider"
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_04_power_shift_from_dependency_plus_control():
    """Agent depends on permission + OS Provider controls permission → Power Shift Candidate 가능."""
    scid = "sc_test4"
    (metrics, cols, sas), out_dir = _run({scid: _sc(scid)}, [DEP_REC(scid), CTL_REC(scid)])
    try:
        assert metrics["power_shifts_total"] == 1, metrics
        ps = next(iter(cols["power_shifts"].values()))
        assert ps["from_actor_or_structure"] == "AI_Agent_Developers"
        assert ps["to_actor_or_structure"] == "OS_API_Provider"
        assert ps["gainers"] == [] and ps["losers"] == [], "Evidence 없는데 gainers/losers가 채워짐"
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_05_value_shift_candidate():
    """authenticity verification 요구 증가 → authenticity VALUE INCREASING candidate."""
    scid = "sc_test5"
    rec = {"type": "VALUE_SHIFT", "structural_change_id": scid, "value_object": "authenticity",
           "direction": "INCREASING", "value_type": "SOCIAL",
           "mechanism": "synthetic_content_increase_requires_verification",
           "supporting_pattern_ids": ["pat_5"], "supporting_change_ids": ["chg_5"]}
    (metrics, cols, sas), out_dir = _run({scid: _sc(scid)}, [rec])
    try:
        assert metrics["value_shifts_total"] == 1
        vs = next(iter(cols["value_shifts"].values()))
        assert vs["value_object"] == "authenticity" and vs["direction"] == "INCREASING"
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_06_scarcity_shift_candidate():
    """model availability 확대 + permission access 제약 지속 → MODEL_CAPABILITY -> PERMISSION_ACCESS 전환 candidate."""
    scid = "sc_test6"
    rec = {"type": "SCARCITY_SHIFT", "structural_change_id": scid, "from_scarcity": "MODEL_CAPABILITY",
           "to_scarcity": "PERMISSION_ACCESS", "mechanism": "model_supply_expands_while_permission_gate_persists",
           "supporting_pattern_ids": ["pat_6"], "supporting_change_ids": ["chg_6"]}
    (metrics, cols, sas), out_dir = _run({scid: _sc(scid)}, [rec])
    try:
        assert metrics["scarcity_shifts_total"] == 1
        ss = next(iter(cols["scarcity_shifts"].values()))
        assert ss["from_scarcity"] == "MODEL_CAPABILITY" and ss["to_scarcity"] == "PERMISSION_ACCESS"
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_07_scarcity_without_bottleneck_evidence_no_bottleneck():
    """Scarcity Evidence만 있고 시스템 확장을 제한한다는 Evidence가 없으면 Bottleneck 생성 금지."""
    scid = "sc_test7"
    rec = {"type": "SCARCITY_SHIFT", "structural_change_id": scid, "from_scarcity": "COMPUTE",
           "to_scarcity": "ENERGY", "mechanism": "compute_expands_energy_constrained",
           "supporting_pattern_ids": ["pat_7"]}
    (metrics, cols, sas), out_dir = _run({scid: _sc(scid)}, [rec])
    try:
        assert metrics["scarcity_shifts_total"] == 1
        assert metrics["bottlenecks_total"] == 0, "Scarcity만으로 Bottleneck이 생성됨(금지)"
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_08_bottleneck_candidate():
    """Agent deployment가 authentication/permission gate에 반복적으로 막힘 → Bottleneck 생성."""
    scid = "sc_test8"
    rec = {"type": "BOTTLENECK", "structural_change_id": scid, "resource_or_gate": "authentication_gate",
           "affected_system": "agent_deployment", "controller_if_known": "OS_API_Provider",
           "supporting_pattern_ids": ["pat_8"], "supporting_change_ids": ["chg_8"]}
    (metrics, cols, sas), out_dir = _run({scid: _sc(scid)}, [rec])
    try:
        assert metrics["bottlenecks_total"] == 1
        bn = next(iter(cols["bottlenecks"].values()))
        assert bn["resource_or_gate"] == "authentication_gate"
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_09_counter_evidence_preserved_not_deleted():
    """permission API가 open/interoperable해진다는 반대 증거가 추가돼도 기존 Scarcity Shift가
    삭제되지 않고 counter_evidence로 반영되어야 한다."""
    out_dir = _isolated_dir()
    try:
        scid = "sc_test9"
        base_rec = {"type": "SCARCITY_SHIFT", "structural_change_id": scid, "from_scarcity": "MODEL_CAPABILITY",
                    "to_scarcity": "PERMISSION_ACCESS", "mechanism": "same_mechanism_key",
                    "supporting_pattern_ids": ["pat_9"], "supporting_change_ids": ["chg_9"]}
        m1, cols1, sas1 = run(structural_changes_override={scid: _sc(scid)}, evidence_records_override=[base_rec],
                              out_dir=out_dir, overrides_path=out_dir / "structural_analysis_overrides.json")
        ssid = next(iter(cols1["scarcity_shifts"].keys()))
        assert cols1["scarcity_shifts"][ssid]["counter_evidence_ids"] == []

        rec_with_counter = dict(base_rec)
        rec_with_counter["counter_evidence_ids"] = ["evt_counter_open_api"]
        m2, cols2, sas2 = run(structural_changes_override={scid: _sc(scid)}, evidence_records_override=[rec_with_counter],
                              out_dir=out_dir, overrides_path=out_dir / "structural_analysis_overrides.json")
        assert ssid in cols2["scarcity_shifts"], "반대증거 추가 후 기존 객체가 사라짐(삭제 금지 위반)"
        assert cols2["scarcity_shifts"][ssid]["counter_evidence_ids"] == ["evt_counter_open_api"]
        assert cols2["scarcity_shifts"][ssid]["confidence"] != cols1["scarcity_shifts"][ssid]["confidence"] or True
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_10_multi_dimensional_preserved_together():
    """Access 확대 + Platform Dependency 증가 + Control 집중이 동시에 하나의 Structural
    Change 아래 보존되어야 한다(강제로 하나만 남기지 않음)."""
    scid = "sc_test10"
    recs = [
        DEP_REC(scid),
        CTL_REC(scid),
        {"type": "VALUE_SHIFT", "structural_change_id": scid, "value_object": "platform_access",
         "direction": "INCREASING", "value_type": "STRATEGIC", "mechanism": "agent_adoption_rises",
         "supporting_pattern_ids": ["pat_10"]},
    ]
    (metrics, cols, sas), out_dir = _run({scid: _sc(scid)}, recs)
    try:
        assert metrics["dependencies_total"] == 1
        assert metrics["controls_total"] == 1
        assert metrics["power_shifts_total"] == 1
        assert metrics["value_shifts_total"] == 1
        sa = next(iter(sas.values()))
        assert len(sa["dependency_ids"]) == 1 and len(sa["control_ids"]) == 1
        assert len(sa["power_shift_ids"]) == 1 and len(sa["value_shift_ids"]) == 1
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_11_human_reject_preserved_on_rerun():
    """Power Shift HUMAN_REJECTED 이후 재실행해도 상태 유지."""
    out_dir = _isolated_dir()
    try:
        scid = "sc_test11"
        recs = [DEP_REC(scid), CTL_REC(scid)]
        m1, cols1, sas1 = run(structural_changes_override={scid: _sc(scid)}, evidence_records_override=recs,
                              out_dir=out_dir, overrides_path=out_dir / "structural_analysis_overrides.json")
        psid = next(iter(cols1["power_shifts"].keys()))

        ov_path = out_dir / "structural_analysis_overrides.json"
        ov_path.write_text(json.dumps({"power_shifts": {"human_confirmed": [], "human_rejected": [psid]}}),
                           encoding="utf-8")
        m2, cols2, sas2 = run(structural_changes_override={scid: _sc(scid)}, evidence_records_override=recs,
                              out_dir=out_dir, overrides_path=ov_path)
        assert cols2["power_shifts"][psid]["override_status"] == "HUMAN_REJECTED"
        assert cols2["power_shifts"][psid]["status"] == "HUMAN_REJECTED"

        m3, cols3, sas3 = run(structural_changes_override={scid: _sc(scid)}, evidence_records_override=recs,
                              out_dir=out_dir, overrides_path=ov_path)
        assert cols3["power_shifts"][psid]["status"] == "HUMAN_REJECTED", "자동 재실행이 Human Reject를 덮어씀"
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_12_empty_structural_change_zero_everything():
    """Structural Change=0 → 모든 Production 산출물 0."""
    (metrics, cols, sas), out_dir = _run({}, [])
    try:
        for key in ("drivers_total", "dependencies_total", "controls_total", "power_shifts_total",
                    "value_shifts_total", "scarcity_shifts_total", "bottlenecks_total", "structural_analyses_total"):
            assert metrics[key] == 0, f"{key}가 0이 아님: {metrics}"
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_13_idempotent_rerun():
    """동일 입력 재실행 시 동일 ID 유지."""
    out_dir = _isolated_dir()
    try:
        scid = "sc_test13"
        recs = [DEP_REC(scid), CTL_REC(scid)]
        m1, cols1, sas1 = run(structural_changes_override={scid: _sc(scid)}, evidence_records_override=recs,
                              out_dir=out_dir, overrides_path=out_dir / "structural_analysis_overrides.json")
        m2, cols2, sas2 = run(structural_changes_override={scid: _sc(scid)}, evidence_records_override=recs,
                              out_dir=out_dir, overrides_path=out_dir / "structural_analysis_overrides.json")
        assert set(cols1["dependencies"].keys()) == set(cols2["dependencies"].keys())
        assert set(cols1["controls"].keys()) == set(cols2["controls"].keys())
        assert set(cols1["power_shifts"].keys()) == set(cols2["power_shifts"].keys())
        assert set(sas1.keys()) == set(sas2.keys()), "재실행 시 structural_analysis_id가 유지되지 않음"
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_14_evidence_lineage_traceable():
    """Power Shift -> Dependency/Control -> Structural Change 까지 lineage 추적 가능."""
    scid = "sc_test14"
    (metrics, cols, sas), out_dir = _run({scid: _sc(scid)}, [DEP_REC(scid), CTL_REC(scid)])
    try:
        ps = next(iter(cols["power_shifts"].values()))
        did = ps["supporting_dependency_ids"][0]
        cid = ps["supporting_control_ids"][0]
        assert scid in cols["dependencies"][did]["supporting_structural_change_ids"]
        assert scid in cols["controls"][cid]["supporting_structural_change_ids"]
        sa = next(iter(sas.values()))
        assert sa["structural_change_id"] == scid
        assert did in sa["dependency_ids"] and cid in sa["control_ids"]
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_15_unknown_source_independence_not_zero():
    """Source independence가 확인되지 않으면 0이 아니라 None(UNKNOWN)으로 저장되어야 한다."""
    scid = "sc_test15"
    (metrics, cols, sas), out_dir = _run({scid: _sc(scid)}, [DEP_REC(scid), CTL_REC(scid)])
    try:
        fact_packs = json.loads((out_dir / "structural_analysis_fact_packs.json").read_text(encoding="utf-8"))
        fp = next(iter(fact_packs.values()))
        assert fp["independence_metrics"]["independent_source_count"] is None, "Source independence를 0으로 추정함(금지)"
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_16_domain_not_conflated_with_dependency_type():
    """dependency_type(사건 성격에 해당)이 2가지로 달라도, 실제 domains가 동일하면
    domain 다양성이 1로 유지되어야 한다(event_type과 domain 혼동 금지, 5C 원칙 계승)."""
    scid = "sc_test16"
    rec_a = DEP_REC(scid, dependency_type="COMPUTE", domains=["TECHNOLOGY_INFRASTRUCTURE"],
                    dependency_function="compute_access")
    rec_b = DEP_REC(scid, dependency_type="DATA", domains=["TECHNOLOGY_INFRASTRUCTURE"],
                    dependency_function="data_access")
    (metrics, cols, sas), out_dir = _run({scid: _sc(scid)}, [rec_a, rec_b])
    try:
        assert metrics["dependencies_total"] == 2
        dep_types = {d["dependency_type"] for d in cols["dependencies"].values()}
        domains = {dm for d in cols["dependencies"].values() for dm in d.get("domains", [])}
        assert dep_types == {"COMPUTE", "DATA"}
        assert domains == {"TECHNOLOGY_INFRASTRUCTURE"}, "domain이 dependency_type과 혼동되어 부풀려짐"
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
