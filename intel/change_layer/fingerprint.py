# PHASE 4C — Change Fingerprint(운영자 지시 9번). SUBJECT+DIRECTION+OBJECT+MECHANISM.
# 사람이 읽을 수 있는 구조체 — 임베딩 아님, LLM 아님.
DIRECTION_LABEL_KO = {
    "EXPANDING": "확대", "CONTRACTING": "축소", "SHIFTING": "이동", "ACCELERATING": "가속",
    "SLOWING": "둔화", "CONCENTRATING": "집중", "DECENTRALIZING": "분산", "INCREASING": "증가",
    "DECREASING": "감소", "FRAGMENTING": "분화", "CONVERGING": "수렴", "OTHER": "변화",
}

# Event Type/Action Family 조합에서 방향성을 유추하는 최소 규칙(운영자 지시 6번: 억지 분류 금지,
# 매핑에 없으면 OTHER). 단일 사건이 아니라 "여러 사건에 걸친 다수결 방향"에 쓴다.
_ACTION_DIRECTION_HINTS = {
    "RELEASE": "EXPANDING", "WITHDRAW": "CONTRACTING", "REGULATE": "SHIFTING",
    "INVESTIGATE": "SHIFTING", "BAN": "CONTRACTING", "APPROVE": "EXPANDING",
    "INVEST": "EXPANDING", "PARTNER": "EXPANDING", "ACQUIRE": "CONCENTRATING",
    "WARN": "SHIFTING", "ANNOUNCE": "SHIFTING", "MEET": "SHIFTING",
}


def infer_direction(action_families):
    """여러 Event의 action_family 다수결로 방향을 추정. 뚜렷한 다수가 없으면 SHIFTING(가장 중립적)."""
    from collections import Counter
    votes = Counter()
    for af in action_families:
        d = _ACTION_DIRECTION_HINTS.get(af)
        if d:
            votes[d] += 1
    if not votes:
        return "OTHER"
    top, n = votes.most_common(1)[0]
    if n < len(action_families) / 2:
        return "SHIFTING"  # 방향이 갈리면 "이동 중"이 가장 정직한 표현
    return top


def change_fingerprint(subject_entities, direction, obj_term, mechanism_terms):
    return {
        "subject": sorted(subject_entities), "direction": direction,
        "object": obj_term, "mechanism": sorted(mechanism_terms)[:3],
    }
