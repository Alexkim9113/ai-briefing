# PHASE 5F — Alternative Path(운영자 지시 13~16, 44번). Evidence-backed branching factor
# (Counter Evidence/Alternative Explanation/Falsifier/명시적 제약)가 있어야만 생성된다 —
# 근거 없는 "다른 미래도 가능하다"를 자동 생성하지 않는다. BASE_PATH != Most Likely.
from common import hash_id, cap_confidence
from schema import new_alternative_path_shell, PATH_TYPES, TIME_HORIZONS
from speculation import compute_speculation_level, apply_speculation_ceiling


def generate_alternative_path_candidates(evidence_records, trajectories, ceiling_map):
    out = {}
    for rec in evidence_records or []:
        if rec.get("type") != "ALTERNATIVE_PATH":
            continue
        trajectory_ids = [tid for tid in rec.get("trajectory_ids", []) if tid in trajectories]
        if not trajectory_ids:
            continue
        trigger_conditions = list(rec.get("trigger_conditions", []))
        branching_evidence = (list(rec.get("counter_evidence_ids", [])) +
                               list(rec.get("alternative_explanation_ids", [])) +
                               list(rec.get("falsifier_ids", [])))
        path_type = rec.get("path_type")
        if path_type not in PATH_TYPES:
            continue
        # BASE_PATH는 현재 관찰된 방향의 reference path이므로 별도 branching evidence 불필요.
        if path_type != "BASE_PATH" and not (trigger_conditions and branching_evidence):
            continue  # Evidence-backed branching factor 없이 대안 경로 생성 금지
        if not rec.get("path_name"):
            continue
        time_horizon = rec.get("time_horizon")
        if time_horizon not in TIME_HORIZONS:
            time_horizon = "UNKNOWN"
        pid = hash_id("pth", f"{'|'.join(sorted(trajectory_ids))}|{path_type}|{rec['path_name']}")
        shell = new_alternative_path_shell(pid, sorted(trajectory_ids), rec["path_name"], path_type,
                                            trigger_conditions, list(rec.get("required_assumptions", [])),
                                            time_horizon)
        shell["supporting_evidence_ids"] = list(rec.get("evidence_ids", []))
        shell["counter_evidence_ids"] = list(rec.get("counter_evidence_ids", []))
        shell["uncertainty_ids"] = list(rec.get("uncertainty_ids", []))
        shell["falsifier_ids"] = list(rec.get("falsifier_ids", []))
        shell["assumption_ids"] = list(rec.get("assumption_ids", []))
        shell["early_indicators"] = list(rec.get("early_indicators", []))
        shell["path_dependency_ids"] = list(rec.get("path_dependency_ids", []))

        ceilings = [trajectories[tid]["epistemic_ceiling"] for tid in trajectory_ids]
        ceiling_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "UNKNOWN": -1}
        ceiling = min(ceilings, key=lambda c: ceiling_order.get(c, -1)) if ceilings else "UNKNOWN"
        shell["epistemic_ceiling"] = ceiling
        speculation = compute_speculation_level(lineage_distance=2,
                                                 assumption_count=len(shell["assumption_ids"]),
                                                 unsupported_transitions=0 if path_type == "BASE_PATH" else 0)
        shell["speculation_level"] = speculation if path_type != "BASE_PATH" else "LOW"
        confidence = cap_confidence("MEDIUM" if branching_evidence or path_type == "BASE_PATH" else "LOW", ceiling)
        shell["confidence"] = apply_speculation_ceiling(confidence, shell["speculation_level"], ceiling)
        out[pid] = shell
    return out
