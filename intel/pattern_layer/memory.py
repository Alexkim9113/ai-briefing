# PHASE 5B — Pattern Memory + History(운영자 지시 16번). 같은 pattern_id가 재관찰되면
# 새로 만들지 않고 UPDATE하며 History에 한 줄씩 누적한다. Human override는 자동 재실행이
# 덮어쓰지 않는다.
import json
from datetime import datetime, timezone
from pathlib import Path

PATTERNS_PATH = Path(__file__).resolve().parent / "patterns.json"


def _now():
    return datetime.now(timezone.utc).isoformat()


def load_existing_patterns(path=PATTERNS_PATH):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _maturity_from_growth(prev_count, new_count, prev_maturity):
    """운영자 지시 15번: 미래예측이 아니라 반복 관찰 상태. change_count 성장 기반 전이."""
    order = ["CANDIDATE", "EMERGING", "RECURRING", "ESTABLISHED"]
    if prev_count is None:
        return "CANDIDATE"
    if new_count > prev_count:
        if prev_maturity in order and order.index(prev_maturity) < len(order) - 1:
            return order[order.index(prev_maturity) + 1]
        return "EMERGING"
    if new_count == prev_count:
        return prev_maturity or "EMERGING"
    return "WEAKENING"


def upsert_pattern(existing, pattern_id, pattern_shell):
    prev = existing.get(pattern_id)
    now = _now()

    if prev is None:
        pattern_shell["created_at"] = now
        pattern_shell["updated_at"] = now
        pattern_shell["first_seen"] = pattern_shell.get("first_seen") or now
        pattern_shell["status_history"] = [{"at": now, "status": pattern_shell["status"]}]
        pattern_shell["maturity_history"] = [{"at": now, "maturity": pattern_shell["maturity"]}]
        pattern_shell["evidence_history"] = [{"at": now, "evidence_strength": pattern_shell.get("evidence_strength")}]
        return pattern_shell

    # Human override는 자동 재실행이 덮어쓰지 않는다(운영자 지시 17번).
    pattern_shell["override_status"] = prev.get("override_status", "AUTO_CANDIDATE")
    if prev.get("override_status") == "HUMAN_REJECTED":
        pattern_shell["status"] = "REJECTED"

    new_maturity = _maturity_from_growth(prev.get("change_count"), pattern_shell["change_count"],
                                          prev.get("maturity"))
    pattern_shell["maturity"] = new_maturity if pattern_shell["status"] != "REJECTED" else prev.get("maturity")
    pattern_shell["created_at"] = prev.get("created_at", now)
    pattern_shell["updated_at"] = now

    status_history = prev.get("status_history", [])
    if not status_history or status_history[-1]["status"] != pattern_shell["status"]:
        status_history = status_history + [{"at": now, "status": pattern_shell["status"]}]
    pattern_shell["status_history"] = status_history

    maturity_history = prev.get("maturity_history", [])
    if not maturity_history or maturity_history[-1]["maturity"] != pattern_shell["maturity"]:
        maturity_history = maturity_history + [{"at": now, "maturity": pattern_shell["maturity"]}]
    pattern_shell["maturity_history"] = maturity_history

    evidence_history = prev.get("evidence_history", [])
    if not evidence_history or evidence_history[-1]["evidence_strength"] != pattern_shell.get("evidence_strength"):
        evidence_history = evidence_history + [{"at": now, "evidence_strength": pattern_shell.get("evidence_strength")}]
    pattern_shell["evidence_history"] = evidence_history

    return pattern_shell
