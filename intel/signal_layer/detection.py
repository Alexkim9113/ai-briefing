# PHASE 5A — Signal Detection(운영자 지시 7번). CODE ONLY. Change 상태의 "변화"만 본다 —
# Event나 기사 수를 직접 보지 않는다(Acceptance 1,2,3번: Change 경유 없이 Signal 생성 금지).
from datetime import date

MIN_DELTA_FOR_SIGNAL = 1  # event_count 등이 최소 이만큼 변해야 신호로 본다(잡음 방지)


def _parse_date(s):
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except Exception:
        return None


def _velocity(delta, prev_updated_at, curr_updated_at):
    """단순 기사량 velocity가 아니라, Change 지표(event_count 등)의 변화 속도(운영자 지시 9번)."""
    d0, d1 = _parse_date(prev_updated_at), _parse_date(curr_updated_at)
    if d0 is None or d1 is None or d1 == d0:
        return None
    days = abs((d1 - d0).days) or 1
    return round(delta / days, 3)


def detect_signals_for_change(change, previous_snapshot):
    """하나의 Change에 대해, 이전 스냅샷과 비교해 감지되는 Signal 후보(복수 가능)를 반환.
    REJECTED(override)된 Change는 애초에 호출하는 쪽에서 걸러진다."""
    candidates = []
    change_id = change["change_id"] if "change_id" in change else change.get("change_id")
    prev = previous_snapshot.get(change_id) if previous_snapshot else None

    if prev is None:
        # 처음 관측된 Change — 그 자체가 NEW_CHANGE Signal 후보(운영자 지시 4번)
        candidates.append({
            "signal_type": "NEW_CHANGE", "change_id": change_id,
            "delta": {"event_count": {"previous": None, "current": change["event_count"]}},
            "direction": change["direction"],
        })
        return candidates

    ec_delta = change["event_count"] - prev.get("event_count", 0)
    ed_delta = change["entity_diversity"] - prev.get("entity_diversity", 0)
    dd_delta = change["domain_diversity"] - prev.get("domain_diversity", 0)
    ce_delta = len(change.get("contradicting_event_ids", [])) - len(prev.get("contradicting_event_ids", []))

    if abs(ec_delta) >= MIN_DELTA_FOR_SIGNAL:
        stype = "STRENGTHENING" if ec_delta > 0 else "WEAKENING"
        candidates.append({"signal_type": stype, "change_id": change_id,
                            "delta": {"event_count": {"previous": prev.get("event_count"), "current": change["event_count"]}},
                            "velocity": _velocity(ec_delta, prev.get("updated_at"), change.get("updated_at")),
                            "direction": change["direction"]})

    if change["direction"] != prev.get("direction") and prev.get("direction") not in (None, "OTHER"):
        candidates.append({"signal_type": "REVERSAL", "change_id": change_id,
                            "delta": {"direction": {"previous": prev.get("direction"), "current": change["direction"]}}})

    if dd_delta >= MIN_DELTA_FOR_SIGNAL:
        candidates.append({"signal_type": "CROSS_DOMAIN_SPREAD", "change_id": change_id,
                            "delta": {"domain_diversity": {"previous": prev.get("domain_diversity"), "current": change["domain_diversity"]}}})
    if ed_delta >= MIN_DELTA_FOR_SIGNAL:
        candidates.append({"signal_type": "ENTITY_SPREAD", "change_id": change_id,
                            "delta": {"entity_diversity": {"previous": prev.get("entity_diversity"), "current": change["entity_diversity"]}}})
    if ce_delta >= MIN_DELTA_FOR_SIGNAL:
        candidates.append({"signal_type": "COUNTER_EVIDENCE_RISING", "change_id": change_id,
                            "delta": {"contradicting_count": {"previous": len(prev.get("contradicting_event_ids", [])),
                                                               "current": len(change.get("contradicting_event_ids", []))}}})

    if ec_delta <= 0 and dd_delta <= 0 and ed_delta <= 0 and ce_delta <= 0 and change.get("status") in ("STABLE",):
        candidates.append({"signal_type": "PERSISTENCE", "change_id": change_id,
                            "delta": {"status": {"previous": prev.get("status"), "current": change.get("status")}}})

    return candidates


def maturity_for(signal_type, prev_maturity):
    """Signal maturity 전이(운영자 지시 6번) — 예측 아님, 관측된 Evidence 상태 전이."""
    order = ["WEAK", "EMERGING", "STRENGTHENING", "ESTABLISHED"]
    if signal_type == "NEW_CHANGE":
        return "WEAK"
    if signal_type in ("STRENGTHENING", "CROSS_DOMAIN_SPREAD", "ENTITY_SPREAD", "PERSISTENCE"):
        if prev_maturity in order and order.index(prev_maturity) < len(order) - 1:
            return order[order.index(prev_maturity) + 1]
        return prev_maturity or "EMERGING"
    if signal_type in ("WEAKENING", "COUNTER_EVIDENCE_RISING"):
        return "WEAKENING"
    if signal_type == "REVERSAL":
        return "REVERSING"
    return prev_maturity or "WEAK"
