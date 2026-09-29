# PHASE 5G — Policy Option(운영자 지시 9~13, 43번). Option != Recommendation, NO_ACTION도
# 정식 옵션이다. 명시적 structured option record가 있을 때만 생성 — LLM의 "가능한 정책
# 10개" 자동 발명 금지. 자동 승자/랭킹/복합 점수 절대 생성하지 않는다.
from common import hash_id
from schema import new_policy_option_shell, OPTION_TYPES, JURISDICTIONS


def generate_policy_option_candidates(evidence_records, policy_questions):
    out = {}
    for rec in evidence_records or []:
        if rec.get("type") != "POLICY_OPTION":
            continue
        pqid = rec.get("policy_question_id")
        if pqid not in policy_questions:
            continue
        option_name = rec.get("option_name")
        option_type = rec.get("option_type")
        mechanism = rec.get("mechanism")
        if not option_name or option_type not in OPTION_TYPES:
            continue
        if option_type != "NO_ACTION" and not mechanism:
            continue  # NO_ACTION 외에는 mechanism 필수(구조화된 옵션 레코드)
        oid = hash_id("opt", f"{pqid}|{option_type}|{option_name}")
        shell = new_policy_option_shell(oid, pqid, option_name, option_type, mechanism,
                                         rec.get("target_actor"), rec.get("implementation_level"))
        shell["required_conditions"] = list(rec.get("required_conditions", []))
        shell["expected_first_order_effects"] = list(rec.get("expected_first_order_effects", []))
        shell["related_second_order_effect_ids"] = list(rec.get("related_second_order_effect_ids", []))
        shell["related_third_order_effect_ids"] = list(rec.get("related_third_order_effect_ids", []))
        shell["supporting_evidence_ids"] = list(rec.get("evidence_ids", []))
        shell["counter_evidence_ids"] = list(rec.get("counter_evidence_ids", []))
        shell["uncertainty_ids"] = list(rec.get("uncertainty_ids", []))
        shell["assumption_ids"] = list(rec.get("assumption_ids", []))
        shell["falsifier_ids"] = list(rec.get("falsifier_ids", []))
        shell["normative_assumption_ids"] = list(rec.get("normative_assumption_ids", []))
        jurisdiction = rec.get("jurisdiction")
        shell["jurisdiction"] = jurisdiction if jurisdiction in JURISDICTIONS else "UNKNOWN"
        shell["valid_from"] = rec.get("valid_from")
        shell["valid_to"] = rec.get("valid_to")
        shell["last_verified_at"] = rec.get("last_verified_at")
        # Feasibility != Desirability(운영자 지시 25, 46번): Evidence로 명시된 값만 반영,
        # 없으면 NOT_ASSESSED — feasibility가 POSITIVE라고 desirability를 자동 도출하지 않는다.
        evaluation = dict(shell["evaluation"])
        for k in evaluation:
            v = rec.get(f"evaluation_{k}")
            from schema import EVALUATION_VALUES
            evaluation[k] = v if v in EVALUATION_VALUES else "NOT_ASSESSED"
        shell["evaluation"] = evaluation
        shell["epistemic_ceiling"] = rec.get("epistemic_ceiling", "UNKNOWN")
        out[oid] = shell
    return out
