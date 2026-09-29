# PHASE 5G — Evidence Need(운영자 지시 33~35번). Evidence Need != Counter Evidence —
# 필요한 Evidence가 없다는 것이 반대 Evidence가 있다는 뜻은 아니다(5E 원칙 유지).
from common import hash_id
from schema import new_evidence_need_shell, PRIORITY_LEVELS


def generate_evidence_need_candidates(evidence_records, research_questions, policy_questions):
    out = {}
    for rec in evidence_records or []:
        if rec.get("type") != "EVIDENCE_NEED":
            continue
        evidence_type = rec.get("evidence_type")
        description_code = rec.get("description_code")
        if not evidence_type or not description_code:
            continue
        related_rq = [rid for rid in rec.get("related_research_question_ids", []) if rid in research_questions]
        related_pq = [pqid for pqid in rec.get("related_policy_question_ids", []) if pqid in policy_questions]
        if not related_rq and not related_pq:
            continue  # 근거 없는 Evidence Need 생성 금지
        priority = rec.get("priority")
        if priority not in PRIORITY_LEVELS:
            priority = "LOW"
        eid = hash_id("eneed", f"{evidence_type}|{description_code}|{'|'.join(sorted(related_rq + related_pq))}")
        shell = new_evidence_need_shell(eid, rec.get("target_object_type"), rec.get("target_object_id"),
                                         evidence_type, description_code, rec.get("required_scope"),
                                         priority, rec.get("collection_method_type"))
        shell["related_research_question_ids"] = related_rq
        shell["related_policy_question_ids"] = related_pq
        shell["related_monitoring_indicator_ids"] = list(rec.get("related_monitoring_indicator_ids", []))
        out[eid] = shell
    return out
