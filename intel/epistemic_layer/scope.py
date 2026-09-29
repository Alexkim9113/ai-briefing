# PHASE 5E — Scope Guard + Contradiction/Tension/Paradox 분류 Dispatcher
# (운영자 지시 8~16번). CONTRADICTION != TENSION != PARADOX를 코드로 강제하는 핵심 모듈.
#
# 입력 "Claim Record" 스키마(명시적으로 제공되어야 함 — 텍스트에서 추론하지 않음):
#   target_object_type, target_object_id, subject, object, domain, population,
#   time_period, context, measurement, relation, dimension, direction
# 각 필드가 없으면 "모른다"(None)이지 "다르다/같다"가 아니다 — UNKNOWN != FALSE 원칙(운영자
# 지시 2번)을 스코프 비교에도 그대로 적용한다.

from schema import PARADOX_RULE_MATRIX

SCOPE_FIELDS = ("subject", "object", "entity", "domain", "population",
                "time_period", "context", "measurement", "relation")


def _field_match(a, b, field):
    va, vb = a.get(field), b.get(field)
    if va is None or vb is None:
        return None  # UNKNOWN - 있다/없다를 함부로 단정하지 않는다
    return va == vb


def compute_scope_flags(claim_a, claim_b):
    """9개 매칭 플래그(subject/object/entity/domain/population/temporal/context/
    measurement/relation_match)를 계산한다. True/False/None(unknown) 중 하나."""
    flags = {}
    for field in SCOPE_FIELDS:
        key = "temporal_match" if field == "time_period" else f"{field}_match"
        flags[key] = _field_match(claim_a, claim_b, field)
    flags["scope_match"] = all(v is True for v in flags.values()) if all(
        v is not None for v in flags.values()) else (
        False if any(v is False for v in flags.values()) else None)
    return flags


def classify_pair(claim_a, claim_b):
    """(category, dimension_or_pair, scope_flags) 반환. category는 다음 중 하나:
    DIRECT_CONTRADICTION, TEMPORAL_REVERSAL_CANDIDATE, NO_DIRECT_CONTRADICTION,
    CONTEXT_DEPENDENT, PARADOX_CANDIDATE, TENSION, None(관계 없음).
    Contradiction!=Tension, Contradiction!=Paradox를 이 함수 하나로 강제한다."""
    dim_a, dim_b = claim_a.get("dimension"), claim_b.get("dimension")
    flags = compute_scope_flags(claim_a, claim_b)

    if dim_a and dim_b and dim_a != dim_b:
        # 서로 다른 차원 — 동시에 참일 수 있음 -> Contradiction 후보 자체가 아님(운영자 지시 15번)
        pair_key = frozenset({dim_a, dim_b})
        if pair_key in PARADOX_RULE_MATRIX and flags["scope_match"] is not False:
            return "PARADOX_CANDIDATE", pair_key, flags
        return "TENSION", pair_key, flags

    if dim_a and dim_b and dim_a == dim_b:
        dir_a, dir_b = claim_a.get("direction"), claim_b.get("direction")
        if dir_a is None or dir_b is None or dir_a == dir_b:
            return None, dim_a, flags  # 방향이 같거나 모르면 충돌 후보 아님
        # 방향이 반대 — Scope Guard 통과 여부를 확인해야 진짜 Contradiction (운영자 지시 8번)
        if flags["temporal_match"] is False:
            return "TEMPORAL_REVERSAL_CANDIDATE", dim_a, flags  # Temporal Guard
        if flags["domain_match"] is False or flags["population_match"] is False:
            return "NO_DIRECT_CONTRADICTION", dim_a, flags  # Geo/Population Guard
        core = ("subject_match", "object_match", "domain_match", "population_match",
                "temporal_match", "context_match", "measurement_match")
        if all(flags.get(f) is True for f in core):
            return "DIRECT_CONTRADICTION", dim_a, flags
        return "CONTEXT_DEPENDENT", dim_a, flags

    return None, None, flags
