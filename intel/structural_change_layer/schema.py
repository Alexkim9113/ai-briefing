# PHASE 5C — Structural Change Schema(운영자 지시 8번). CODE ONLY, LLM 미사용.

# 운영자 지시 0-A: EVENT TYPE(무슨 종류의 사건)과 DOMAIN(세계의 어느 영역)은 다른 개념이다.
# 이 Layer는 이 둘을 별도 필드로 취급한다. DOMAIN 통제 어휘 — 실제 lineage로 확인되지 않으면
# UNKNOWN을 쓰고 event_type에서 임의로 추측 변환하지 않는다(운영자 지시 0-C).
DOMAINS = ("TECHNOLOGY_INFRASTRUCTURE", "SCIENCE_RESEARCH", "POLICY_LAW_GOVERNANCE",
           "ECONOMY_INDUSTRY_LABOR", "HUMAN_SOCIETY_EDUCATION", "CULTURE_ARTS_MEDIA",
           "SECURITY_GEOPOLITICS", "PLANET", "UNKNOWN")

STRUCTURAL_DIMENSIONS = ("POWER", "VALUE", "SCARCITY", "DEPENDENCY", "CONTROL", "ACCESS",
                          "AUTHORITY", "RESPONSIBILITY", "LABOR", "RIGHTS", "INSTITUTION",
                          "INFRASTRUCTURE", "HUMAN_AGENCY", "CULTURAL_NORM", "RESOURCE",
                          "ENVIRONMENTAL_PRESSURE")

STRUCTURAL_CHANGE_TYPES = ("POWER_REALLOCATION", "VALUE_REALLOCATION", "SCARCITY_REALLOCATION",
                            "DEPENDENCY_RECONFIGURATION", "CONTROL_RECONFIGURATION",
                            "ACCESS_RECONFIGURATION", "AUTHORITY_RECONFIGURATION",
                            "RESPONSIBILITY_RECONFIGURATION", "LABOR_RECONFIGURATION",
                            "INSTITUTIONAL_RECONFIGURATION", "HUMAN_AGENCY_RECONFIGURATION",
                            "CULTURAL_RECONFIGURATION", "RESOURCE_RECONFIGURATION",
                            "INFRASTRUCTURE_RECONFIGURATION", "ENVIRONMENTAL_RECONFIGURATION",
                            "MULTI_DIMENSIONAL", "OTHER")

MATURITY = ("CANDIDATE", "EMERGING", "DEVELOPING", "ESTABLISHED", "WEAKENING", "REVERSING", "BROKEN")
CONFIDENCE_LEVELS = ("LOW", "MEDIUM", "HIGH")  # 가짜 확률 금지(운영자 지시 18번)
OVERRIDE_STATUS = ("AUTO_CANDIDATE", "HUMAN_CONFIRMED", "HUMAN_REJECTED")

MIN_INDEPENDENT_PATTERNS = 2  # 운영자 지시 4번
MAX_PATTERN_OVERLAP_RATIO = 0.5  # 운영자 지시 13번: Evidence 과대평가 방지 임계값


def new_structural_change_shell(structural_change_id, name, statement, structural_change_type,
                                 dimensions, from_state, to_state):
    return {
        "structural_change_id": structural_change_id,
        "structural_change_name": name, "structural_change_statement": statement,
        "structural_change_type": structural_change_type,
        "from_state": from_state, "to_state": to_state,
        "dimensions": dimensions,

        # 운영자 지시 0-A/0-B: event_type과 domain은 분리된 별도 필드.
        "event_types": [], "domains": [],

        "supporting_pattern_ids": [], "supporting_signal_ids": [], "supporting_change_ids": [],
        "contradicting_pattern_ids": [], "contradicting_signal_ids": [], "contradicting_change_ids": [],

        "entities": [], "institutions": [], "resources": [],

        "first_seen": None, "last_seen": None, "time_span_days": 0,

        "pattern_count": 0,
        # 운영자 지시 0-D: 서로 다른 independence 개념을 절대 혼용하지 않는다.
        # 실제 lineage로 확인 불가능한 지표는 0이 아니라 None(UNKNOWN)으로 남긴다.
        "independent_pattern_count": 0,
        "independent_signal_count": 0,
        "independent_change_count": 0,
        "independent_event_count": None,
        "independent_document_count": None,
        "independent_source_count": None,

        "domain_diversity": 0, "event_type_diversity": 0, "entity_diversity": 0,
        "pattern_overlap_ratio": None,

        "evidence_strength": None, "structural_confidence": "LOW",

        "maturity": "CANDIDATE", "status": "CANDIDATE", "override_status": "AUTO_CANDIDATE",

        "status_history": [], "maturity_history": [], "evidence_history": [], "revision_history": [],

        # 운영자 지시 9번: 확장 가능 구조 필드 — 현재 Evidence 없으면 빈 배열.
        "potential_gainers": [], "potential_losers": [],
        "value_shift": [], "scarcity_shift": [], "dependency_shift": [], "control_shift": [],
        "access_shift": [], "authority_shift": [], "responsibility_shift": [],
        "bottlenecks": [], "uncertainties": [],

        # 운영자 지시 20, 27번: 향후 확장 — 이번 Phase에서 생성하지 않음.
        "related_pattern_ids": [], "predecessor_pattern_ids": [],
        "first_order_effects": [], "second_order_effects": [], "third_order_effects": [],
        "historical_analogies": [], "historical_predecessors": [],

        "created_at": None, "updated_at": None,
    }
