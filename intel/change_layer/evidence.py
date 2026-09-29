# PHASE 4C — Supporting/Contradicting Evidence + Event Quality 반영(운영자 지시 3, 11, 12번).
# 모든 CONFIRMED Event를 같은 신뢰도로 안 쓴다. Event 하나가 틀려도 Change 전체가
# 무너지지 않도록, evidence 목록에 항상 event_quality 메타데이터를 함께 남긴다.
from fingerprint import infer_direction


def event_quality_record(event_id, event, override_status="AUTO_CONFIRMED"):
    """Change Evidence 한 줄. Human Confirmed Event는 더 높은 quality를 갖는다(운영자 지시 3번)."""
    quality = "HIGH" if override_status == "HUMAN_CONFIRMED" else (
        "MEDIUM" if event.get("source_diversity", 1) >= 2 else "LOW")
    return {
        "event_id": event_id, "event_quality": quality,
        "merge_confidence": event.get("merge_confidence"),
        "source_count": event.get("source_count"), "source_diversity": event.get("source_diversity"),
        "primary_document_id": event.get("primary_document_id"),
    }


def split_supporting_contradicting(candidate, events):
    """같은 object-term 그룹 안에서 다수 방향과 반대되는 Event는 contradicting으로 분리
    (운영자 지시 11번). 단일 방향만 있으면 contradicting은 빈 배열."""
    majority = candidate["direction"]
    supporting, contradicting = [], []
    for eid in candidate["supporting_event_ids"]:
        ev = events[eid]
        d = infer_direction([ev["action_family"]])
        if majority != "OTHER" and d != "OTHER" and d != majority and d != "SHIFTING":
            contradicting.append(eid)
        else:
            supporting.append(eid)
    return supporting, contradicting
