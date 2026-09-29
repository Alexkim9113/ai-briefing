# PHASE 5E — Memory/History(운영자 지시 35번). 5D memory.py와 동일한 패턴: 값이 바뀔 때만
# history에 추가하고, 재감지되지 않은 기존 객체도 삭제하지 않는다. Resolution/Reopen도
# 이 upsert 경로를 통해 history에 남는다(운영자 지시 29~30번).
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.utc).isoformat()


def _status_field(shell):
    for f in ("status", "assessment_status"):
        if f in shell:
            return f
    return None


def upsert_object(existing_collection, obj_id, shell):
    prev = existing_collection.get(obj_id)
    now = _now()
    status_field = _status_field(shell)

    if prev is None:
        if "created_at" in shell:
            shell["created_at"] = now
        if "updated_at" in shell:
            shell["updated_at"] = now
        if "first_seen" in shell:
            shell["first_seen"] = shell.get("first_seen") or now
        if "history" in shell:
            entry = {"at": now}
            if status_field:
                entry["status"] = shell[status_field]
            if "confidence" in shell:
                entry["confidence"] = shell["confidence"]
            shell["history"] = [entry]
        return shell

    if "override_status" in shell:
        shell["override_status"] = prev.get("override_status", "AUTO_CANDIDATE")
        if prev.get("override_status") == "HUMAN_REJECTED" and status_field:
            shell[status_field] = "HUMAN_REJECTED"
        elif prev.get("override_status") == "HUMAN_CONFIRMED" and status_field:
            shell[status_field] = "HUMAN_CONFIRMED"

    if "created_at" in shell:
        shell["created_at"] = prev.get("created_at", now)
    if "updated_at" in shell:
        shell["updated_at"] = now

    if "history" in shell:
        history = prev.get("history", [])
        last = history[-1] if history else None
        changed = last is None
        if not changed and status_field:
            changed = last.get("status") != shell.get(status_field)
        if not changed and "confidence" in shell:
            changed = last.get("confidence") != shell.get("confidence")
        if changed:
            entry = {"at": now}
            if status_field:
                entry["status"] = shell[status_field]
            if "confidence" in shell:
                entry["confidence"] = shell["confidence"]
            history = history + [entry]
        shell["history"] = history
    return shell


def upsert_collection(existing, new_candidates):
    """이번 실행에서 재감지되지 않은 기존 객체도 dict(existing) 기반으로 보존한다 —
    5A에서 발견됐던 memory 유실 버그를 5E에서도 반복하지 않는다."""
    merged = dict(existing)
    for obj_id, shell in new_candidates.items():
        merged[obj_id] = upsert_object(existing, obj_id, shell)
    return merged
