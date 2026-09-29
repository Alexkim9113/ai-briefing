# PHASE 5C — Transition Fingerprint(운영자 지시 7, 12번). Structural Change의 핵심은 상태
# 전환(FROM->TO)이다. 키워드 fingerprint가 아니라 DIMENSION + relation에서 유도한 구조적
# 상태 전환 클래스를 사용한다. CODE ONLY — 서술문을 지어내지 않고, 구조적 라벨만 만든다.

# Pattern.relation_type(운영자 지시 7번 typed relation)에서 상태 전환 방향을 유도하는 최소
# 규칙표. 매핑에 없으면 (None, None) — 억지 서술 금지, null 허용(운영자 지시 6번).
_RELATION_STATE_SHIFT = {
    "INCREASES": ("LOWER", "HIGHER"),
    "DECREASES": ("HIGHER", "LOWER"),
    "ENABLES": ("RESTRICTED", "ENABLED"),
    "REQUIRES": ("OPTIONAL", "REQUIRED"),
    "DEPENDS_ON": ("INDEPENDENT", "DEPENDENT"),
    "PRESSURES": ("UNPRESSURED", "PRESSURED"),
    "REGULATES": ("UNREGULATED", "REGULATED"),
    "CHALLENGES": ("STABLE", "CONTESTED"),
    "CONTRADICTS": ("ALIGNED", "CONFLICTING"),
    "SUPPORTS": ("WEAK", "REINFORCED"),
    "TRANSFORMS": ("PRIOR_FORM", "NEW_FORM"),
    "REPLACES": ("INCUMBENT", "SUCCESSOR"),
    "CREATES": ("ABSENT", "PRESENT"),
    "LEADS_TO": ("PRIOR_STATE", "RESULTING_STATE"),
    "CAUSES": ("PRIOR_STATE", "CAUSED_STATE"),
    "RELATED_TO": (None, None),
}

_DIMENSION_TO_STRUCTURAL_TYPE = {
    "POWER": "POWER_REALLOCATION", "VALUE": "VALUE_REALLOCATION", "SCARCITY": "SCARCITY_REALLOCATION",
    "DEPENDENCY": "DEPENDENCY_RECONFIGURATION", "CONTROL": "CONTROL_RECONFIGURATION",
    "ACCESS": "ACCESS_RECONFIGURATION", "AUTHORITY": "AUTHORITY_RECONFIGURATION",
    "RESPONSIBILITY": "RESPONSIBILITY_RECONFIGURATION", "LABOR": "LABOR_RECONFIGURATION",
    "INSTITUTION": "INSTITUTIONAL_RECONFIGURATION", "INFRASTRUCTURE": "INFRASTRUCTURE_RECONFIGURATION",
    "HUMAN_AGENCY": "HUMAN_AGENCY_RECONFIGURATION", "CULTURAL_NORM": "CULTURAL_RECONFIGURATION",
    "RESOURCE": "RESOURCE_RECONFIGURATION", "ENVIRONMENTAL_PRESSURE": "ENVIRONMENTAL_RECONFIGURATION",
}


def state_shift_for(dimension, relation):
    frm, to = _RELATION_STATE_SHIFT.get(relation, (None, None))
    if frm is None:
        return None, None
    return f"{dimension}:{frm}", f"{dimension}:{to}"


def structural_change_type_for(dimensions, is_cross_domain):
    """운영자 지시 10번: 억지 분류 금지. 복수 dimension이면 MULTI_DIMENSIONAL,
    실제 Domain(사회적 영역)을 넘어선 확산이면 그 자체는 type이 아니라 cross-domain
    플래그로만 별도 기록(운영자 지시 0-B — event_type 다양성과 혼동 금지)."""
    unique_dims = sorted(set(dimensions))
    if len(unique_dims) >= 2:
        return "MULTI_DIMENSIONAL"
    if len(unique_dims) == 1:
        return _DIMENSION_TO_STRUCTURAL_TYPE.get(unique_dims[0], "OTHER")
    return "OTHER"


def transition_fingerprint(pattern):
    """Pattern 1개를 (dimension, relation) 구조로 축약 — 동일 fingerprint를 가진 서로 다른
    Pattern들만 Structural Change 후보로 묶는다. dimension 목록 중 결정적으로 첫 번째만
    대표값으로 사용(재실행 시 항상 동일)."""
    dims = sorted(pattern.get("analytic_dimensions", []) or pattern.get("dimensions", []))
    relation = pattern.get("relation_type")
    if not dims or not relation:
        return None
    primary_dim = dims[0]
    frm, to = state_shift_for(primary_dim, relation)
    return {
        "dimension": primary_dim, "relation": relation,
        "from_state": frm, "to_state": to,
        "key": (primary_dim, relation),
    }
