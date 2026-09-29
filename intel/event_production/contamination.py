# PHASE 4B — Market/Analyst Contamination 방지(운영자 지시 5번).
# "대신證 LG전자 목표가" 같은 애널리스트 리포트/시황 기사가 실제 사건(파트너십 등)과
# 같은 Event로 섞이는 걸 막는다. 새 Noise 사전을 또 만들지 않고 기존 briefing.py의
# Noise Engine(STOCK 규칙)을 재사용하고, 부족한 부분만 얇게 보강한다.
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
import briefing  # noqa: E402

# briefing.classify_noise()의 STOCK 규칙은 "주가/실적/배당" 등 시장 반응 기사를 이미 잡아낸다.
# 여기서는 그 중에서도 "애널리스트가 특정 사건을 근거로 목표가/투자의견을 냈다"는, STOCK보다
# 좁은 하위 유형만 추가로 구분한다(증권사명+목표가/투자의견 언급).
import re
_ANALYST_RX = re.compile(r"목표가|투자의견|매수의견|매도의견|target price|price target|rating\b|"
                         r"대신증권|삼성증권|미래에셋|한국투자증권|NH투자증권|키움증권|신한투자증권|"
                         r"DA데이비슨|모건스탠리|골드만삭스|JP모건", re.I)


def market_reaction_type(item):
    """이 문서가 시장/애널리스트 반응 성격인지 판정. None이면 해당 없음."""
    title = item.get("title", "") + " " + (item.get("title_ko") or "")
    try:
        noise = briefing.classify_noise(title, item.get("summary", ""))
    except Exception:
        noise = {"noise_type": None}
    if noise.get("noise_type") == "STOCK":
        if _ANALYST_RX.search(title):
            return "ANALYST_REPORT"
        return "MARKET_REACTION"
    if _ANALYST_RX.search(title):
        return "ANALYST_REPORT"
    return None


def blocks_same_event(a, b):
    """운영자 지시 5번 핵심: 시장/애널리스트 성격 문서 하나와, 그렇지 않은 실제 사건 문서
    하나가 짝지어지면 같은 Event로 자동 Merge하지 않는다(둘 다 시장성격이면 허용 — 같은
    주가 반응을 다룬 기사끼리는 같은 Event일 수 있음)."""
    ma, mb = market_reaction_type(a), market_reaction_type(b)
    return bool(ma) != bool(mb)  # 하나만 시장성격이면 True(차단)
