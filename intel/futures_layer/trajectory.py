# PHASE 5F — Trajectory(운영자 지시 5~9, 42번). Trajectory != Prediction: 미래 사건이 아니라
# 현재까지 관찰된 변화의 방향/지속 상태다. CODE FIRST — Signal/Pattern/Structural Change 중
# 최소 하나의 근거가 있어야 생성된다(단순 article count 기반 생성 금지).
from common import hash_id, valid_target, cap_confidence
from schema import new_trajectory_shell, TRAJECTORY_DIRECTIONS, TRAJECTORY_MATURITY, TIME_HORIZONS
from speculation import compute_speculation_level, apply_speculation_ceiling


def generate_trajectory_candidates(evidence_records, target_index, ceiling_map):
    out = {}
    for rec in evidence_records or []:
        if rec.get("type") != "TRAJECTORY":
            continue
        target_type, target_id = rec.get("target_object_type"), rec.get("target_object_id")
        if not valid_target(target_type, target_id, target_index):
            continue  # 5E Epistemic Assessment 없이 Trajectory 생성 금지
        signals = list(rec.get("supporting_signal_ids", []))
        patterns = list(rec.get("supporting_pattern_ids", []))
        structural_changes = list(rec.get("supporting_structural_change_ids", []))
        changes = list(rec.get("supporting_change_ids", []))
        if not (signals or patterns or structural_changes or changes):
            continue  # Evidence 근거 없는 Trajectory 생성 금지
        direction = rec.get("direction")
        maturity = rec.get("maturity")
        if direction not in TRAJECTORY_DIRECTIONS or maturity not in TRAJECTORY_MATURITY:
            continue
        time_horizon = rec.get("time_horizon")
        if time_horizon not in TIME_HORIZONS:
            time_horizon = "UNKNOWN"  # Evidence가 시간 범위를 정당화 못하면 UNKNOWN
        tid = hash_id("trj", f"{target_type}|{target_id}|{rec.get('trajectory_type')}|{direction}")
        shell = new_trajectory_shell(tid, target_type, target_id, rec.get("trajectory_type"),
                                      direction, maturity, time_horizon)
        shell["supporting_signal_ids"] = signals
        shell["supporting_pattern_ids"] = patterns
        shell["supporting_structural_change_ids"] = structural_changes
        shell["supporting_change_ids"] = changes
        shell["supporting_evidence_ids"] = list(rec.get("evidence_ids", []))
        shell["counter_evidence_ids"] = list(rec.get("counter_evidence_ids", []))
        shell["uncertainty_ids"] = list(rec.get("uncertainty_ids", []))
        shell["assumption_ids"] = list(rec.get("assumption_ids", []))
        shell["falsifier_ids"] = list(rec.get("falsifier_ids", []))
        shell["alternative_explanation_ids"] = list(rec.get("alternative_explanation_ids", []))
        shell["first_observed"] = rec.get("first_observed")
        shell["last_observed"] = rec.get("last_observed")

        ceiling = ceiling_map.get((target_type, target_id), "UNKNOWN")
        shell["epistemic_ceiling"] = ceiling
        strength = len(signals) + len(patterns) + len(structural_changes) + len(changes)
        confidence = "HIGH" if strength >= 3 else ("MEDIUM" if strength >= 1 else "LOW")
        speculation = compute_speculation_level(lineage_distance=1, assumption_count=len(shell["assumption_ids"]),
                                                 unsupported_transitions=0)
        shell["speculation_level"] = speculation
        confidence = cap_confidence(confidence, ceiling)
        shell["confidence"] = apply_speculation_ceiling(confidence, speculation, ceiling)
        out[tid] = shell
    return out
