# PHASE 4B — Event Fingerprint + ONGOING ISSUE 분리(운영자 지시 3, 4번).
# EVENT FINGERPRINT = WHO(canonical entities) + DID WHAT(action family) + TO/ABOUT WHAT
# (distinctive terms) + WHEN(date bucket). "빌 게이츠 AI 우려"처럼 같은 인물이 여러 날에
# 걸쳐 비슷한 취지의 발언을 반복하는 경우(ONGOING ISSUE)를, 특정 날짜의 특정 발언 하나
# (EVENT)와 구분한다.
from datetime import datetime

# 반복 발언성 행위(성명·경고·발표)는 같은 인물이 여러 날 여러 매체에 비슷한 말을 해도
# 매번 "새 사건"처럼 보이기 쉽다 — 이 행위군은 날짜창을 좁히고, 이걸로 만들어지는
# 클러스터 크기를 제한해 ONGOING ISSUE로 새는 걸 막는다.
# 발견한 문제(Production Shadow Run): REGULATE도 "AI 규제 논쟁"처럼 여러 날 여러 당사자가
# 각자 다른 발언을 하는 진행형 이슈가 되기 쉬워 추가함(빌 게이츠 면담 요청과 실제 백악관
# 회동, 교황 비판이 한 클러스터에 섞이는 오염을 확인).
RECURRING_STATEMENT_ACTIONS = {"WARN", "ANNOUNCE", "REGULATE"}
STATEMENT_CLUSTER_CAP = 3  # 이 이상 묶이면 나머지는 ONGOING_ISSUE로 분리
STATEMENT_DATE_WINDOW_DAYS = 1  # 성명류는 날짜창을 2일→1일로 좁힘


def date_bucket(item):
    p = item.get("published")
    if not p:
        return None
    try:
        return datetime.fromisoformat(p.replace("Z", "+00:00")).date().isoformat()
    except Exception:
        return None


def fingerprint(entities, action, distinctive_terms, date):
    """WHO+DID WHAT+ABOUT WHAT+WHEN. 사람이 읽을 수 있는 튜플 — 임베딩 아님."""
    return (tuple(sorted(entities)), action, tuple(sorted(distinctive_terms)[:3]), date)


def is_recurring_statement_pair(sig):
    """같은 인물/기관의 반복적 성명류 행위인지(TOPIC/ONGOING ISSUE 오염 위험이 높은 유형)."""
    return sig["action_family_a"] in RECURRING_STATEMENT_ACTIONS and sig["action_family_b"] in RECURRING_STATEMENT_ACTIONS
