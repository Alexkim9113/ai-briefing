# PHASE 4C — Change Memory + Status History(운영자 지시 17, 18번). 같은 Change가 다시
# 발견되면 새로 만들지 않고 기존 change_id를 UPDATE하고 status_history에 한 줄 추가한다.
import json
from datetime import datetime, timezone
from pathlib import Path

CHANGES_PATH = Path(__file__).resolve().parent / "changes.json"


def _now():
    return datetime.now(timezone.utc).isoformat()


def load_existing_changes():
    if not CHANGES_PATH.exists():
        return {}
    return json.loads(CHANGES_PATH.read_text(encoding="utf-8"))


def _status_from_growth(prev_count, new_count):
    """이전 실행 대비 supporting event 수 변화로 status를 갱신(운영자 지시 5번: status는
    예측이 아니라 관측된 Evidence 상태). 첫 발견은 CANDIDATE."""
    if prev_count is None:
        return "CANDIDATE"
    if new_count > prev_count:
        return "STRENGTHENING" if prev_count > 0 else "EMERGING"
    if new_count == prev_count:
        return "STABLE"
    return "WEAKENING"


def upsert_change(existing, change_id, change_shell):
    prev = existing.get(change_id)
    now = _now()
    if prev is None:
        change_shell["created_at"] = now
        change_shell["updated_at"] = now
        change_shell["status"] = "CANDIDATE"
        change_shell["status_history"] = [{"at": now, "status": "CANDIDATE",
                                            "event_count": change_shell["event_count"]}]
        # Human override는 새 Change에 아직 없으므로 그대로 둠
        return change_shell
    new_status = _status_from_growth(prev.get("event_count"), change_shell["event_count"])
    change_shell["created_at"] = prev.get("created_at", now)
    change_shell["updated_at"] = now
    change_shell["status"] = new_status
    change_shell["override_status"] = prev.get("override_status", "AUTO_CANDIDATE")
    history = prev.get("status_history", [])
    if not history or history[-1]["status"] != new_status:
        history = history + [{"at": now, "status": new_status, "event_count": change_shell["event_count"]}]
    change_shell["status_history"] = history
    return change_shell
