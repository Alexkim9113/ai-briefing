# PHASE 5C — Supporting/Counter Evidence(운영자 지시 16, 17번). 반대증거가 나타나도
# Structural Change를 삭제하지 않고 별도 목록에 보존한다.
_OPPOSITE_RELATION = {
    "INCREASES": "DECREASES", "DECREASES": "INCREASES",
    "ENABLES": "CHALLENGES", "CHALLENGES": "ENABLES",
    "SUPPORTS": "CONTRADICTS", "CONTRADICTS": "SUPPORTS",
    "CREATES": "REPLACES", "REPLACES": "CREATES",
}


def find_contradicting_patterns(dimension, own_relation, all_patterns, exclude_pattern_ids):
    """같은 dimension을 공유하지만 반대 relation을 가진 Pattern을 반대증거로 잡는다.
    삭제하지 않고 목록에만 담는다(운영자 지시 17번)."""
    from transition import transition_fingerprint
    opposite = _OPPOSITE_RELATION.get(own_relation)
    if opposite is None:
        return []
    out = []
    for pid, pat in all_patterns.items():
        if pid in exclude_pattern_ids:
            continue
        fp = transition_fingerprint(pat)
        if fp is None:
            continue
        if fp["dimension"] == dimension and fp["relation"] == opposite:
            out.append(pid)
    return sorted(out)


def pattern_quality_record(pattern_id, pattern):
    """중복 계산 방지용 Evidence 품질 레코드 — Pattern 1개당 1개(운영자 지시 16번)."""
    return {
        "pattern_id": pattern_id,
        "pattern_confidence": pattern.get("pattern_confidence", "LOW"),
        "evidence_strength": pattern.get("evidence_strength"),
        "change_count": pattern.get("change_count"),
        "status": pattern.get("status"),
    }
