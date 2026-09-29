# PHASE 5G — Policy Trade-off(운영자 지시 14~17번). Trade-off != Disadvantage Only —
# 한 차원의 개선이 다른 차원의 비용/위험이 될 수 있는 구조적 긴장. Evidence가 약하면
# CONFIRMED_TRADEOFF가 아니라 POTENTIAL_TRADEOFF로 남긴다(자동 확정 금지).
from common import hash_id
from schema import new_policy_tradeoff_shell, TRADEOFF_DIMENSIONS


def generate_tradeoff_candidates(evidence_records, policy_options):
    out = {}
    for rec in evidence_records or []:
        if rec.get("type") != "POLICY_TRADEOFF":
            continue
        oid = rec.get("policy_option_id")
        if oid not in policy_options:
            continue
        dim_a, dim_b = rec.get("dimension_a"), rec.get("dimension_b")
        if dim_a not in TRADEOFF_DIMENSIONS or dim_b not in TRADEOFF_DIMENSIONS:
            continue
        mechanism = rec.get("mechanism")
        if not mechanism:
            continue
        evidence_ids = list(rec.get("evidence_ids", []))
        status = "CONFIRMED_TRADEOFF" if evidence_ids else "POTENTIAL_TRADEOFF"
        tid = hash_id("tof", f"{oid}|{dim_a}|{dim_b}|{mechanism}")
        shell = new_policy_tradeoff_shell(tid, oid, dim_a, rec.get("direction_a"), dim_b,
                                           rec.get("direction_b"), mechanism, status)
        shell["supporting_evidence_ids"] = evidence_ids
        shell["counter_evidence_ids"] = list(rec.get("counter_evidence_ids", []))
        shell["uncertainty_ids"] = list(rec.get("uncertainty_ids", []))
        shell["affected_stakeholder_ids"] = list(rec.get("affected_stakeholder_ids", []))
        shell["confidence"] = "MEDIUM" if status == "CONFIRMED_TRADEOFF" else "LOW"
        out[tid] = shell
    return out
