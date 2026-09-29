# PHASE 5F — Futures Fact Pack(운영자 지시 61번). 빈 배열/null 허용, LLM 미사용, 장문 서사 금지.
def build_futures_fact_pack(assessment):
    return {
        "futures_assessment_id": assessment["futures_assessment_id"],
        "structural_change_ids": assessment.get("target_structural_change_ids", []),
        "structural_analysis_ids": [], "epistemic_assessment_ids": [],
        "trajectory_ids": assessment.get("trajectory_ids", []),
        "outlook_ids": assessment.get("outlook_ids", []),
        "alternative_path_ids": assessment.get("alternative_path_ids", []),
        "scenario_ids": assessment.get("scenario_ids", []),
        "second_order_effect_ids": assessment.get("second_order_effect_ids", []),
        "third_order_effect_ids": assessment.get("third_order_effect_ids", []),
        "forecast_ids": assessment.get("forecast_ids", []),
        "supporting_evidence": [], "counter_evidence": assessment.get("counter_evidence_ids", []),
        "contradictions": [], "tensions": [],
        "uncertainties": assessment.get("uncertainty_ids", []),
        "assumptions": assessment.get("assumption_ids", []),
        "falsifiers": assessment.get("falsifier_ids", []),
        "evidence_gaps": [], "alternative_explanations": [],
        "epistemic_ceiling": assessment.get("epistemic_ceiling"), "speculation_level": None,
        "domains": [], "entities": [], "institutions": [], "resources": [],
        "time_range": {"first_seen": None, "last_seen": None}, "lineage": [], "unknowns": [],
    }
