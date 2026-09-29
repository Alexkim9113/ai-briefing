# PHASE 5D — Structural Analysis Fact Pack(운영자 지시 40번). 빈 배열/null 허용, LLM 미사용.
def build_structural_analysis_fact_pack(analysis_id, structural_change_id, drivers, dependencies,
                                         controls, power_shifts, value_shifts, scarcity_shifts,
                                         bottlenecks, supporting_patterns, supporting_changes,
                                         supporting_events, domains, event_types, entities,
                                         institutions, resources, counter_evidence, uncertainties,
                                         independence_metrics, first_seen, last_seen):
    return {
        "structural_analysis_id": analysis_id, "structural_change_id": structural_change_id,
        "drivers": drivers, "dependencies": dependencies, "controls": controls,
        "power_shifts": power_shifts, "value_shifts": value_shifts, "scarcity_shifts": scarcity_shifts,
        "bottlenecks": bottlenecks,
        "supporting_patterns": supporting_patterns, "supporting_changes": supporting_changes,
        "supporting_events": supporting_events,
        "verified_facts": [], "reported_claims": [],
        "domains": domains, "event_types": event_types, "entities": entities,
        "institutions": institutions, "resources": resources,
        "counter_evidence": counter_evidence, "uncertainties": uncertainties,
        "independence_metrics": independence_metrics,
        "time_range": {"first_seen": first_seen, "last_seen": last_seen},
    }
