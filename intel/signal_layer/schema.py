# PHASE 5A — Signal Schema(운영자 지시 5번). CODE ONLY, LLM 미사용.
SIGNAL_TYPES = ("NEW_CHANGE", "STRENGTHENING", "WEAKENING", "REVERSAL", "EXPANSION", "CONTRACTION",
                "CROSS_DOMAIN_SPREAD", "ENTITY_SPREAD", "EVIDENCE_ACCELERATION",
                "COUNTER_EVIDENCE_RISING", "PERSISTENCE", "OTHER")
MATURITY = ("WEAK", "EMERGING", "STRENGTHENING", "ESTABLISHED", "WEAKENING", "REVERSING")
CONFIDENCE_LEVELS = ("LOW", "MEDIUM", "HIGH")  # 가짜 확률 금지(운영자 지시 13번)
OVERRIDE_STATUS = ("AUTO_DETECTED", "HUMAN_CONFIRMED", "HUMAN_REJECTED")
OBSERVATION_WINDOWS_DAYS = (7, 14, 30, 90)  # 지원만 하고, 데이터 없으면 0 Signal(운영자 지시 21번)


def new_signal_shell(signal_id, signal_name, signal_type, change_ids):
    return {
        "signal_id": signal_id, "signal_name": signal_name, "signal_type": signal_type,
        "change_ids": change_ids,
        "first_detected": None, "last_updated": None,
        "direction": None, "maturity": "WEAK",
        "supporting_event_ids": [], "contradicting_event_ids": [],
        "evidence_strength": None, "signal_confidence": "LOW",
        "time_window_days": None,
        "entity_diversity": 0, "domain_diversity": 0,
        "status": "CANDIDATE",
        "override_status": "AUTO_DETECTED",
        "status_history": [], "maturity_history": [], "evidence_history": [],
        "baseline": {"previous_state": None, "current_state": None, "delta": None},
        "created_at": None, "updated_at": None,
    }
