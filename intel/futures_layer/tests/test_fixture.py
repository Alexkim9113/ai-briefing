#!/usr/bin/env python3
# PHASE 5F — 32개 Synthetic Fixture 테스트(운영자 지시 58, 69번). 전부 tempfile.mkdtemp()로
# 격리된 out_dir/override 경로만 사용 — 실제 Production JSON은 절대 건드리지 않는다.
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAYER = HERE.parent
ROOT = LAYER.parent.parent
sys.path.insert(0, str(LAYER))
sys.path.insert(0, str(ROOT))

import pipeline  # noqa: E402


def epistemic_context(*entries):
    """entries: (target_type, target_id, ceiling) 튜플들. 5E Epistemic Assessment가 실제
    존재하는 대상만 target_index에 들어간다 — bypass guard의 핵심."""
    target_index, ceiling_map = {}, {}
    for tt, tid, ceiling in entries:
        target_index.setdefault(tt, set()).add(tid)
        ceiling_map[(tt, tid)] = ceiling
    return target_index, ceiling_map


def isolated_dir():
    d = Path(tempfile.mkdtemp(prefix="futures_test_"))
    overrides_path = d / "overrides.json"
    overrides_path.write_text(json.dumps(
        {c: {"human_confirmed": [], "human_rejected": []} for c in
         ("trajectories", "outlooks", "alternative_paths", "scenarios", "second_order_effects",
          "third_order_effects", "forecasts", "futures_assessments")}), encoding="utf-8")
    return d, overrides_path


def run_isolated(records, target_index, ceiling_map, out_dir=None, overrides_path=None):
    if out_dir is None:
        out_dir, overrides_path = isolated_dir()
    metrics, collections, observations, revisions, assessments = pipeline.run(
        target_index_override=target_index, ceiling_map_override=ceiling_map,
        evidence_records_override=records, out_dir=out_dir, overrides_path=overrides_path)
    return out_dir, overrides_path, metrics, collections, observations, revisions, assessments


def trajectory_rec(target_id="sc1", direction="ACCELERATING", maturity="STRENGTHENING",
                    time_horizon="1_3_YEARS", **kw):
    base = {"type": "TRAJECTORY", "target_object_type": "STRUCTURAL_CHANGE", "target_object_id": target_id,
            "trajectory_type": "PERMISSION_DEPENDENCY", "direction": direction, "maturity": maturity,
            "time_horizon": time_horizon, "supporting_signal_ids": ["sig1"], "evidence_ids": ["e1"]}
    base.update(kw)
    return base


def test_01_trajectory():
    ti, cm = epistemic_context(("STRUCTURAL_CHANGE", "sc1", "MEDIUM"))
    rec = trajectory_rec()
    _, _, m, coll, *_ = run_isolated([rec], ti, cm)
    assert m["trajectories_total"] == 1
    t = next(iter(coll["trajectories"].values()))
    assert t["maturity"] == "STRENGTHENING"
    print("test_01 OK")


def test_02_5e_bypass():
    ti, cm = epistemic_context()  # sc1에 대한 Epistemic Assessment 없음
    rec = trajectory_rec(target_id="sc1")
    _, _, m, *_ = run_isolated([rec], ti, cm)
    assert m["trajectories_total"] == 0
    print("test_02 OK")


def test_03_outlook_conditional():
    ti, cm = epistemic_context(("STRUCTURAL_CHANGE", "sc1", "MEDIUM"))
    traj = trajectory_rec()
    out_dir, overrides_path, _, coll, *_ = run_isolated([traj], ti, cm)
    tid = next(iter(coll["trajectories"].keys()))
    outlook = {"type": "OUTLOOK", "trajectory_ids": [tid], "outlook_type": "CONTROL_STRENGTHENING",
               "condition": "IF permission architecture remains concentrated",
               "direction": "STRENGTHENING", "time_horizon": "1_3_YEARS", "evidence_ids": ["e1"]}
    _, _, m, coll2, *_ = run_isolated([traj, outlook], ti, cm, out_dir=out_dir, overrides_path=overrides_path)
    assert m["outlooks_total"] == 1
    print("test_03 OK")


