# PHASE 5F — Forecast(운영자 지시 32~34, 56번). Forecast != Scenario: 나중에 맞았는지
# 검토 가능한 조건부 판단 기록. observable_indicators가 없으면 검증 불가능하므로 생성 금지.
# 숫자 정확도(Brier score 등) 생성 금지 — qualitative status만 사용.
from common import hash_id, cap_confidence
from schema import new_forecast_shell, TIME_HORIZONS
from speculation import compute_speculation_level, apply_speculation_ceiling


def generate_forecast_candidates(evidence_records, target_index, ceiling_map):
    out = {}
    for rec in evidence_records or []:
        if rec.get("type") != "FORECAST":
            continue
        statement = rec.get("forecast_statement")
        target = rec.get("target")
        observable_indicators = list(rec.get("observable_indicators", []))
        if not statement or not target or not observable_indicators:
            continue  # 검증 불가능한 Forecast 생성 금지
        time_horizon = rec.get("time_horizon")
        if time_horizon not in TIME_HORIZONS:
            time_horizon = "UNKNOWN"
        target_type, target_id = target.get("type"), target.get("id")
        from common import valid_target
        if not valid_target(target_type, target_id, target_index):
            continue
        fid = hash_id("fcs", f"{statement}|{target_type}|{target_id}")
        shell = new_forecast_shell(fid, statement, target, rec.get("baseline_date"), time_horizon,
                                    rec.get("expected_direction"), list(rec.get("conditions", [])),
                                    observable_indicators)
        shell["supporting_evidence_ids"] = list(rec.get("evidence_ids", []))
        shell["counter_evidence_ids"] = list(rec.get("counter_evidence_ids", []))
        shell["assumption_ids"] = list(rec.get("assumption_ids", []))
        shell["uncertainty_ids"] = list(rec.get("uncertainty_ids", []))
        shell["falsifier_ids"] = list(rec.get("falsifier_ids", []))

        ceiling = ceiling_map.get((target_type, target_id), "UNKNOWN")
        shell["epistemic_ceiling"] = ceiling
        speculation = compute_speculation_level(lineage_distance=2, assumption_count=len(shell["assumption_ids"]),
                                                 unsupported_transitions=0)
        shell["speculation_level"] = speculation
        confidence = cap_confidence("MEDIUM" if shell["supporting_evidence_ids"] else "LOW", ceiling)
        shell["confidence"] = apply_speculation_ceiling(confidence, speculation, ceiling)
        out[fid] = shell
    return out
