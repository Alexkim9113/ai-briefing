# PHASE 5A — Signal Memory + History(운영자 지시 15, 16번). 같은 signal_id가 재감지되면
# 새로 만들지 않고 기존 항목을 UPDATE하며 status_history/maturity_history/evidence_history에
# 한 줄씩 누적한다. Human override는 자동 재실행으로 덮어쓰지 않는다.
import json
from datetime import datetime, timezone
from pathlib import Path

SIGNALS_PATH = Path(__file__).resolve().parent / "signals.json"


def _now():
    return datetime.now(timezone.utc).isoformat()


def load_existing_signals(path=SIGNALS_PATH):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def upsert_signal(existing, signal_id, signal_shell):
    prev = existing.get(signal_id)
    now = _now()
    if prev is None:
        signal_shell["created_at"] = now
        signal_shell["updated_at"] = now
        signal_shell["first_detected"] = now
        signal_shell["last_updated"] = now
        signal_shell["status_history"] = [{"at": now, "status": signal_shell["status"],
                                            "signal_type": signal_shell["signal_type"]}]
        signal_shell["maturity_history"] = [{"at": now, "maturity": signal_shell["maturity"]}]
        signal_shell["evidence_history"] = [{"at": now, "evidence_strength": signal_shell.get("evidence_strength")}]
        return signal_shell

    # Human override는 자동 재실행이 덮어쓰지 않는다(운영자 지시 16번).
    signal_shell["override_status"] = prev.get("override_status", "AUTO_DETECTED")
    if prev.get("override_status") == "HUMAN_REJECTED":
        signal_shell["status"] = "REJECTED"

    signal_shell["created_at"] = prev.get("created_at", now)
    signal_shell["first_detected"] = prev.get("first_detected", now)
    signal_shell["updated_at"] = now
    signal_shell["last_updated"] = now

    status_history = prev.get("status_history", [])
    if not status_history or status_history[-1]["status"] != signal_shell["status"]:
        status_history = status_history + [{"at": now, "status": signal_shell["status"],
                                             "signal_type": signal_shell["signal_type"]}]
    signal_shell["status_history"] = status_history

    maturity_history = prev.get("maturity_history", [])
    if not maturity_history or maturity_history[-1]["maturity"] != signal_shell["maturity"]:
        maturity_history = maturity_history + [{"at": now, "maturity": signal_shell["maturity"]}]
    signal_shell["maturity_history"] = maturity_history

    evidence_history = prev.get("evidence_history", [])
    if not evidence_history or evidence_history[-1]["evidence_strength"] != signal_shell.get("evidence_strength"):
        evidence_history = evidence_history + [{"at": now, "evidence_strength": signal_shell.get("evidence_strength")}]
    signal_shell["evidence_history"] = evidence_history

    return signal_shell
