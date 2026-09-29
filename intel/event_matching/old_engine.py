# 기존 intel/event_service.py의 4중 AND 조건을 "쌍(pair)" 단위로 그대로 재현한 것.
# 기존 파일은 전혀 수정하지 않고(운영자 지시 19), 비교 평가를 위해 로직만 여기서 재사용한다.
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
import briefing  # noqa: E402


def _pub_date(item):
    p = item.get("published")
    if not p:
        return None
    try:
        return datetime.fromisoformat(p.replace("Z", "+00:00")).date()
    except Exception:
        return None


def old_engine_merge(a, b):
    """intel/event_service.py의 병합 조건과 동일: entity ∩ + topic 동일 + 날짜<=2일 + 제목유사도>=0.3."""
    topic_a, _ = briefing.topic_of(a)
    topic_b, _ = briefing.topic_of(b)
    ents_a, ents_b = set(briefing.mx_actors(a)), set(briefing.mx_actors(b))
    date_a, date_b = _pub_date(a), _pub_date(b)
    entity_match = bool(ents_a & ents_b)
    topic_match = topic_a == topic_b and topic_a is not None
    dd = abs((date_a - date_b).days) if (date_a and date_b) else None
    date_ok = dd is not None and dd <= 2
    ga = briefing.grams(briefing.title_key(a.get("title_ko") or a["title"]))
    gb = briefing.grams(briefing.title_key(b.get("title_ko") or b["title"]))
    title_sim = (len(ga[0] & gb[0]) / len(ga[0] | gb[0])) if (ga[0] and gb[0]) else 0.0
    return entity_match and topic_match and date_ok and title_sim >= 0.3
