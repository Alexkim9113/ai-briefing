# PHASE 5F — Scenario(운영자 지시 17~22, 45번). Scenario != Prediction. Alternative Path가
# 있어야 생성되며(Trajectory만으로 자동 생성 금지), 숫자 확률/자동 승자 선정을 하지 않는다.
from common import hash_id, cap_confidence
from schema import new_scenario_shell, SCENARIO_TYPES, TIME_HORIZONS
from speculation import compute_speculation_level, apply_speculation_ceiling


def generate_scenario_candidates(evidence_records, trajectories, alternative_paths, ceiling_map):
    out = {}
    for rec in evidence_records or []:
        if rec.get("type") != "SCENARIO":
            continue
        alt_path_ids = [pid for pid in rec.get("alternative_path_ids", []) if pid in alternative_paths]
        if not alt_path_ids:
            continue  # Alternative Path 없이 Scenario 생성 금지
        trajectory_ids = [tid for tid in rec.get("trajectory_ids", []) if tid in trajectories]
        if not trajectory_ids:
            continue
        scenario_type = rec.get("scenario_type")
        if scenario_type not in SCENARIO_TYPES:
            continue
        assumption_ids = list(rec.get("assumption_ids", []))
        trigger_conditions = list(rec.get("trigger_conditions", []))
        if not assumption_ids or not trigger_conditions:
            continue  # Scenario 최소 요건(운영자 지시 18번): 명시적 assumption + trigger 필수
        name = rec.get("scenario_name")
        if not name:
            continue
        time_horizon = rec.get("time_horizon")
        if time_horizon not in TIME_HORIZONS:
            time_horizon = "UNKNOWN"
        sid = hash_id("scn", f"{name}|{scenario_type}|{'|'.join(sorted(alt_path_ids))}")
        shell = new_scenario_shell(sid, name, scenario_type, sorted(trajectory_ids), sorted(alt_path_ids),
                                    list(rec.get("structural_change_ids", [])), trigger_conditions, time_horizon)
        shell["assumption_ids"] = assumption_ids
        shell["assumption_count"] = len(assumption_ids)
        shell["supporting_evidence_ids"] = list(rec.get("evidence_ids", []))
        shell["counter_evidence_ids"] = list(rec.get("counter_evidence_ids", []))
        shell["uncertainty_ids"] = list(rec.get("uncertainty_ids", []))
        shell["falsifier_ids"] = list(rec.get("falsifier_ids", []))
        if not shell["uncertainty_ids"]:
            continue  # Scenario 최소 요건: Uncertainty 필수(운영자 지시 18번)
        shell["path_dependency_ids"] = list(rec.get("path_dependency_ids", []))

        ceiling_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "UNKNOWN": -1}
        ceilings = [trajectories[tid]["epistemic_ceiling"] for tid in trajectory_ids] + \
                   [alternative_paths[pid]["epistemic_ceiling"] for pid in alt_path_ids]
        ceiling = min(ceilings, key=lambda c: ceiling_order.get(c, -1)) if ceilings else "UNKNOWN"
        shell["epistemic_ceiling"] = ceiling
        # 확률이 아니라 "탐색 가치가 있는 경로로서의 Evidence 지지 수준"(운영자 지시 22번).
        speculation = compute_speculation_level(lineage_distance=3, assumption_count=len(assumption_ids),
                                                 unsupported_transitions=0)
        shell["speculation_level"] = speculation
        base_confidence = "MEDIUM" if len(shell["supporting_evidence_ids"]) >= 1 else "LOW"
        confidence = cap_confidence(base_confidence, ceiling)
        shell["confidence"] = apply_speculation_ceiling(confidence, speculation, ceiling)
        out[sid] = shell
    return out