def test_04_condition_required():
    ti, cm = epistemic_context(("STRUCTURAL_CHANGE", "sc1", "MEDIUM"))
    out_dir, overrides_path, _, coll, *_ = run_isolated([trajectory_rec()], ti, cm)
    tid = next(iter(coll["trajectories"].keys()))
    outlook = {"type": "OUTLOOK", "trajectory_ids": [tid], "outlook_type": "X",
               "direction": "STRENGTHENING", "time_horizon": "1_3_YEARS"}  # condition 없음
    _, _, m, *_ = run_isolated([trajectory_rec(), outlook], ti, cm, out_dir=out_dir, overrides_path=overrides_path)
    assert m["outlooks_total"] == 0
    print("test_04 OK")


def test_05_alternative_path():
    ti, cm = epistemic_context(("STRUCTURAL_CHANGE", "sc1", "MEDIUM"))
    out_dir, overrides_path, _, coll, *_ = run_isolated([trajectory_rec()], ti, cm)
    tid = next(iter(coll["trajectories"].keys()))
    path = {"type": "ALTERNATIVE_PATH", "trajectory_ids": [tid], "path_name": "OPEN_STANDARD",
            "path_type": "SUBSTITUTION_PATH", "trigger_conditions": ["major platforms adopt open standard"],
            "counter_evidence_ids": ["ce1"], "time_horizon": "1_3_YEARS"}
    _, _, m, coll2, *_ = run_isolated([trajectory_rec(), path], ti, cm, out_dir=out_dir, overrides_path=overrides_path)
    assert m["alternative_paths_total"] == 1
    print("test_05 OK")


def test_06_no_evidence_branch():
    ti, cm = epistemic_context(("STRUCTURAL_CHANGE", "sc1", "MEDIUM"))
    out_dir, overrides_path, _, coll, *_ = run_isolated([trajectory_rec()], ti, cm)
    tid = next(iter(coll["trajectories"].keys()))
    path = {"type": "ALTERNATIVE_PATH", "trajectory_ids": [tid], "path_name": "ARBITRARY",
            "path_type": "SUBSTITUTION_PATH", "trigger_conditions": [], "time_horizon": "1_3_YEARS"}
    _, _, m, *_ = run_isolated([trajectory_rec(), path], ti, cm, out_dir=out_dir, overrides_path=overrides_path)
    assert m["alternative_paths_total"] == 0
    print("test_06 OK")


def _traj_and_path(ti, cm):
    out_dir, overrides_path, _, coll, *_ = run_isolated([trajectory_rec()], ti, cm)
    tid = next(iter(coll["trajectories"].keys()))
    path = {"type": "ALTERNATIVE_PATH", "trajectory_ids": [tid], "path_name": "OPEN_STANDARD",
            "path_type": "SUBSTITUTION_PATH", "trigger_conditions": ["regulator mandates interoperability"],
            "counter_evidence_ids": ["ce1"], "time_horizon": "1_3_YEARS"}
    out_dir, overrides_path, _, coll, *_ = run_isolated([trajectory_rec(), path], ti, cm,
                                                         out_dir=out_dir, overrides_path=overrides_path)
    pid = next(iter(coll["alternative_paths"].keys()))
    return out_dir, overrides_path, tid, pid


def test_07_scenario():
    ti, cm = epistemic_context(("STRUCTURAL_CHANGE", "sc1", "MEDIUM"))
    out_dir, overrides_path, tid, pid = _traj_and_path(ti, cm)
    scenario = {"type": "SCENARIO", "scenario_name": "OPEN_STANDARD_SCENARIO", "scenario_type": "CONSTRAINT",
                "trajectory_ids": [tid], "alternative_path_ids": [pid], "assumption_ids": ["asm1"],
                "trigger_conditions": ["regulator mandates interoperability"], "uncertainty_ids": ["unc1"],
                "time_horizon": "1_3_YEARS", "evidence_ids": ["e1"]}
    records = [trajectory_rec(), {"type": "ALTERNATIVE_PATH", "trajectory_ids": [tid], "path_name": "OPEN_STANDARD",
               "path_type": "SUBSTITUTION_PATH", "trigger_conditions": ["regulator mandates interoperability"],
               "counter_evidence_ids": ["ce1"], "time_horizon": "1_3_YEARS"}, scenario]
    _, _, m, coll, *_ = run_isolated(records, ti, cm, out_dir=out_dir, overrides_path=overrides_path)
    assert m["scenarios_total"] == 1
    print("test_07 OK")


