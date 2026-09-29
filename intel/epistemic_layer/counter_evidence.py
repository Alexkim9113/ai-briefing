# PHASE 5E — Counter Evidence(운영자 지시 5번). Counter Evidence != Refutation:
# 대상 객체(Structural Change/Driver/.../Structural Analysis)를 절대 삭제하지 않는다 —
# confidence/uncertainty/revision-candidate 변화만 가능하게 한다.
# Missing Evidence != Counter Evidence(운영자 지시 14번): 명시적 COUNTER_EVIDENCE 타입
# Record만 취급하고, Evidence가 그냥 없는 경우는 evidence_gap.py의 몫이다.
from common import hash_id, valid_target, fill_common_evidence
from schema import new_counter_evidence_shell, COUNTER_EVIDENCE_RELATIONS


def generate_counter_evidence_candidates(evidence_records, target_index):
    out = {}
    for rec in evidence_records or []:
        if rec.get("type") != "COUNTER_EVIDENCE":
            continue
        target_type, target_id = rec.get("target_object_type"), rec.get("target_object_id")
        if not valid_target(target_type, target_id, target_index):
            continue  # 5D 대상 없이 5E 객체 없음
        evidence_type = rec.get("evidence_type")
        if not evidence_type:
            continue
        relationship = rec.get("relationship", "UNKNOWN")
        if relationship not in COUNTER_EVIDENCE_RELATIONS:
            relationship = "UNKNOWN"
        scope = rec.get("scope")
        ceid = hash_id("ce", f"{target_type}|{target_id}|{evidence_type}|{relationship}")
        shell = new_counter_evidence_shell(ceid, target_type, target_id, evidence_type, relationship, scope)
        shell = fill_common_evidence(shell, rec)
        out[ceid] = shell
    return out
