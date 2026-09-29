# PHASE 5E — Uncertainty(운영자 지시 17번). Confidence != Uncertainty — confidence가
# HIGH여도 CAUSALITY_UNCERTAIN 등이 공존할 수 있다. UNKNOWN != FALSE/0.
from common import hash_id, valid_target
from schema import new_uncertainty_shell, UNCERTAINTY_TYPES, PRIORITY_LEVELS, UNCERTAINTY_STATUS


def generate_uncertainty_candidates(evidence_records, target_index):
    out = {}
    for rec in evidence_records or []:
        if rec.get("type") != "UNCERTAINTY":
            continue
        target_type, target_id = rec.get("target_object_type"), rec.get("target_object_id")
        if not valid_target(target_type, target_id, target_index):
            continue
        utype = rec.get("uncertainty_type")
        if utype not in UNCERTAINTY_TYPES:
            continue  # 매핑 불가한 타입 억지 분류 금지
        uid = hash_id("unc", f"{target_type}|{target_id}|{utype}|{rec.get('description_code', '')}")
        shell = new_uncertainty_shell(uid, target_type, target_id, utype, rec.get("description_code"),
                                       rec.get("scope"))
        shell["evidence_ids"] = list(rec.get("evidence_ids", []))
        shell["first_seen"] = rec.get("first_seen")
        shell["last_seen"] = rec.get("last_seen")
        severity = rec.get("severity")
        shell["severity"] = severity if severity in PRIORITY_LEVELS else "LOW"
        resolvable = rec.get("resolvable")
        shell["resolvable"] = resolvable if resolvable in (True, False) else "unknown"
        shell["required_evidence_types"] = list(rec.get("required_evidence_types", []))
        # Resolution/Reopen(운영자 지시 30번): 명시적 status_override로만 전이 — 자동 추정 금지.
        status_override = rec.get("status_override")
        if status_override in UNCERTAINTY_STATUS:
            shell["status"] = status_override
        out[uid] = shell
    return out