def test_08_no_path_no_scenario():
    ti, cm = epistemic_context(("STRUCTURAL_CHANGE", "sc1", "MEDIUM"))
    out_dir, overrides_path = isolated_dir()
    traj = trajectory_rec()
    out_dir, overrides_path, _, coll, *_ = run_isolated([traj], ti, cm, out_dir=out_dir, overrides_path=overrides_path)
    tid = next(iter(coll["trajectories"].keys()))
    scenario = {"type": "SCENARIO", "scenario_name": "NO_PATH", "scenario_type": "BASE",
                "trajectory_ids": [tid], "alternative_path_ids": ["nonexistent"], "assumption_ids": ["asm1"],
                "trigger_conditions": ["x"], "uncertainty_ids": ["unc1"], "time_horizon": "1_3_YEARS"}
    _, _, m, *_ = run_isolated([traj, scenario], ti, cm, out_dir=out_dir, overrides_path=overrides_path)
    assert m["scenarios_total"] == 0
    print("test_08 OK")


def test_09_no_probability():
    ti, cm = epistemic_context(("STRUCTURAL_CHANGE", "sc1", "MEDIUM"))
    out_dir, overrides_path, tid, pid = _traj_and_path(ti, cm)
    scenario = {"type": "SCENARIO", "scenario_name": "S1", "scenario_type": "BASE",
                "trajectory_ids": [tid], "alternative_path_ids": [pid], "assumption_ids": ["asm1"],
                "trigger_conditions": ["t1"], "uncertainty_ids": ["unc1"], "time_horizon": "1_3_YEARS"}
    records = [trajectory_rec(), {"type": "ALTERNATIVE_PATH", "trajectory_ids": [tid], "path_name": "OPEN_STANDARD",
               "path_type": "SUBSTITUTION_PATH", "trigger_conditions": ["regulator mandates interoperability"],
               "counter_evidence_ids": ["ce1"], "time_horizon": "1_3_YEARS"}, scenario]
    _, _, m, coll, *_ = run_isolated(records, ti, cm, out_dir=out_dir, overrides_path=overrides_path)
    s = next(iter(coll["scenarios"].values()))
    assert "probability" not in s
    assert s["confidence"] in ("LOW", "MEDIUM", "HIGH")
    print("test_09 OK")


def test_10_second_order():
    ti, cm = epistemic_context(("STRUCTURAL_CHANGE", "sc1", "MEDIUM"))
    rec = {"type": "SECOND_ORDER_EFFECT", "source_object_type": "STRUCTURAL_CHANGE", "source_object_id": "sc1",
           "effect_type": "AD_OPTIMIZATION_SHIFT", "affected_domain": "ECONOMY_INDUSTRY_LABOR",
           "mechanism": "agent transaction increase -> advertising shifts toward agent optimization",
           "evidence_ids": ["e1"]}
    _, _, m, coll, *_ = run_isolated([rec], ti, cm)
    assert m["second_order_effects_total"] == 1
    e = next(iter(coll["second_order_effects"].values()))
    assert e["status"] == "HYPOTHESIS_CANDIDATE"
    print("test_10 OK")


def test_11_third_order():
    ti, cm = epistemic_context(("STRUCTURAL_CHANGE", "sc1", "MEDIUM"))
    rec2 = {"type": "SECOND_ORDER_EFFECT", "source_object_type": "STRUCTURAL_CHANGE", "source_object_id": "sc1",
            "effect_type": "AD_OPTIMIZATION_SHIFT", "affected_domain": "ECONOMY_INDUSTRY_LABOR",
            "mechanism": "agent transaction increase -> ad shift", "evidence_ids": ["e1"]}
    out_dir, overrides_path, _, coll, *_ = run_isolated([rec2], ti, cm)
    eid2 = next(iter(coll["second_order_effects"].keys()))
    rec3 = {"type": "THIRD_ORDER_EFFECT", "source_second_order_effect_id": eid2,
            "effect_type": "PERMISSION_LAYER_INTERMEDIATION", "affected_domains": ["POLICY_LAW_GOVERNANCE"],
            "mechanism": "ad shift -> platform mediation -> permission layer becomes intermediary"}
    _, _, m, coll2, *_ = run_isolated([rec2, rec3], ti, cm, out_dir=out_dir, overrides_path=overrides_path)
    assert m["third_order_effects_total"] == 1
    print("test_11 OK")


