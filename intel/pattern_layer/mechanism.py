# PHASE 5B — Pattern Fingerprint / Mechanism(운영자 지시 5, 6, 7번). 키워드 공통점이 아니라
# ACTOR_TYPE + MECHANISM(RELATION) + DIRECTION + AFFECTED analytic dimension 구조로 판정한다.
# CODE ONLY, LLM 미사용.

# Change/Event의 domains(=event_type 목록, intel/event_production/event_type.py의
# EVENT_TYPES 어휘)를 analytic dimension으로 매핑하는 규칙표. 불확실하면 매핑하지 않는다
# (강제 분류 금지 — 운영자 지시 6번은 목록이지 강제 분류표가 아님).
_DOMAIN_TO_DIMENSION = {
    "MODEL_RELEASE": "CONTROL", "PRODUCT_RELEASE": "ACCESS",
    "RESEARCH_PUBLICATION": "VALUE", "POLICY_ANNOUNCEMENT": "AUTHORITY",
    "LAW_ENACTMENT": "AUTHORITY", "COURT_DECISION": "AUTHORITY",
    "REGULATORY_ACTION": "CONTROL", "COMPANY_ACTION": "POWER",
    "PARTNERSHIP": "DEPENDENCY", "FUNDING": "RESOURCE",
    "INFRASTRUCTURE": "INFRASTRUCTURE", "SECURITY_INCIDENT": "RISK_ACCESS",
    "PUBLIC_STATEMENT": "CULTURAL_NORM", "LEGAL_ACTION": "RESPONSIBILITY",
    "LABOR_CHANGE": "LABOR", "CULTURAL_CHANGE": "CULTURAL_NORM",
    "ENVIRONMENTAL_IMPACT": "ENVIRONMENTAL_PRESSURE",
}
# SECURITY_INCIDENT은 ANALYTIC_DIMENSIONS 표준 어휘에 없으므로 가장 가까운 ACCESS로 정규화.
_DIMENSION_ALIAS = {"RISK_ACCESS": "ACCESS"}

# Change Direction(운영자 지시 15개 값, intel/change_layer/schema.py)을 typed relation으로
# 매핑하는 최소 규칙. 불확실하면 RELATED_TO(가장 약한 관계)로만 표현.
_DIRECTION_TO_RELATION = {
    "EXPANDING": "INCREASES", "CONTRACTING": "DECREASES", "INCREASING": "INCREASES",
    "DECREASING": "DECREASES", "ACCELERATING": "INCREASES", "SLOWING": "DECREASES",
    "CONCENTRATING": "REQUIRES", "DECENTRALIZING": "ENABLES",
    "FRAGMENTING": "CHALLENGES", "CONVERGING": "SUPPORTS", "SHIFTING": "TRANSFORMS",
    "OTHER": "RELATED_TO",
}

# (dimension, relation) 조합에서 pattern_type을 유추하는 최소 규칙. 없으면 OTHER
# (운영자 지시 9번: 억지 분류 금지, 불명확하면 OTHER).
_DIMENSION_TO_PATTERN_TYPE = {
    "POWER": "POWER_SHIFT", "VALUE": "VALUE_SHIFT", "SCARCITY": "SCARCITY_SHIFT",
    "DEPENDENCY": "DEPENDENCY_SHIFT", "CONTROL": "CONTROL_SHIFT", "ACCESS": "ACCESS_SHIFT",
    "AUTHORITY": "AUTHORITY_SHIFT", "RESPONSIBILITY": "RESPONSIBILITY_SHIFT",
    "LABOR": "LABOR_RECONFIGURATION", "RESOURCE": "RESOURCE_PRESSURE",
    "INFRASTRUCTURE": "INSTITUTIONAL_CHANGE", "CULTURAL_NORM": "CULTURAL_CHANGE",
}


def dimension_for_domain(domain):
    d = _DOMAIN_TO_DIMENSION.get(domain)
    return _DIMENSION_ALIAS.get(d, d)


def relation_for_direction(direction):
    return _DIRECTION_TO_RELATION.get(direction, "RELATED_TO")


def pattern_type_for(dimensions, is_cross_domain):
    """서로 다른 Domain(사건 종류)에 걸쳐 같은 mechanism(relation+dimension)이 반복되면
    CROSS_DOMAIN_MECHANISM을 우선 부여한다(운영자 지시 12번) — dimension 자체가 여러 개일
    필요는 없다; 서로 다른 Domain의 사건들이 같은 구조를 공유한다는 사실 자체가 중요하다."""
    if is_cross_domain:
        return "CROSS_DOMAIN_MECHANISM"
    for d in dimensions:
        if d in _DIMENSION_TO_PATTERN_TYPE:
            return _DIMENSION_TO_PATTERN_TYPE[d]
    return "OTHER"


def mechanism_fingerprint(change):
    """Change 하나를 (relation, dimension) 구조로 축약. 동일 fingerprint를 가진 서로 다른
    Change들만 Pattern 후보로 묶는다 — 단어/인물/회사/토픽 겹침이 아니라 구조 겹침(운영자 지시 11번)."""
    relation = relation_for_direction(change.get("direction"))
    dims = sorted({dimension_for_domain(d) for d in change.get("domains", []) if dimension_for_domain(d)})
    if not dims:
        return None  # 매핑 불가 — 억지로 묶지 않음
    # 대표 dimension: 가장 먼저 알려진 것(결정적, 재실행 시 항상 동일)
    primary_dim = dims[0]
    return {"relation": relation, "dimensions": tuple(dims), "primary_dimension": primary_dim,
            "key": (relation, tuple(dims))}
