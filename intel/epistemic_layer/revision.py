# PHASE 5E — View Revision(운영자 지시 23~26번). METAXIS는 스스로 판단을 수정할 수 있어야
# 한다. 자동 재작성은 규칙 기반 전이(HIGH->MEDIUM 등)까지만 허용 — 상위 테제를 자동으로
# 다시 쓰지 않는다(그건 Human/미래 단계의 몫).
from common import hash_id, valid_target
from schema import new_view_revision_shell, REVISION_REASONS


def generate_view_revision_candidates(evidence_records, target_index, falsifiers_new, falsifiers_existing):
    out = {}
    for rec in evidence_records or []:
        if rec.get("type") != "VIEW_REVISION":
            continue
        target_type, target_id = rec.get("target_object_type"), rec.get("target_object_id")
        if not valid_target(target_type, target_id, target_index):
            continue
        reason = rec.get("revision_reason_type")
        if reason not in REVISION_REASONS:
            continue
        vid = hash_id("rev", f"{target_type}|{target_id}|{reason}|{rec.get('previous_state')}|{rec.get('new_state')}")
        shell = new_view_revision_shell(vid, target_type, target_id, rec.get("previous_state"),
                                         rec.get("new_state"), rec.get("previous_confidence"),
                                         rec.get("new_confidence"), reason)
        shell["trigger_evidence_ids"] = list(rec.get("trigger_evidence_ids", []))
        shell["counter_evidence_ids"] = list(rec.get("counter_evidence_ids", []))
        shell["falsifier_ids"] = list(rec.get("falsifier_ids", []))
        shell["timestamp"] = rec.get("timestamp")
        shell["human_validated"] = bool(rec.get("human_validated", False))
        out[vid] = shell

    # 자동 규칙: Falsifier가 이번 실행에서 UNTESTED(또는 미존재) -> OBSERVED로 전이하면
    # View Revision Candidate를 생성할 수 있다(운영자 지시 테스트 12번). 최종 확정은 Human 몫
    # 이므로 human_validated=False로 둔다.
    for fid, falsifier in falsifiers_new.items():
        prev_status = falsifiers_existing.get(fid, {}).get("status", "UNTESTED")
        if falsifier.get("status") == "OBSERVED" and prev_status != "OBSERVED":
            vid = hash_id("rev", f"FALSIFIER_OBSERVED|{fid}")
            shell = new_view_revision_shell(
                vid, falsifier["target_object_type"], falsifier["target_object_id"],
                previous_state=prev_status, new_state="OBSERVED",
                previous_confidence=None, new_confidence=None, revision_reason_type="FALSIFIER_OBSERVED")
            shell["falsifier_ids"] = [fid]
            shell["trigger_evidence_ids"] = list(falsifier.get("evidence_ids", []))
            out[vid] = shell
    return out