def test_12_depth_limit():
    ti, cm = epistemic_context(("STRUCTURAL_CHANGE", "sc1", "MEDIUM"))
    rec2 = {"type": "SECOND_ORDER_EFFECT", "source_object_type": "STRUCTURAL_CHANGE", "source_object_id": "sc1",
            "effect_type": "T", "affected_domain": "ECONOMY_INDUSTRY_LABOR", "mechanism": "m"}
    out_dir, overrides_path, _, coll, *_ = run_isolated([rec2], ti, cm)
    eid2 = next(iter(coll["second_order_effects"].keys()))
    rec3 = {"type": "THIRD_ORDER_EFFECT", "source_second_order_effect_id": eid2, "effect_type": "T3",
            "affected_domains": ["POLICY_LAW_GOVERNANCE"], "mechanism": "m2"}
    _, _, _, coll2, *_ = run_isolated([rec2, rec3], ti, cm, out_dir=out_dir, overrides_path=overrides_path)
    eid3 = next(iter(coll2["third_order_effects"].keys()))
    # 4차 시도: source_second_order_effect_id에 3차 효과 id를 넣어도 second_order_effects에 없으므로 생성 금지
    rec4 = {"type": "THIRD_ORDER_EFFECT", "source_second_order_effect_id": eid3, "effect_type": "T4",
            "affected_domains": ["PLANET"], "mechanism": "m3"}
    _, _, m, *_ = run_isolated([rec2, rec3, rec4], ti, cm, out_dir=out_dir, overrides_path=overrides_path)
    assert m["third_order_effects_total"] == 1  # rec4는 생성되지 않음
    print("test_12 OK")


def test_13_counter_evidence_no_delete():
    ti, cm = epistemic_context(("STRUCTURAL_CHANGE", "sc1", "MEDIUM"))
    out_dir, overrides_path, _, coll, *_ = run_isolated([trajectory_rec()], ti, cm)
    tid = next(iter(coll["trajectories"].keys()))
    rec_with_ce = trajectory_rec(counter_evidence_ids=["ce1"])
    _, _, m, coll2, *_ = run_isolated([rec_with_ce], ti, cm, out_dir=out_dir, overrides_path=overrides_path)
    assert tid in coll2["trajectories"]  # 대상 삭제되지 않음
    assert coll2["trajectories"][tid]["counter_evidence_ids"] == ["ce1"]
    print("test_13 OK")


def test_14_uncertainty_propagation():
    ti, cm = epistemic_context(("STRUCTURAL_CHANGE", "sc1", "MEDIUM"))
    rec = trajectory_rec(uncertainty_ids=["unc_causality"])
    _, _, m, coll, *_ = run_isolated([rec], ti, cm)
    t = next(iter(coll["trajectories"].values()))
    assert t["uncertainty_ids"] == ["unc_causality"]  # 사라지지 않음
    print("test_14 OK")


def test_15_epistemic_ceiling():
    ti, cm = epistemic_context(("STRUCTURAL_CHANGE", "sc1", "MEDIUM"))
    rec = trajectory_rec(supporting_signal_ids=["s1", "s2"], supporting_pattern_ids=["p1"],
                          supporting_structural_change_ids=["sc_x"])
    _, _, m, coll, *_ = run_isolated([rec], ti, cm)
    t = next(iter(coll["trajectories"].values()))
    assert t["confidence"] != "HIGH"  # ceiling MEDIUM을 넘지 못함
    print("test_15 OK")


def test_16_speculation_ceiling():
    ti, cm = epistemic_context(("STRUCTURAL_CHANGE", "sc1", "LOW"))
    rec2 = {"type": "SECOND_ORDER_EFFECT", "source_object_type": "STRUCTURAL_CHANGE", "source_object_id": "sc1",
            "effect_type": "T", "affected_domain": "ECONOMY_INDUSTRY_LABOR", "mechanism": "m"}
    out_dir, overrides_path, _, coll, *_ = run_isolated([rec2], ti, cm)
    eid2 = next(iter(coll["second_order_effects"].keys()))
    rec3 = {"type": "THIRD_ORDER_EFFECT", "source_second_order_effect_id": eid2, "effect_type": "T3",
            "affected_domains": ["POLICY_LAW_GOVERNANCE"], "mechanism": "m2"}
    _, _, m, coll2, *_ = run_isolated([rec2, rec3], ti, cm, out_dir=out_dir, overrides_path=overrides_path)
    e3 = next(iter(coll2["third_order_effects"].values()))
    assert e3["speculation_level"] == "HIGH"
    assert e3["confidence"] == "LOW"  # HIGH speculation + LOW ceiling -> LOW
    print("test_16 OK")


