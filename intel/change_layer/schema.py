# PHASE 4C — CHANGE Schema(운영자 지시 5번). CODE ONLY, LLM 미사용.
CHANGE_STATUS = ("CANDIDATE", "EMERGING", "STRENGTHENING", "STABLE", "WEAKENING", "REVERSING", "REJECTED")
DIRECTIONS = ("INCREASING", "DECREASING", "EXPANDING", "CONTRACTING", "SHIFTING", "CONCENTRATING",
              "DECENTRALIZING", "ACCELERATING", "SLOWING", "FRAGMENTING", "CONVERGING", "OTHER")
CONFIDENCE_LEVELS = ("LOW", "MEDIUM", "HIGH")  # 가짜 정밀 확률(0.73 등) 금지 — 운영자 지시 14번
OVERRIDE_STATUS = ("AUTO_CANDIDATE", "HUMAN_CONFIRMED", "HUMAN_REJECTED")

MIN_SUPPORTING_EVENTS = 2  # 운영자 지시 2번: 최소 2개, 권장 3개 이상


def new_change_shell(change_id, change_name, change_statement, direction):
    return {
        "change_id": change_id, "change_name": change_name, "change_statement": change_statement,
        "direction": direction, "status": "CANDIDATE",
        "first_seen": None, "last_seen": None,
        "supporting_event_ids": [], "contradicting_event_ids": [],
        "event_count": 0, "independent_source_count": 0, "entity_diversity": 0,
        "domain_diversity": 0, "time_span_days": 0,
        "topics": [], "domains": [], "entities": [],
        "evidence_strength": None, "change_confidence": "LOW",
        "override_status": "AUTO_CANDIDATE",
        "status_history": [],
        "created_at": None, "updated_at": None,
    }
