# PHASE 5A — Signal Fact Pack(운영자 지시 17번). 빈 배열 허용, LLM으로 채우지 않음.
def build_signal_fact_pack(signal_id, signal_type, maturity, supporting_changes,
                            supporting_events, contradicting_events,
                            change_fact_packs_by_id, key_entities, domains, topics,
                            first_seen, last_seen):
    verified_facts, reported_claims = [], []
    for cid in supporting_changes:
        fp = change_fact_packs_by_id.get(cid)
        if not fp:
            continue
        verified_facts += fp.get("verified_facts", [])
        reported_claims += fp.get("reported_claims", [])
    return {
        "signal_id": signal_id, "signal_type": signal_type, "maturity": maturity,
        "supporting_changes": supporting_changes,
        "supporting_events": supporting_events, "contradicting_events": contradicting_events,
        "verified_facts": verified_facts, "reported_claims": reported_claims,
        "key_entities": key_entities, "key_numbers": [],
        "domains": domains, "topics": topics,
        "time_range": {"first_seen": first_seen, "last_seen": last_seen},
        "uncertainties": [],
    }
