# PHASE 4C — Change Fact Pack(운영자 지시 21번). 빈 필드는 [] 허용, LLM으로 채우지 않음.
def build_change_fact_pack(change_id, change_statement, supporting_events, contradicting_events,
                            event_fact_packs_by_id, key_entities, first_seen, last_seen):
    verified_facts, reported_claims = [], []
    for eid in supporting_events:
        fp = event_fact_packs_by_id.get(eid)
        if not fp:
            continue
        verified_facts += fp.get("verified_facts", [])
        reported_claims += fp.get("reported_claims", [])
    return {
        "change_id": change_id, "change_statement": change_statement,
        "supporting_events": supporting_events, "contradicting_events": contradicting_events,
        "verified_facts": verified_facts, "reported_claims": reported_claims,
        "key_entities": key_entities, "key_numbers": [],
        "related_research": [], "related_policy": [],
        "time_range": {"first_seen": first_seen, "last_seen": last_seen},
        "uncertainties": [],
    }
