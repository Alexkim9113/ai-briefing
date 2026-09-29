# Memory/History — claims/evidence_records 공통 upsert. 재실행 시 이번에 재감지되지 않은
# 기존 객체도 보존한다(삭제 안 함). Human Override는 자동 재실행이 덮어쓰지 않는다(overrides.py
# 가 그 다음 단계에서 적용).
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.utc).isoformat()


def upsert_object(existing_collection, obj_id, shell, status_field):
    prev = existing_collection.get(obj_id)
    now = _now()
    if prev is None:
        shell["history"] = [{"at": now, status_field: shell.get(status_field)}]
        return shell

    shell["created_at"] = prev.get("created_at", shell.get("created_at", now))
    if prev.get("human_review_status") in ("HUMAN_CONFIRMED", "HUMAN_REJECTED", "HUMAN_EDITED"):
        shell["human_review_status"] = prev["human_review_status"]

    history = prev.get("history", [])
    last = history[-1] if history else None
    if last is None or last.get(status_field) != shell.get(status_field):
        history = history + [{"at": now, status_field: shell.get(status_field)}]
    shell["history"] = history
    return shell


def upsert_collection(existing, new_items, id_field, status_field):
    merged = dict(existing)
    for item in new_items:
        oid = item[id_field]
        merged[oid] = upsert_object(existing, oid, item, status_field)
    return merged