def test_17_falsifier_reference():
    ti, cm = epistemic_context(("STRUCTURAL_CHANGE", "sc1", "MEDIUM"))
    out_dir, overrides_path, tid, pid = _traj_and_path(ti, cm)
    scenario = {"type": "SCENARIO", "scenario_name": "S_FALS", "scenario_type": "BASE",
                "trajectory_ids": [tid], "alternative_path_ids": [pid], "assumption_ids": ["asm1"],
                "trigger_conditions": ["t1"], "uncertainty_ids": ["unc1"], "falsifier_ids": ["fls1"],
                "time_horizon": "1_3_YEARS"}
    records = [trajectory_rec(), {"type": "ALTERNATIVE_PATH", "trajectory_ids": [tid], "path_name": "OPEN_STANDARD",
               "path_type": "SUBSTITUTION_PATH", "trigger_conditions": ["regulator mandates interoperability"],
               "counter_evidence_ids": ["ce1"], "time_horizon": "1_3_YEARS"}, scenario]
    _, _, m, coll, *_ = run_isolated(records, ti, cm, out_dir=out_dir, overrides_path=overrides_path)
    s = next(iter(coll["scenarios"].values()))
    assert s["falsifier_ids"] == ["fls1"]
    print("test_17 OK")


def test_18_falsifier_observed_revision_candidate():
    ti, cm = epistemic_context(("STRUCTURAL_CHANGE", "sc1", "MEDIUM"))
    forecast = {"type": "FORECAST", "forecast_statement": "Permission control strengthens",
                "target": {"type": "STRUCTURAL_CHANGE", "id": "sc1"}, "time_horizon": "1_3_YEARS",
                "observable_indicators": ["API policy changes"], "conditions": ["c1"], "evidence_ids": ["e1"]}
    out_dir, overrides_path, _, coll, *_ = run_isolated([forecast], ti, cm)
    fid = next(iter(coll["forecasts"].keys()))
    revision = {"type": "FORECAST_REVISION", "forecast_id": fid,
                "previous_statement": "Permission control strengthens",
                "new_statement": "Permission control weakens (falsifier observed)",
                "previous_confidence": "MEDIUM", "new_confidence": "LOW",
                "revision_reason": "FALSIFIER_OBSERVED", "timestamp": "2026-09-29"}
    _, _, m, coll2, obs, revs, _ = run_isolated([forecast, revision], ti, cm, out_dir=out_dir,
                                                 overrides_path=overrides_path)
    assert m["forecast_revisions_total"] == 1
    assert list(revs.values())[0]["revision_reason"] == "FALSIFIER_OBSERVED"
    print("test_18 OK")


def test_19_forecast_active():
    ti, cm = epistemic_context(("STRUCTURAL_CHANGE", "sc1", "MEDIUM"))
    forecast = {"type": "FORECAST", "forecast_statement": "S1", "target": {"type": "STRUCTURAL_CHANGE", "id": "sc1"},
                "time_horizon": "1_3_YEARS", "observable_indicators": ["ind1"], "conditions": ["c1"]}
    _, _, m, coll, *_ = run_isolated([forecast], ti, cm)
    f = next(iter(coll["forecasts"].values()))
    assert f["status"] == "ACTIVE"
    print("test_19 OK")


def test_20_forecast_observation_supported():
    ti, cm = epistemic_context(("STRUCTURAL_CHANGE", "sc1", "MEDIUM"))
    forecast = {"type": "FORECAST", "forecast_statement": "S1", "target": {"type": "STRUCTURAL_CHANGE", "id": "sc1"},
                "time_horizon": "1_3_YEARS", "observable_indicators": ["ind1"], "conditions": ["c1"]}
    out_dir, overrides_path, _, coll, *_ = run_isolated([forecast], ti, cm)
    fid = next(iter(coll["forecasts"].keys()))
    obs = {"type": "FORECAST_OBSERVATION", "forecast_id": fid, "observation_date": "2026-10-06",
           "observed_indicators": ["ind1"], "assessment": "SUPPORTS"}
    _, _, m, coll2, *_ = run_isolated([forecast, obs], ti, cm, out_dir=out_dir, overrides_path=overrides_path)
    assert coll2["forecasts"][fid]["status"] == "SUPPORTED"
    print("test_20 OK")


