# PHASE 5C — Structural Change Memory + History(운영자 지시 20, 21, 23번). 동일 구조적
# 전환은 매 실행마다 새 객체로 만들지 않고 UPDATE한다. revision_history는 from_state/
# to_state/statement/confidence 판단이 바뀔 때 이전 판단을 지우지 않고 기록한다.
import json
from datetime import datetime, timezone
from pathlib import Path

STRUCTURAL_CHANGES_PATH = Path(__file__).resolve().parent / "structural_changes.json"


def _now():
    return datetime.now(timezone.utc).isoformat()


def load_existing(path=STRUCTURAL_CHANGES_PATH):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _maturity_from_growth(prev_count, new_count, prev_maturity):
    order = ["CANDIDATE", "EMERGING", "DEVELOPING", "ESTABLISHED"]
    if prev_count is None:
        return "CANDIDATE"
    if new_count > prev_count:
        if prev_maturity in order and order.index(prev_maturity) < len(order) - 1:
            return order[order.index(prev_maturity) + 1]
        return "EMERGING"
    if new_count == prev_count:
        return prev_maturity or "EMERGING"
    return "WEAKENING"


def upsert_structural_change(existing, sc_id, shell):
    prev = existing.get(sc_id)
    now = _now()

    if prev is None:
        shell["created_at"] = now
        shell["updated_at"] = now
        shell["first_seen"] = shell.get("first_seen") or now
        shell["status_history"] = [{"at": now, "status": shell["status"]}]
        shell["maturity_history"] = [{"at": now, "maturity": shell["maturity"]}]
        shell["evidence_history"] = [{"at": now, "evidence_strength": shell.get("evidence_strength")}]
        shell["revision_history"] = [{
            "at": now, "previous_statement": None, "new_statement": shell["structural_change_statement"],
            "previous_from_state": None, "new_from_state": shell["from_state"],
            "previous_to_state": None, "new_to_state": shell["to_state"],
            "previous_confidence": None, "new_confidence": shell["structural_confidence"],
            "revision_reason": "INITIAL_OBSERVATION",
        }]
        return shell

    # Human override는 자동 재실행이 덮어쓰지 않는다(운영자 지시 22번).
    shell["override_status"] = prev.get("override_status", "AUTO_CANDIDATE")
    if prev.get("override_status") == "HUMAN_REJECTED":
        shell["status"] = "REJECTED"

    new_maturity = _maturity_from_growth(prev.get("pattern_count"), shell["pattern_count"], prev.get("maturity"))
    shell["maturity"] = new_maturity if shell["status"] != "REJECTED" else prev.get("maturity")
    shell["created_at"] = prev.get("created_at", now)
    shell["updated_at"] = now

    status_history = prev.get("status_history", [])
    if not status_history or status_history[-1]["status"] != shell["status"]:
        status_history = status_history + [{"at": now, "status": shell["status"]}]
    shell["status_history"] = status_history

    maturity_history = prev.get("maturity_history", [])
    if not maturity_history or maturity_history[-1]["maturity"] != shell["maturity"]:
        maturity_history = maturity_history + [{"at": now, "maturity": shell["maturity"]}]
    shell["maturity_history"] = maturity_history

    evidence_history = prev.get("evidence_history", [])
    if not evidence_history or evidence_history[-1]["evidence_strength"] != shell.get("evidence_strength"):
        evidence_history = evidence_history + [{"at": now, "evidence_strength": shell.get("evidence_strength")}]
    shell["evidence_history"] = evidence_history

    revision_history = prev.get("revision_history", [])
    changed = (prev.get("structural_change_statement") != shell["structural_change_statement"]
               or prev.get("from_state") != shell["from_state"]
               or prev.get("to_state") != shell["to_state"]
               or prev.get("structural_confidence") != shell["structural_confidence"])
    if changed:
        revision_history = revision_history + [{
            "at": now,
            "previous_statement": prev.get("structural_change_statement"),
            "new_statement": shell["structural_change_statement"],
            "previous_from_state": prev.get("from_state"), "new_from_state": shell["from_state"],
            "previous_to_state": prev.get("to_state"), "new_to_state": shell["to_state"],
            "previous_confidence": prev.get("structural_confidence"),
            "new_confidence": shell["structural_confidence"],
            "revision_reason": "EVIDENCE_UPDATE",
        }]
    shell["revision_history"] = revision_history

    return shell
