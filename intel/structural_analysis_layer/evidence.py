# PHASE 5D — Evidence Lineage 집계(운영자 지시 16, 23, 27번). 개별 객체가 아니라
# Structural Analysis 통합 객체 수준에서 supporting/counter evidence id를 모은다.
def collect_evidence_ids(*collections_of_objects):
    supporting, counter = set(), set()
    for collection in collections_of_objects:
        for obj in collection.values():
            supporting.update(obj.get("supporting_pattern_ids", []))
            supporting.update(obj.get("supporting_change_ids", []))
            supporting.update(obj.get("supporting_event_ids", []))
            counter.update(obj.get("counter_evidence_ids", []))
    return sorted(supporting), sorted(counter)


def uncertainty_flags_for(collections_by_name):
    """운영자 지시 26번: 본격 Uncertainty Intelligence는 5E. 이번 Phase는 구조화된 flag만."""
    flags = []
    for name, collection in collections_by_name.items():
        for obj_id, obj in collection.items():
            if obj.get("confidence") == "LOW":
                flags.append({"object_type": name, "object_id": obj_id, "flag": "LOW_CONFIDENCE_EVIDENCE"})
            if obj.get("counter_evidence_ids"):
                flags.append({"object_type": name, "object_id": obj_id, "flag": "COUNTER_EVIDENCE_PRESENT"})
    return flags