def test_21_forecast_contradicted():
    ti, cm = epistemic_context(("STRUCTURAL_CHANGE", "sc1", "MEDIUM"))
    forecast = {"type": "FORECAST", "forecast_statement": "S1", "target": {"type": "STRUCTURAL_CHANGE", "id": "sc1"},
                "time_horizon": "1_3_YEARS", "observable_indicators": ["ind1"], "conditions": ["c1"]}
    out_dir, overrides_path, _, coll, *_ = run_isolated([forecast], ti, cm)
    fid = next(iter(coll["forecasts"].keys()))
    obs = {"type": "FORECAST_OBSERVATION", "forecast_id": fid, "observation_date": "2026-10-06",
           "observed_indicators": ["ind1"], "assessment": "CONTRADICTS"}
    _, _, m, coll2, *_ = run_isolated([forecast, obs], ti, cm, out_dir=out_dir, overrides_path=overrides_path)
    assert coll2["forecasts"][fid]["status"] == "CONTRADICTED"
    print("test_21 OK")


def test_22_forecast_revision_no_delete():
    ti, cm = epistemic_context(("STRUCTURAL_CHANGE", "sc1", "MEDIUM"))
    forecast = {"type": "FORECAST", "forecast_statement": "S1", "target": {"type": "STRUCTURAL_CHANGE", "id": "sc1"},
                "time_horizon": "1_3_YEARS", "observable_indicators": ["ind1"], "conditions": ["c1"]}
    out_dir, overrides_path, _, coll, *_ = run_isolated([forecast], ti, cm)
    fid = next(iter(coll["forecasts"].keys()))
    revision = {"type": "FORECAST_REVISION", "forecast_id": fid, "previous_statement": "S1", "new_statement": "S2",
                "previous_confidence": "LOW", "new_confidence": "MEDIUM", "revision_reason": "NEW_EVIDENCE",
                "timestamp": "2026-10-06"}
    _, _, m, coll2, obs, revs, _ = run_isolated([forecast, revision], ti, cm, out_dir=out_dir,
                                                 overrides_path=overrides_path)
    assert fid in coll2["forecasts"]  # 삭제되지 않음
    assert coll2["forecasts"][fid]["forecast_statement"] == "S2"
    assert len(revs) == 1
    print("test_22 OK")


def test_23_forecast_memory():
    ti, cm = epistemic_context(("STRUCTURAL_CHANGE", "sc1", "MEDIUM"))
    forecast = {"type": "FORECAST", "forecast_statement": "S1", "target": {"type": "STRUCTURAL_CHANGE", "id": "sc1"},
                "time_horizon": "1_3_YEARS", "observable_indicators": ["ind1"], "conditions": ["c1"]}
    out_dir, overrides_path, _, coll, *_ = run_isolated([forecast], ti, cm)
    fid = next(iter(coll["forecasts"].keys()))
    obs1 = {"type": "FORECAST_OBSERVATION", "forecast_id": fid, "observation_date": "W1", "assessment": "SUPPORTS"}
    out_dir, overrides_path, _, coll, obs, *_ = run_isolated([forecast, obs1], ti, cm, out_dir=out_dir,
                                                              overrides_path=overrides_path)
    obs2 = {"type": "FORECAST_OBSERVATION", "forecast_id": fid, "observation_date": "W8", "assessment": "WEAKENS"}
    _, _, m, coll2, obs2_all, *_ = run_isolated([forecast, obs1, obs2], ti, cm, out_dir=out_dir,
                                                 overrides_path=overrides_path)
    assert len(obs2_all) == 2  # W1, W8 관측 전부 보존
    print("test_23 OK")


def test_24_multiple_scenarios_no_winner():
    ti, cm = epistemic_context(("STRUCTURAL_CHANGE", "sc1", "MEDIUM"))
    out_dir, overrides_path, tid, pid = _traj_and_path(ti, cm)
    base = {"type": "SCENARIO", "scenario_name": "BASE_S", "scenario_type": "BASE", "trajectory_ids": [tid],
            "alternative_path_ids": [pid], "assumption_ids": ["a1"], "trigger_conditions": ["t1"],
            "uncertainty_ids": ["u1"], "time_horizon": "1_3_YEARS"}
    accel = {"type": "SCENARIO", "scenario_name": "ACCEL_S", "scenario_type": "ACCELERATION",
             "trajectory_ids": [tid], "alternative_path_ids": [pid], "assumption_ids": ["a1"],
             "trigger_conditions": ["t1"], "uncertainty_ids": ["u1"], "time_horizon": "1_3_YEARS"}
    constraint = {"type": "SCENARIO", "scenario_name": "CONSTRAINT_S", "scenario_type": "CONSTRAINT",
                  "trajectory_ids": [tid], "alternative_path_ids": [pid], "assumption_ids": ["a1"],
                  "trigger_conditions": ["t1"], "uncertainty_ids": ["u1"], "time_horizon": "1_3_YEARS"}
    path_rec = {"type": "ALTERNATIVE_PATH", "trajectory_ids": [tid], "path_name": "OPEN_STANDARD",
                "path_type": "SUBSTITUTION_PATH", "trigger_conditions": ["regulator mandates interoperability"],
                "counter_evidence_ids": ["ce1"], "time_horizon": "1_3_YEARS"}
    _, _, m, coll, *_ = run_isolated([trajectory_rec(), path_rec, base, accel, constraint], ti, cm,
                                      out_dir=out_dir, overrides_path=overrides_path)
    assert m["scenarios_total"] == 3
    for s in coll["scenarios"].values():
        assert "winner" not in s and "most_likely" not in s
    print("test_24 OK")


