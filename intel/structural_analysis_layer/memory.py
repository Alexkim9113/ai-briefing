# PHASE 5D — Memory/History(운영자 지시 36번). Driver/Dependency/Control/PowerShift/
# ValueShift/ScarcityShift/Bottleneck 공통 upsert. 값이 바뀔 때만 history에 추가하고,
# Human override는 자동 재실행이 덮어쓰지 않는다(운영자 지시 37번).
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.utc).isoformat()


def upsert_object(existing_collection, obj_id, shell):
    prev = existing_collection.get(obj_id)
    now = _now()

    if prev is None:
        shell["created_at"] = now
        shell["updated_at"] = now
        shell["first_seen"] = shell.get("first_seen") or now
        shell["history"] = [{"at": now, "status": shell["status"], "confidence": shell["confidence"],
                              "evidence_strength": shell.get("evidence_strength")}]
        return shell

    shell["override_status"] = prev.get("override_status", "AUTO_CANDIDATE")
    if prev.get("override_status") == "HUMAN_REJECTED":
        shell["status"] = "HUMAN_REJECTED"
    elif prev.get("override_status") == "HUMAN_CONFIRMED":
        shell["status"] = "HUMAN_CONFIRMED"

    shell["created_at"] = prev.get("created_at", now)
    shell["updated_at"] = now

    history = prev.get("history", [])
    last = history[-1] if history else None
    changed = (last is None or last.get("status") != shell["status"] or last.get("confidence") != shell["confidence"]
               or last.get("evidence_strength") != shell.get("evidence_strength"))
    if changed:
        history = history + [{"at": now, "status": shell["status"], "confidence": shell["confidence"],
                               "evidence_strength": shell.get("evidence_strength")}]
    shell["history"] = history
    return shell


def upsert_collection(existing, new_candidates):
    """새로 감지된 candidates를 기존 컬렉션에 upsert하고, 이번 실행에서 재감지되지 않은
    기존 객체도 보존한다(재발견되지 않았다고 지우지 않는다 — Signal/Pattern Layer와 동일 원칙)."""
    merged = dict(existing)
    for obj_id, shell in new_candidates.items():
        merged[obj_id] = upsert_object(existing, obj_id, shell)
    return merged
