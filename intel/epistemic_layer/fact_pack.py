# PHASE 5E — Epistemic Fact Pack(운영자 지시 44번). 빈 배열/null 허용, LLM 미사용.
def build_epistemic_fact_pack(target_object_type, target_object_id, assessment, independence_metrics):
    return {
        "target_object_type": target_object_type, "target_object_id": target_object_id,
        "supporting_evidence": [], "counter_evidence": assessment.get("counter_evidence_count", 0),
        "contradictions": assessment.get("contradiction_ids", []),
        "tensions": assessment.get("tension_ids", []),
        "paradox_candidates": assessment.get("paradox_candidate_ids", []),
        "uncertainties": assessment.get("uncertainty_ids", []),
        "assumptions": assessment.get("assumption_ids", []),
        "falsifiers": assessment.get("falsifier_ids", []),
        "evidence_gaps": assessment.get("evidence_gap_ids", []),
        "alternative_explanations": assessment.get("alternative_explanation_ids", []),
        "confidence_before": assessment.get("confidence_before"),
        "confidence_after": assessment.get("confidence_after"),
        "epistemic_ceiling": assessment.get("epistemic_ceiling"),
        "verified_facts": [], "reported_claims": [],
        "domains": [], "event_types": [], "entities": [], "institutions": [], "resources": [],
        "time_range": {"first_seen": None, "last_seen": None},
        "scope": None, "lineage": [], "unknowns": [],
        "independence_metrics": independence_metrics,
    }