def test_25_cross_domain_chain():
    ti, cm = epistemic_context(("STRUCTURAL_CHANGE", "sc1", "MEDIUM"))
    rec2 = {"type": "SECOND_ORDER_EFFECT", "source_object_type": "STRUCTURAL_CHANGE", "source_object_id": "sc1",
            "effect_type": "T", "affected_domain": "ECONOMY_INDUSTRY_LABOR", "mechanism": "m"}
    out_dir, overrides_path, _, coll, *_ = run_isolated([rec2], ti, cm)
    eid2 = next(iter(coll["second_order_effects"].keys()))
    rec3 = {"type": "THIRD_ORDER_EFFECT", "source_second_order_effect_id": eid2, "effect_type": "T3",
            "affected_domains": ["POLICY_LAW_GOVERNANCE", "HUMAN_SOCIETY_EDUCATION"], "mechanism": "m2"}
    _, _, m, coll2, *_ = run_isolated([rec2, rec3], ti, cm, out_dir=out_dir, overrides_path=overrides_path)
    e3 = next(iter(coll2["third_order_effects"].values()))
    assert set(e3["affected_domains"]) == {"POLICY_LAW_GOVERNANCE", "HUMAN_SOCIETY_EDUCATION"}
    print("test_25 OK")


def test_26_domain_not_event_type():
    ti, cm = epistemic_context(("STRUCTURAL_CHANGE", "sc1", "MEDIUM"))
    rec = {"type": "SECOND_ORDER_EFFECT", "source_object_type": "STRUCTURAL_CHANGE", "source_object_id": "sc1",
           "effect_type": "T", "affected_domain": "MODEL_RELEASE", "mechanism": "m"}  # Event Type을 Domain으로 오용
    _, _, m, *_ = run_isolated([rec], ti, cm)
    assert m["second_order_effects_total"] == 0
    print("test_26 OK")


def test_27_assumption_load():
    ti, cm = epistemic_context(("STRUCTURAL_CHANGE", "sc1", "MEDIUM"))
    out_dir, overrides_path, tid, pid = _traj_and_path(ti, cm)
    scenario = {"type": "SCENARIO", "scenario_name": "S_ASM", "scenario_type": "BASE", "trajectory_ids": [tid],
                "alternative_path_ids": [pid], "assumption_ids": ["a1", "a2", "a3"], "trigger_conditions": ["t1"],
                "uncertainty_ids": ["u1"], "time_horizon": "1_3_YEARS"}
    path_rec = {"type": "ALTERNATIVE_PATH", "trajectory_ids": [tid], "path_name": "OPEN_STANDARD",
                "path_type": "SUBSTITUTION_PATH", "trigger_conditions": ["regulator mandates interoperability"],
                "counter_evidence_ids": ["ce1"], "time_horizon": "1_3_YEARS"}
    _, _, m, coll, *_ = run_isolated([trajectory_rec(), path_rec, scenario], ti, cm,
                                      out_dir=out_dir, overrides_path=overrides_path)
    s = next(iter(coll["scenarios"].values()))
    assert s["assumption_count"] == 3
    print("test_27 OK")


def test_28_unknown_time_horizon():
    ti, cm = epistemic_context(("STRUCTURAL_CHANGE", "sc1", "MEDIUM"))
    rec = trajectory_rec(time_horizon="NOT_A_VALID_HORIZON")
    _, _, m, coll, *_ = run_isolated([rec], ti, cm)
    t = next(iter(coll["trajectories"].values()))
    assert t["time_horizon"] == "UNKNOWN"
    print("test_28 OK")


