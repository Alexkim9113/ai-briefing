# PHASE 5E — Alternative Explanation(운영자 지시 21~22번). 하나의 관찰에 여러 근거-기반
# 메커니즘이 가능할 때 모두 보존한다 — 자동으로 "승자"를 고르지 않는다.
# Evidence 없는 설명은 절대 생성하지 않는다(운영자 지시 21번).
from common import hash_id, valid_target
from schema import new_alternative_explanation_shell


def generate_alternative_explanation_candidates(evidence_records, target_index):
    out = {}
    for rec in evidence_records or []:
        if rec.get("type") != "ALTERNATIVE_EXPLANATION":
            continue
        target_type, target_id = rec.get("target_object_type"), rec.get("target_object_id")
        if not valid_target(target_type, target_id, target_index):
            continue
        statement = rec.get("explanation_code_or_statement")
        supporting = list(rec.get("supporting_evidence_ids", []))
        if not statement or not supporting:
            continue  # Evidence 없는 설명 생성 금지
        eid = hash_id("alt", f"{target_type}|{target_id}|{statement}")
        shell = new_alternative_explanation_shell(eid, target_type, target_id, statement)
        shell["supporting_evidence_ids"] = supporting
        shell["challenging_evidence_ids"] = list(rec.get("challenging_evidence_ids", []))
        shell["evidence_ids"] = sorted(set(supporting) | set(shell["challenging_evidence_ids"]))
        shell["first_seen"] = rec.get("first_seen")
        shell["last_seen"] = rec.get("last_seen")
        out[eid] = shell
    return out
