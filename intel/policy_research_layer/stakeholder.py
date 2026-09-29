# PHASE 5G — Stakeholder Impact(운영자 지시 18~21번). Impact != Moral Verdict — Benefit/Cost/
# Risk는 기술적 분류일 뿐, "누가 옳다"를 자동 판단하지 않는다. 동일 Option이 stakeholder별로
# 다른 방향의 영향을 가질 수 있음을 평균으로 압축하지 않고 각각 보존한다.
from common import hash_id
from schema import new_stakeholder_impact_shell, STAKEHOLDER_TYPES, IMPACT_DIRECTIONS


def generate_stakeholder_impact_candidates(evidence_records, policy_options):
    out = {}
    for rec in evidence_records or []:
        if rec.get("type") != "STAKEHOLDER_IMPACT":
            continue
        oid = rec.get("policy_option_id")
        if oid not in policy_options:
            continue
        stakeholder_type = rec.get("stakeholder_type")
        direction = rec.get("direction")
        mechanism = rec.get("mechanism")
        if stakeholder_type not in STAKEHOLDER_TYPES or direction not in IMPACT_DIRECTIONS or not mechanism:
            continue
        label = rec.get("stakeholder_id_or_label", stakeholder_type)
        sid = hash_id("sti", f"{oid}|{stakeholder_type}|{label}|{rec.get('impact_dimension')}")
        shell = new_stakeholder_impact_shell(sid, oid, stakeholder_type, label, rec.get("impact_dimension"),
                                              direction, mechanism, rec.get("time_horizon"))
        shell["supporting_evidence_ids"] = list(rec.get("evidence_ids", []))
        shell["counter_evidence_ids"] = list(rec.get("counter_evidence_ids", []))
        shell["uncertainty_ids"] = list(rec.get("uncertainty_ids", []))
        shell["confidence"] = "MEDIUM" if shell["supporting_evidence_ids"] else "LOW"
        out[sid] = shell
    return out