def test_29_human_reject_persists():
    ti, cm = epistemic_context(("STRUCTURAL_CHANGE", "sc1", "MEDIUM"))
    out_dir, overrides_path, tid, pid = _traj_and_path(ti, cm)
    scenario = {"type": "SCENARIO", "scenario_name": "S_REJ", "scenario_type": "BASE", "trajectory_ids": [tid],
                "alternative_path_ids": [pid], "assumption_ids": ["a1"], "trigger_conditions": ["t1"],
                "uncertainty_ids": ["u1"], "time_horizon": "1_3_YEARS"}
    path_rec = {"type": "ALTERNATIVE_PATH", "trajectory_ids": [tid], "path_name": "OPEN_STANDARD",
                "path_type": "SUBSTITUTION_PATH", "trigger_conditions": ["regulator mandates interoperability"],
                "counter_evidence_ids": ["ce1"], "time_horizon": "1_3_YEARS"}
    records = [trajectory_rec(), path_rec, scenario]
    _, _, _, coll, *_ = run_isolated(records, ti, cm, out_dir=out_dir, overrides_path=overrides_path)
    sid = next(iter(coll["scenarios"].keys()))
    overrides = json.loads(overrides_path.read_text(encoding="utf-8"))
    overrides["scenarios"]["human_rejected"].append(sid)
    overrides_path.write_text(json.dumps(overrides), encoding="utf-8")
    for _ in range(3):
        _, _, _, coll, *_ = run_isolated(records, ti, cm, out_dir=out_dir, overrides_path=overrides_path)
        assert coll["scenarios"][sid]["status"] == "HUMAN_REJECTED"
    print("test_29 OK")


def test_30_idempotency():
    ti, cm = epistemic_context(("STRUCTURAL_CHANGE", "sc1", "MEDIUM"))
    out_dir, overrides_path = isolated_dir()
    rec = trajectory_rec()
    _, _, _, coll1, *_ = run_isolated([rec], ti, cm, out_dir=out_dir, overrides_path=overrides_path)
    ids1 = sorted(coll1["trajectories"].keys())
    _, _, _, coll2, *_ = run_isolated([rec], ti, cm, out_dir=out_dir, overrides_path=overrides_path)
    ids2 = sorted(coll2["trajectories"].keys())
    assert ids1 == ids2
    print("test_30 OK")


def test_31_lineage():
    ti, cm = epistemic_context(("STRUCTURAL_CHANGE", "sc1", "MEDIUM"))
    out_dir, overrides_path, tid, pid = _traj_and_path(ti, cm)
    scenario = {"type": "SCENARIO", "scenario_name": "S_LIN", "scenario_type": "BASE", "trajectory_ids": [tid],
                "alternative_path_ids": [pid], "assumption_ids": ["a1"], "trigger_conditions": ["t1"],
                "uncertainty_ids": ["u1"], "time_horizon": "1_3_YEARS"}
    path_rec = {"type": "ALTERNATIVE_PATH", "trajectory_ids": [tid], "path_name": "OPEN_STANDARD",
                "path_type": "SUBSTITUTION_PATH", "trigger_conditions": ["regulator mandates interoperability"],
                "counter_evidence_ids": ["ce1"], "time_horizon": "1_3_YEARS"}
    _, _, m, coll, _, _, assessments = run_isolated([trajectory_rec(), path_rec, scenario], ti, cm,
                                                     out_dir=out_dir, overrides_path=overrides_path)
    sid = next(iter(coll["scenarios"].keys()))
    s = coll["scenarios"][sid]
    assert tid in s["trajectory_ids"] and pid in s["alternative_path_ids"]
    assert coll["trajectories"][tid]["target_object_type"] == "STRUCTURAL_CHANGE"
    a = next(iter(assessments.values()))
    assert sid in a["scenario_ids"] and tid in a["trajectory_ids"]
    print("test_31 OK")


def test_32_empty_state():
    ti, cm = epistemic_context()  # 5E Epistemic Assessment 0건
    _, _, m, *_ = run_isolated([], ti, cm)
    for name in ("trajectories_total", "outlooks_total", "alternative_paths_total", "scenarios_total",
                 "second_order_effects_total", "third_order_effects_total", "forecasts_total",
                 "forecast_observations_total", "forecast_revisions_total", "futures_assessments_total"):
        assert m[name] == 0, name
    print("test_32 OK")


def run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
    print(f"\n{len(fns)}/{len(fns)} PASSED")


if __name__ == "__main__":
    run_all()
