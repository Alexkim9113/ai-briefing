# PHASE 4A — Structured Candidate Score. AND 조건 대신 신호별 가중 합산 + 명백한 충돌 감점.
# ML 모델 아님(운영자 지시 6번) — 사람이 읽을 수 있는 규칙과 숫자만 사용.
from .signals import compute_signals, document_type_of

STATES = ("CONFIRMED", "CANDIDATE", "UNRESOLVED", "REJECTED")

# 임계값은 Gold Test Set 결과를 보고 정함(운영자 지시 6번) — gold_set.py 평가로 확정한 값.
T_CONFIRMED = 7.0
T_CANDIDATE = 4.0


def score_pair(a, b):
    """반환: (score, state, positive_evidence[], negative_evidence[], signals dict)."""
    sig = compute_signals(a, b)
    pos, neg = [], []
    score = 0.0

    # identifier: 명확히 다른 논문을 가리키면 즉시 REJECT(가장 강한 부정 증거)
    if sig["exact_identifier_match"] is True:
        score += 10
        pos.append("EXACT_IDENTIFIER_MATCH")
    elif sig["exact_identifier_match"] is False:
        neg.append("IDENTIFIER_MISMATCH")
        return round(score, 2), "REJECTED", pos, neg, sig

    # entity overlap: strong
    n_ent = len(sig["canonical_entity_overlap"])
    if n_ent >= 1:
        score += 3 + min(n_ent - 1, 2)  # 겹치는 entity가 많을수록 조금 더(최대 +2 추가)
        pos.append(f"CANONICAL_ENTITY_OVERLAP({n_ent})")
    else:
        neg.append("NO_SHARED_ENTITY")
        score -= 1

    # distinctive term overlap: strong (일반 AI 낱말은 mx_keywords가 이미 걸러냄)
    n_term = len(sig["distinctive_term_overlap"])
    if n_term >= 1:
        score += 3 + min(n_term - 1, 2)
        pos.append(f"DISTINCTIVE_TERM_OVERLAP({n_term})")
    else:
        neg.append("NO_SHARED_DISTINCTIVE_TERM")

    # date: medium, 그리고 큰 날짜 차이는 명백한 부정 증거
    dd = sig["event_date_distance_days"]
    if dd is not None:
        if dd <= 1:
            score += 1.5
            pos.append("DATE_ADJACENT(<=1d)")
        elif dd <= 2:
            score += 1.0
            pos.append("DATE_CLOSE(<=2d)")
        elif dd > 5:
            score -= 2
            neg.append(f"LARGE_DATE_DISTANCE({dd}d)")

    # title similarity: medium
    ts = sig["title_similarity"]
    if ts >= 0.3:
        score += 1.5
        pos.append(f"TITLE_SIMILARITY({ts})")
    elif ts >= 0.15:
        score += 0.5

    # action compatibility: medium, 명백히 다른 행위면 부정 증거(운영자 지시 5,7번 핵심)
    if sig["action_compatible"] is True:
        score += 2
        pos.append(f"ACTION_MATCH({sig['action_family_a']})")
    elif sig["action_compatible"] is False:
        score -= 3
        neg.append(f"ACTION_FAMILY_MISMATCH({sig['action_family_a']} vs {sig['action_family_b']})")

    # document type: 비호환이면 감점(예: RESEARCH vs NEWS인데 서로 다른 논문)
    if sig["document_type_compatible"]:
        score += 1
    else:
        score -= 2
        neg.append("DOCUMENT_TYPE_INCOMPATIBLE")

    # topic: weak — 단독으로는 거의 영향 없음(운영자 지시: TOPIC만으로 EVENT 판정 금지)
    if sig["topic_compatible"]:
        score += 0.5

    # 운영자 지시 7번 핵심 가드: SAME ENTITY + SAME DATE만으로는 CONFIRMED에 못 올라가게
    # (entity 3~5 + date 1.5 + topic 0.5 = 최대 7.0이지만, action_compatible이 None이고
    # distinctive term/title이 전혀 없으면 여기서 이미 미달이거나 딱 걸치는 수준 — 아래
    # 명시적 가드로 한 번 더 강제한다)
    only_entity_and_date = (n_ent >= 1 and n_term == 0 and ts < 0.15 and sig["action_compatible"] is not True)
    if only_entity_and_date and score >= T_CONFIRMED:
        score = T_CONFIRMED - 0.5  # CONFIRMED 문턱 바로 아래로 강제 하향 → CANDIDATE까지만

    # Papers 전용 정책(운영자 지시 9번): identifier 없는 논문 쌍은 절대 CONFIRMED 불가
    if document_type_of(a) == "RESEARCH" and document_type_of(b) == "RESEARCH" and sig["exact_identifier_match"] is not True:
        score = min(score, T_CONFIRMED - 0.5)
        neg.append("PAPERS_WITHOUT_IDENTIFIER_CAPPED")

    # 발견한 문제(Shadow Run에서 확인): entity가 전혀 안 겹치는데도 action_family만 같고
    # ("raises"/"acquires" 같은 동사 자체가 mx_keywords에 "고유명사"처럼 걸려 distinctive
    # term으로 오인되는 경우) date가 가까우면 CONFIRMED까지 올라가는 사례 발견(서로 다른
    # 두 회사의 개별 투자유치/인수를 하나로 오합). SAME ACTION + 우연한 날짜 근접만으로는
    # 절대 CONFIRMED에 올릴 수 없다는 가드를 명시적으로 추가한다.
    if n_ent == 0 and sig["exact_identifier_match"] is not True and ts < 0.3:
        score = min(score, T_CONFIRMED - 0.5)
        neg.append("NO_ENTITY_ANCHOR_CAPPED")

    if score >= T_CONFIRMED:
        state = "CONFIRMED"
    elif score >= T_CANDIDATE:
        state = "CANDIDATE"
    else:
        state = "UNRESOLVED"
    return round(score, 2), state, pos, neg, sig
