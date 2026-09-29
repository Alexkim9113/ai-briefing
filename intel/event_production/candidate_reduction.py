# PHASE 4B — Candidate Explosion 해결(운영자 지시 9번). 1,727개를 사람이 다 볼 수 없으므로
# 점수 구간으로 좁혀서, CONFIRMED 경계에 가깝고 실제 검토 가치가 있는 것만 사람 눈앞에 둔다.
HIGH_REVIEW_MIN = 6.0    # CONFIRMED(7.0) 바로 아래 — 경계에 가장 가까운 애매한 쌍
LOW_CONFIDENCE_MIN = 4.0  # 그 아래는 참고용으로만 저장, Review Queue에는 안 올림


def bucket(candidate_pairs):
    high, low = [], []
    for c in candidate_pairs:
        if c["score"] >= HIGH_REVIEW_MIN:
            high.append({**c, "review_bucket": "HIGH_REVIEW"})
        elif c["score"] >= LOW_CONFIDENCE_MIN:
            low.append({**c, "review_bucket": "LOW_CONFIDENCE"})
        # LOW_CONFIDENCE_MIN 미만은 UNRESOLVED로만 남기고 저장하지 않음(9번: 절대 전수를 사람이 보게 하지 않음)
    return high, low
