# PHASE 5E — Falsifier(운영자 지시 19번). Falsifier != Prediction: "이렇게 될 것이다"가
# 아니라 "이것이 관측되면 현재 판단을 철회/수정해야 한다"는 조건이다.
from common import hash_id, valid_target
from schema import new_falsifier_shell


def generate_falsifier_candidates(evidence_records, target_index, existing=None):
    out = {}
    existing = existing or {}
    for rec in evidence_records or []:
        if rec.get("type") != "FALSIFIER":
            continue
        target_type, target_id = rec.get("target_object_type"), rec.get("target_object_id")
        if not valid_target(target_type, target_id, target_index):
            continue
        condition = rec.get("condition")
        condition_type = rec.get("condition_type")
        if not condition or not condition_type:
            continue
        fid = hash_id("fls", f"{target_type}|{target_id}|{condition_type}|{condition}")
        shell = new_falsifier_shell(fid, target_type, target_id, condition_type, condition,
                                     rec.get("observable_indicator"), rec.get("required_scope"))
        shell["evidence_ids"] = list(rec.get("evidence_ids", []))
        shell["first_seen"] = rec.get("first_seen")
        shell["last_seen"] = rec.get("last_seen")
        # 운영자 지시(테스트 12): 조건을 충족하는 observed_evidence_ids가 오면 OBSERVED로 전이한다.
        # 자동 재실행이 사람이 이미 내린 INVALIDATED/NOT_OBSERVED 확정 판단은 덮어쓰지 않는다.
        prev_status = existing.get(fid, {}).get("status")
        if rec.get("observed_evidence_ids") and prev_status not in ("INVALIDATED", "NOT_OBSERVED"):
            shell["status"] = "OBSERVED"
            shell["evidence_ids"] = sorted(set(shell["evidence_ids"]) | set(rec["observed_evidence_ids"]))
        elif prev_status:
            shell["status"] = prev_status
        out[fid] = shell
    return out
