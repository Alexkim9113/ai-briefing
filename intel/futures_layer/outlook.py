# PHASE 5F — Outlook(운영자 지시 10~12, 43번). Outlook != Fact — 반드시 condition을 가진
# 조건부 Intelligence다. Trajectory + Condition + Evidence + Epistemic Assessment가 모두
# 있어야 생성된다.
from common import hash_id, cap_confidence
from schema import new_outlook_shell, TIME_HORIZONS
from speculation import compute_speculation_level, apply_speculation_ceiling


def generate_outlook_candidates(evidence_records, trajectories, ceiling_map):
    out = {}
    for rec in evidence_records or []:
        if rec.get("type") != "OUTLOOK":
            continue
        trajectory_ids = [tid for tid in rec.get("trajectory_ids", []) if tid in trajectories]
        if not trajectory_ids:
            continue  # Trajectory 없이 Outlook 생성 금지
        condition = rec.get("condition")
        if not condition:
            continue  # Condition 없는 Outlook 생성 금지(운영자 지시 12, 43번)
        direction = rec.get("direction")
        if not direction:
            continue
        time_horizon = rec.get("time_horizon")
        if time_horizon not in TIME_HORIZONS:
            time_horizon = "UNKNOWN"
        structural_change_ids = list(rec.get("structural_change_ids", []))
        oid = hash_id("otl", f"{'|'.join(sorted(trajectory_ids))}|{condition}|{direction}")
        shell = new_outlook_shell(oid, sorted(trajectory_ids), structural_change_ids,
                                   rec.get("outlook_type"), condition, direction, time_horizon)
        shell["supporting_evidence_ids"] = list(rec.get("evidence_ids", []))
        shell["counter_evidence_ids"] = list(rec.get("counter_evidence_ids", []))
        shell["assumption_ids"] = list(rec.get("assumption_ids", []))
        shell["uncertainty_ids"] = list(rec.get("uncertainty_ids", []))
        shell["falsifier_ids"] = list(rec.get("falsifier_ids", []))

        ceilings = [trajectories[tid]["epistemic_ceiling"] for tid in trajectory_ids]
        ceiling_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "UNKNOWN": -1}
        ceiling = min(ceilings, key=lambda c: ceiling_order.get(c, -1)) if ceilings else "UNKNOWN"
        shell["epistemic_ceiling"] = ceiling
        base_confidence = min((trajectories[tid]["confidence"] for tid in trajectory_ids),
                               key=lambda c: {"LOW": 0, "MEDIUM": 1, "HIGH": 2}.get(c, 0))
        speculation = compute_speculation_level(lineage_distance=2, assumption_count=len(shell["assumption_ids"]),
                                                 unsupported_transitions=0)
        shell["speculation_level"] = speculation
        confidence = cap_confidence(base_confidence, ceiling)
        shell["confidence"] = apply_speculation_ceiling(confidence, speculation, ceiling)
        out[oid] = shell
    return out
