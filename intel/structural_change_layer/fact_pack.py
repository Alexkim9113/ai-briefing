# PHASE 5C — Structural Fact Pack(운영자 지시 24번). 빈 배열/None 허용, LLM으로 채우지 않음.
def build_structural_fact_pack(sc_id, statement, from_state, to_state, dimensions,
                                event_types, domains, supporting_patterns, supporting_signals,
                                supporting_changes, contradicting_patterns, contradicting_signals,
                                contradicting_changes, pattern_fact_packs_by_id, key_entities,
                                independence_metrics, first_seen, last_seen):
    verified_facts, reported_claims = [], []
    for pid in supporting_patterns:
        fp = pattern_fact_packs_by_id.get(pid)
        if not fp:
            continue
        verified_facts += fp.get("verified_facts", [])
        reported_claims += fp.get("reported_claims", [])
    return {
        "structural_change_id": sc_id, "statement": statement,
        "from_state": from_state, "to_state": to_state,
        "dimensions": dimensions,
        "event_types": event_types, "domains": domains,
        "supporting_patterns": supporting_patterns, "supporting_signals": supporting_signals,
        "supporting_changes": supporting_changes,
        "contradicting_patterns": contradicting_patterns, "contradicting_signals": contradicting_signals,
        "contradicting_changes": contradicting_changes,
        "verified_facts": verified_facts, "reported_claims": reported_claims,
        "key_entities": key_entities, "institutions": [], "resources": [], "topics": event_types,
        "time_range": {"first_seen": first_seen, "last_seen": last_seen},
        "independence_metrics": independence_metrics,
        "uncertainties": [],
    }
