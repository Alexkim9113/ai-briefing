# PHASE 5B — Pattern Supporting/Contradicting Evidence(운영자 지시 13번). 반대증거가
# 나타나도 Pattern을 지우지 않고 별도 목록에 보존한다.
_OPPOSITE_RELATION = {
    "INCREASES": "DECREASES", "DECREASES": "INCREASES",
    "ENABLES": "CHALLENGES", "CHALLENGES": "ENABLES",
    "SUPPORTS": "CONTRADICTS", "CONTRADICTS": "SUPPORTS",
    "CREATES": "REPLACES", "REPLACES": "CREATES",
}


def find_contradicting_changes(dimensions, own_relation, all_changes, exclude_change_ids):
    """같은 analytic dimension을 공유하지만 반대 relation을 가진 Change를 반대증거로 잡는다.
    삭제하지 않고 목록에만 담는다(운영자 지시 13, 29-7번)."""
    from mechanism import mechanism_fingerprint
    opposite = _OPPOSITE_RELATION.get(own_relation)
    if opposite is None:
        return []
    out = []
    for cid, ch in all_changes.items():
        if cid in exclude_change_ids:
            continue
        fp = mechanism_fingerprint(ch)
        if fp is None:
            continue
        if fp["relation"] == opposite and set(fp["dimensions"]) & set(dimensions):
            out.append(cid)
    return sorted(out)


def change_quality_record(change_id, change):
    """중복 계산 방지용 Evidence 품질 레코드 — Change 1개당 1개(운영자 지시 10번)."""
    return {
        "change_id": change_id,
        "change_confidence": change.get("change_confidence", "LOW"),
        "evidence_strength": change.get("evidence_strength"),
        "event_count": change.get("event_count"),
        "status": change.get("status"),
    }
