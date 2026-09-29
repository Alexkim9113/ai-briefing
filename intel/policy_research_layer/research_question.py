# PHASE 5G — Research Question(운영자 지시 27~29, 41, 44번). Research Question != Finding.
# Evidence Gap/Uncertainty/Contradiction/Alternative Explanation/Falsifier/Forecast Validation
# Need/Policy Decision Need 중 하나에서 구조적으로 생성 가능 — 단순 관심 주제에서 무한
# 연구 질문을 자동 생성하지 않는다.
from common import hash_id
from schema import new_research_question_shell, RESEARCH_QUESTION_TYPES, PRIORITY_LEVELS


def generate_research_question_candidates(evidence_records, policy_questions):
    out = {}
    for rec in evidence_records or []:
        if rec.get("type") != "RESEARCH_QUESTION":
            continue
        question = rec.get("question")
        question_type = rec.get("question_type")
        if not question or question_type not in RESEARCH_QUESTION_TYPES:
            continue
        evidence_gap_ids = list(rec.get("evidence_gap_ids", []))
        uncertainty_ids = list(rec.get("uncertainty_ids", []))
        related_pq = [pqid for pqid in rec.get("related_policy_question_ids", []) if pqid in policy_questions]
        counter_hypothesis_ids = list(rec.get("counter_hypothesis_ids", []))
        # 생성 근거(운영자 지시 44번): Gap/Uncertainty/Contradiction/Policy Question 연결 중 최소 하나 필요.
        if not (evidence_gap_ids or uncertainty_ids or related_pq or counter_hypothesis_ids):
            continue
        priority = rec.get("priority")
        if priority not in PRIORITY_LEVELS:
            priority = "LOW"
        rid = hash_id("rq", f"{question_type}|{question}")
        shell = new_research_question_shell(rid, question, question_type, rec.get("target_object_type"),
                                             rec.get("target_object_id"), rec.get("population"),
                                             rec.get("geography"), rec.get("time_scope"), priority)
        shell["related_policy_question_ids"] = related_pq
        shell["why_it_matters_code"] = rec.get("why_it_matters_code")
        shell["required_evidence_types"] = list(rec.get("required_evidence_types", []))
        shell["variables_or_constructs"] = list(rec.get("variables_or_constructs", []))
        shell["counter_hypothesis_ids"] = counter_hypothesis_ids
        shell["evidence_gap_ids"] = evidence_gap_ids
        shell["uncertainty_ids"] = uncertainty_ids
        shell["supporting_evidence_ids"] = list(rec.get("evidence_ids", []))
        out[rid] = shell
    return out
