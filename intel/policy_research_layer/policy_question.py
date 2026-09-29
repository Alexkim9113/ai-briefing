# PHASE 5G — Policy Question(운영자 지시 5~8, 43번). Policy Question != Recommendation.
# 5F Futures Assessment를 통과한 Structural Change에 대해, 명시적 decision issue(trigger
# conditions)가 있을 때만 생성한다 — Document/Event에서 직접 생성하지 않는다.
from common import hash_id, valid_structural_change
from schema import new_policy_question_shell, POLICY_QUESTION_TYPES, DECISION_LEVELS, JURISDICTIONS


def generate_policy_question_candidates(evidence_records, target_index):
    out = {}
    for rec in evidence_records or []:
        if rec.get("type") != "POLICY_QUESTION":
            continue
        scids = [s for s in rec.get("target_structural_change_ids", []) if valid_structural_change(s, target_index)]
        if not scids:
            continue  # 5F Bypass 금지 — Futures Assessment 없는 Structural Change 제외
        question = rec.get("question")
        question_type = rec.get("question_type")
        trigger_conditions = list(rec.get("trigger_conditions", []))
        if not question or question_type not in POLICY_QUESTION_TYPES or not trigger_conditions:
            continue  # 명시적 decision issue(trigger_conditions) 없으면 생성 금지
        decision_level = rec.get("decision_level")
        if decision_level not in DECISION_LEVELS:
            decision_level = "UNKNOWN"
        pid = hash_id("pq", f"{'|'.join(sorted(scids))}|{question_type}|{question}")
        shell = new_policy_question_shell(pid, question, question_type, sorted(scids),
                                           list(rec.get("futures_assessment_ids", [])),
                                           list(rec.get("affected_domains", [])), decision_level)
        shell["trigger_conditions"] = trigger_conditions
        shell["decision_horizon"] = rec.get("decision_horizon")
        shell["supporting_evidence_ids"] = list(rec.get("evidence_ids", []))
        shell["counter_evidence_ids"] = list(rec.get("counter_evidence_ids", []))
        shell["uncertainty_ids"] = list(rec.get("uncertainty_ids", []))
        shell["assumption_ids"] = list(rec.get("assumption_ids", []))
        shell["falsifier_ids"] = list(rec.get("falsifier_ids", []))
        shell["evidence_gap_ids"] = list(rec.get("evidence_gap_ids", []))
        shell["stakeholder_ids"] = list(rec.get("stakeholder_ids", []))
        jurisdiction = rec.get("jurisdiction")
        shell["jurisdiction"] = jurisdiction if jurisdiction in JURISDICTIONS else "UNKNOWN"
        shell["epistemic_ceiling"] = rec.get("epistemic_ceiling", "UNKNOWN")
        out[pid] = shell
    return out
