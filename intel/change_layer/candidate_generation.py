# PHASE 4C — Change Candidate Generation. CODE ONLY(운영자 지시 7,15번).
# Production Event(intel/event_production/production_events.json)만 입력으로 쓴다 —
# Document를 직접 보지 않는다(Master Chain: DOCUMENT→EVENT→CHANGE 순서 유지).
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "intel"))
from event_matching.signals import distinctive_terms  # noqa: E402  — object/mechanism 후보 추출 재사용

from schema import MIN_SUPPORTING_EVENTS
from fingerprint import infer_direction, change_fingerprint

MIN_ENTITY_DIVERSITY = 2  # 운영자 지시 8번 가드: entity가 전부 같으면(=한 회사 얘기) Change 아님


# 발견한 문제(Pilot 1차 실행): event_matching.distinctive_terms()는 EVENT 매칭용으로는
# 충분히 구체적이지만("모델"/"기술" 등만 걸러냄), CHANGE의 OBJECT로 쓰기엔 여전히 너무
# 일반적인 업무 동사/명사("개발","자사","판매","아모데"처럼 사람 이름이 잘못 잘린 조각 등)가
# 새서 전부 FALSE CONNECTION으로 이어졌다. CHANGE 후보 생성에서만 한 겹 더 거른다.
_TOO_GENERIC_FOR_CHANGE_OBJECT = {
    "개발", "자사", "판매", "발표", "공개", "출시", "도입", "강화", "확대", "추진", "운영",
    "서비스", "제공", "계획", "전략", "협력", "진행", "검토", "논의", "시작", "마련",
    "development", "sale", "service", "plan", "strategy",
}


def _event_object_terms(event, raw_items_by_id):
    """Event의 대표(anchor=primary_document) 문서에서 object/mechanism 후보 낱말을 뽑는다.
    event_matching.distinctive_terms()를 재사용하되, CHANGE 후보 전용으로 한 번 더 거른다."""
    anchor = raw_items_by_id.get(event.get("primary_document_id"))
    if not anchor:
        return set()
    terms = distinctive_terms(anchor)
    return {t for t in terms if t.lower() not in _TOO_GENERIC_FOR_CHANGE_OBJECT and len(t) >= 2}


def generate_candidates(events, raw_items_by_id):
    """공유 object 낱말(=distinctive term) 기준으로 Event를 묶는다. TOPIC-only 방지를 위해
    entity_diversity(서로 다른 회사/기관 수) >= 2를 반드시 요구한다(운영자 지시 8번) —
    "AI 규제"라는 낱말 하나로 서로 무관한 정책들을 묶는 실수를 code로 막는다."""
    term_index = defaultdict(list)  # term -> [event_id]
    event_terms = {}
    for eid, ev in events.items():
        terms = _event_object_terms(ev, raw_items_by_id)
        event_terms[eid] = terms
        for t in terms:
            term_index[t].append(eid)

    candidates = []
    seen_group_keys = set()
    for term, eids in term_index.items():
        eids = sorted(set(eids))
        if len(eids) < MIN_SUPPORTING_EVENTS:
            continue
        group_events = [events[e] for e in eids]
        all_entities = set()
        for ge in group_events:
            all_entities |= set(ge["entities"])
        entity_diversity = len(all_entities)
        if entity_diversity < MIN_ENTITY_DIVERSITY:
            continue  # 같은 회사 얘기만 반복 — Change 아님(단일 주체의 활동 나열)

        # 운영자 지시 8번 핵심 가드: entity 집합이 서로 겹치지 않는(=독립적인 주체들의) Event가
        # 최소 2개는 있어야 한다. 안 그러면 "A사 얘기 + A사 얘기(다른 표현)"를 cross-entity로 착각.
        entity_sets = [frozenset(ge["entities"]) for ge in group_events]
        distinct_actor_groups = len(set(entity_sets))
        if distinct_actor_groups < MIN_ENTITY_DIVERSITY:
            continue

        group_key = (term, tuple(eids))
        if group_key in seen_group_keys:
            continue
        seen_group_keys.add(group_key)

        directions = infer_direction([ge["action_family"] for ge in group_events])
        mechanism_terms = set()
        for ge in group_events:
            mechanism_terms |= (event_terms[ge["event_id"]] - {term})

        dates = sorted(d for d in (ge.get("event_date") for ge in group_events) if d)
        candidates.append({
            "object_term": term,
            "supporting_event_ids": eids,
            "entities": sorted(all_entities),
            "entity_diversity": entity_diversity,
            "event_count": len(eids),
            "direction": directions,
            "fingerprint": change_fingerprint(all_entities, directions, term, mechanism_terms),
            "first_seen": dates[0] if dates else None,
            "last_seen": dates[-1] if dates else None,
            "event_types": sorted({ge["event_type"] for ge in group_events}),
        })
    return candidates
