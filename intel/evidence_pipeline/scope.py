# SCOPE GUARD(운영자 지시 섹션 31, 33). Evidence Pipeline은 5E보다 아래 계층이므로 5E
# 코드를 import하지 않고(계층 역전 금지) 독립적으로 같은 결과 어휘(SCOPE_VERDICT)를 쓴다 —
# 나중에 5E가 이 Layer의 Counter Evidence를 읽을 때 같은 판정 어휘를 재사용할 수 있게.
#
# 핵심 원칙: subject/domain/temporal/population 범위가 다르면 "모순"이 아니라
# "범위가 다른 것"(NO_DIRECT_CONTRADICTION/CONTEXT_DEPENDENT)이다 — EU 규제 Evidence를
# 전세계로 일반화하거나, 미국 설문을 전 인류로 일반화하지 않는다(섹션 33).
from datetime import date, timedelta


def _norm(s):
    return (s or "").strip().lower() or None


def compute_scope_flags(a, b):
    subject_match = _norm(a.get("subject")) == _norm(b.get("subject")) and a.get("subject") is not None
    domain_a, domain_b = set(a.get("domains") or []), set(b.get("domains") or [])
    domain_match = bool(domain_a & domain_b) if (domain_a or domain_b) else None  # 정보 없으면 UNKNOWN
    pop_a, pop_b = a.get("population_scope"), b.get("population_scope")
    population_match = (pop_a == pop_b) if (pop_a or pop_b) else None
    geo_a, geo_b = a.get("geographic_scope"), b.get("geographic_scope")
    geographic_match = (geo_a == geo_b) if (geo_a or geo_b) else None

    temporal_match = None
    da, db = a.get("first_seen"), b.get("first_seen")
    if da and db:
        try:
            d1 = date.fromisoformat(da[:10])
            d2 = date.fromisoformat(db[:10])
            temporal_match = abs((d1 - d2).days) <= 30
        except Exception:
            temporal_match = None

    return {
        "subject_match": subject_match, "domain_match": domain_match,
        "population_match": population_match, "geographic_match": geographic_match,
        "temporal_match": temporal_match,
    }


def classify_pair(flags, opposite_direction):
    """opposite_direction: 텍스트 상 방향/평가가 반대라는 어휘 신호(호출자가 판단해 전달).
    범위(geo/population)가 명확히 다르면 직접 모순이 아니라 범위-종속(CONTEXT_DEPENDENT)."""
    if not opposite_direction:
        return "NO_DIRECT_CONTRADICTION"
    if flags["geographic_match"] is False or flags["population_match"] is False:
        return "CONTEXT_DEPENDENT"
    if flags["subject_match"] and flags["domain_match"] is not False:
        return "DIRECT_CONTRADICTION"
    return "TENSION"
