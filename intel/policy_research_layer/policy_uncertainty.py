# PHASE 5G — Policy Uncertainty(운영자 지시 26번). 5E Uncertainty를 정책 판단 맥락에서
# 구체화한다 — 5E의 별도 객체이지 이를 대체하지 않는다.
from common import hash_id
from schema import new_policy_uncertainty_shell, POLICY_UNCERTAINTY_TYPES


def generate_policy_uncertainty_candidates(evidence_records, policy_questions, policy_options):
    out = {}
    for rec in evidence_records or []:
        if rec.get("type") != "POLICY_UNCERTAINTY":
            continue
        pqid, oid = rec.get("policy_question_id"), rec.get("policy_option_id")
        if pqid not in policy_questions and oid not in policy_options:
            continue
        uncertainty_type = rec.get("uncertainty_type")
        if uncertainty_type not in POLICY_UNCERTAINTY_TYPES:
            continue
        uid = hash_id("pun", f"{pqid}|{oid}|{uncertainty_type}|{rec.get('description_code', '')}")
        shell = new_policy_uncertainty_shell(uid, pqid if pqid in policy_questions else None,
                                              oid if oid in policy_options else None,
                                              uncertainty_type, rec.get("description_code"))
        shell["supporting_evidence_ids"] = list(rec.get("evidence_ids", []))
        shell["counter_evidence_ids"] = list(rec.get("counter_evidence_ids", []))
        out[uid] = shell
    return out
