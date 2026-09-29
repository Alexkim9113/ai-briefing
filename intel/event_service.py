# EVENT: 현실에서 일어난 구체적 사건(운영자 지시 8번 — TOPIC과 혼동 금지: "AI 저작권"은 TOPIC,
# "미국 법원이 특정 AI 학습데이터 사건에서 판결"이 EVENT). 이번 Pilot은 Precision 우선:
# entity + topic + 날짜 근접(<=2일) + 제목 유사도가 모두 맞을 때만 자동 병합하고,
# 하나라도 애매하면 UNRESOLVED로 둔다. 기존 briefing.py의 title 2-gram 유사도(similar/grams)를 그대로 재사용해
# 새 유사도 로직을 따로 만들지 않는다(운영자 지시 10, "새 시스템을 크게 만들지 마라"에 맞춤).
from datetime import datetime

EVENT_STATUS = ("CANDIDATE", "RESOLVED", "UNRESOLVED", "REVIEWED", "REJECTED", "MERGED")
DATE_WINDOW_DAYS = 2


def _pub_date(item):
    p = item.get("published")
    if not p:
        return None
    try:
        return datetime.fromisoformat(p.replace("Z", "+00:00")).date()
    except Exception:
        return None


def _title_similarity(briefing, a, b):
    ga = briefing.grams(briefing.title_key(a.get("title_ko") or a["title"]))
    gb = briefing.grams(briefing.title_key(b.get("title_ko") or b["title"]))
    if not ga[0] or not gb[0]:
        return 0.0
    return len(ga[0] & gb[0]) / len(ga[0] | gb[0])


def cluster_events(briefing, items, normalized_topic_of, normalized_entities_of):
    """보수적 규칙 병합. items는 (document_id, item) 목록. 반환: events dict, doc→event_id 매핑, 근거 로그."""
    events, doc_event, merge_log = {}, {}, []
    n = len(items)
    for i in range(n):
        did_a, a = items[i]
        if did_a in doc_event:
            continue
        topic_a = normalized_topic_of(a)
        ents_a = normalized_entities_of(a)
        date_a = _pub_date(a)
        cluster = [(did_a, a)]
        for j in range(i + 1, n):
            did_b, b = items[j]
            if did_b in doc_event:
                continue
            topic_b, ents_b, date_b = normalized_topic_of(b), normalized_entities_of(b), _pub_date(b)
            entity_match = bool(ents_a & ents_b)
            topic_match = topic_a == topic_b and topic_a is not None
            date_distance = abs((date_a - date_b).days) if (date_a and date_b) else None
            date_ok = date_distance is not None and date_distance <= DATE_WINDOW_DAYS
            title_sim = _title_similarity(briefing, a, b)
            if entity_match and topic_match and date_ok and title_sim >= 0.3:
                cluster.append((did_b, b))
                merge_log.append({"a": did_a, "b": did_b, "merge_method": "rule", "merge_score": round(title_sim, 2),
                                   "merge_evidence": {"entity_match": entity_match, "topic_match": topic_match,
                                                       "date_distance_days": date_distance,
                                                       "title_similarity": round(title_sim, 2)}})
        if len(cluster) > 1:
            eid = f"evt_{did_a}"
            events[eid] = {"event_id": eid, "event_name": (a.get("title_ko") or a["title"])[:80],
                           "document_ids": [d for d, _ in cluster], "date": a.get("published"), "topic": topic_a,
                           "entities": sorted(ents_a), "status": "RESOLVED",
                           "merge_method": "rule", "merge_evidence_count": len(cluster) - 1}
            for d, _ in cluster:
                doc_event[d] = eid
        else:
            doc_event[did_a] = None  # UNRESOLVED(단독 문서, 아직 이벤트 없음)
    return events, doc_event, merge_log
