# PHASE 5B — Pattern Schema(운영자 지시 8번). CODE ONLY, LLM 미사용.
PATTERN_TYPES = ("POWER_SHIFT", "VALUE_SHIFT", "SCARCITY_SHIFT", "DEPENDENCY_SHIFT",
                  "CONTROL_SHIFT", "ACCESS_SHIFT", "AUTHORITY_SHIFT", "RESPONSIBILITY_SHIFT",
                  "LABOR_RECONFIGURATION", "INSTITUTIONAL_CHANGE", "CULTURAL_CHANGE",
                  "RESOURCE_PRESSURE", "CROSS_DOMAIN_MECHANISM", "OTHER")

# 운영자 지시 6번: controlled analytic dimensions, 강제 분류 목록 아님.
ANALYTIC_DIMENSIONS = ("POWER", "VALUE", "SCARCITY", "DEPENDENCY", "CONTROL", "ACCESS",
                        "AUTHORITY", "RESPONSIBILITY", "LABOR", "RIGHTS", "INFRASTRUCTURE",
                        "RESOURCE", "INSTITUTION", "CULTURAL_NORM", "HUMAN_AGENCY",
                        "ENVIRONMENTAL_PRESSURE")

# 운영자 지시 7번: 기존 Knowledge Model 방향과 호환되는 typed relation.
RELATION_TYPES = ("CAUSES", "INCREASES", "DECREASES", "ENABLES", "REQUIRES", "DEPENDS_ON",
                   "PRESSURES", "REGULATES", "CHALLENGES", "CONTRADICTS", "SUPPORTS",
                   "TRANSFORMS", "REPLACES", "CREATES", "LEADS_TO", "RELATED_TO")

MATURITY = ("CANDIDATE", "EMERGING", "RECURRING", "ESTABLISHED", "WEAKENING", "BREAKING")
CONFIDENCE_LEVELS = ("LOW", "MEDIUM", "HIGH")  # 가짜 확률 금지(운영자 지시 14번)
OVERRIDE_STATUS = ("AUTO_CANDIDATE", "HUMAN_CONFIRMED", "HUMAN_REJECTED")

MIN_INDEPENDENT_CHANGES = 2  # 운영자 지시 4번: 최소 2개 독립 Change 또는 2개 서로 다른 Signal family


def new_pattern_shell(pattern_id, pattern_name, pattern_statement, pattern_type, analytic_dimensions):
    return {
        "pattern_id": pattern_id, "pattern_name": pattern_name, "pattern_statement": pattern_statement,
        "pattern_type": pattern_type, "analytic_dimensions": analytic_dimensions,
        "relation_type": None,
        "supporting_change_ids": [], "supporting_signal_ids": [],
        "contradicting_change_ids": [], "contradicting_signal_ids": [],
        "domains": [], "entities": [],
        "first_seen": None, "last_seen": None, "time_span_days": 0,
        "change_count": 0, "signal_count": 0, "domain_diversity": 0, "entity_diversity": 0,
        "evidence_strength": None, "pattern_confidence": "LOW",
        "maturity": "CANDIDATE", "status": "CANDIDATE",
        "override_status": "AUTO_CANDIDATE",
        "related_pattern_ids": [], "predecessor_pattern_ids": [],
        "status_history": [], "maturity_history": [], "evidence_history": [],
        "created_at": None, "updated_at": None,
    }
