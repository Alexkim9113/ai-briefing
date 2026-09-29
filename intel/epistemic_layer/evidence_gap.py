# PHASE 5E — Evidence Gap(운영자 지시 20번). Missing Evidence != Counter Evidence —
# 반박 근거가 아니라 "판단에 필요한데 아직 없는 정보"다.
from common import hash_id, valid_target
from schema import new_evidence_gap_shell, PRIORITY_LEVELS


def generate_evidence_gap_candidates(evidence_records, target_index):
    out = {}
    for rec in evidence_records or []:
        if rec.get("type") != "EVIDENCE_GAP":
            continue
        target_type, target_id = rec.get("target_object_type"), rec.get("target_object_id")
        if not valid_target(target_type, target_id, target_index):
            continue
        gap_type = rec.get("gap_type")
        missing_evidence_type = rec.get("missing_evidence_type")
        if not gap_type or not missing_evidence_type:
            continue
        gid = hash_id("gap", f"{target_type}|{target_id}|{gap_type}|{missing_evidence_type}")
        priority = rec.get("priority")
        shell = new_evidence_gap_shell(gid, target_type, target_id, gap_type, missing_evidence_type,
                                        rec.get("why_needed_code"),
                                        priority if priority in PRIORITY_LEVELS else "LOW")
        resolvable = rec.get("resolvable")
        shell["resolvable"] = resolvable if resolvable in (True, False) else "unknown"
        shell["first_seen"] = rec.get("first_seen")
        shell["last_seen"] = rec.get("last_seen")
        # Resolution/Reopen(운영자 지시 30번): 명시적 status_override로만 전이 — 자동 추정 금지.
        status_override = rec.get("status_override")
        from schema import EVIDENCE_GAP_STATUS
        if status_override in EVIDENCE_GAP_STATUS:
            shell["status"] = status_override
        out[gid] = shell
    return out
