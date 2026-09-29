# PHASE 5B — Pattern Fact Pack(운영자 지시 18번). 빈 배열 허용, LLM으로 채우지 않음.
def build_pattern_fact_pack(pattern_id, pattern_statement, supporting_changes, supporting_signals,
                             contradicting_changes, contradicting_signals,
                             change_fact_packs_by_id, key_entities, domains, topics,
                             analytic_dimensions, first_seen, last_seen):
    verified_facts, reported_claims = [], []
    for cid in supporting_changes:
        fp = change_fact_packs_by_id.get(cid)
        if not fp:
            continue
        verified_facts += fp.get("verified_facts", [])
        reported_claims += fp.get("reported_claims", [])
    return {
        "pattern_id": pattern_id, "pattern_statement": pattern_statement,
        "supporting_changes": supporting_changes, "supporting_signals": supporting_signals,
        "contradicting_changes": contradicting_changes, "contradicting_signals": contradicting_signals,
        "verified_facts": verified_facts, "reported_claims": reported_claims,
        "key_entities": key_entities, "domains": domains, "topics": topics,
        "time_range": {"first_seen": first_seen, "last_seen": last_seen},
        "analytic_dimensions": analytic_dimensions,
        "uncertainties": [],
    }
