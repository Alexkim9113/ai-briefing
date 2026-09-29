# PHASE 5F — Futures Intelligence Schema(운영자 지시 4~40번). CODE ONLY, LLM 미사용.
#
# 핵심 원칙(운영자 지시 1번): SCENARIO != PREDICTION, OUTLOOK != FACT, TRAJECTORY != DESTINY,
# POSSIBLE != PROBABLE, PLAUSIBLE != CERTAIN, 2ND/3RD-ORDER EFFECT != OBSERVED/FORECASTED FACT,
# ASSUMPTION != EVIDENCE, FORECAST != KNOWLEDGE, CURRENT DIRECTION != INEVITABLE FUTURE.
# 10개 객체는 서로 독립적이며 하나의 generic prediction으로 뭉뚱그리지 않는다(운영자 지시 4번).

CONFIDENCE_LEVELS = ("LOW", "MEDIUM", "HIGH")  # 숫자 probability 금지(운영자 지시 21번)
OVERRIDE_STATUS = ("AUTO_CANDIDATE", "HUMAN_CONFIRMED", "HUMAN_REJECTED")
SPECULATION_LEVELS = ("LOW", "MEDIUM", "HIGH")
EPISTEMIC_CEILING_LEVELS = ("LOW", "MEDIUM", "HIGH", "UNKNOWN")

TRAJECTORY_DIRECTIONS = ("INCREASING", "DECREASING", "STABLE", "ACCELERATING", "DECELERATING",
                          "EXPANDING", "CONTRACTING", "DIFFUSING", "CONCENTRATING",
                          "FRAGMENTING", "REVERSING", "UNCLEAR")
TRAJECTORY_MATURITY = ("WEAK_SIGNAL", "EMERGING", "STRENGTHENING", "ESTABLISHED",
                        "WEAKENING", "REVERSING", "BROKEN", "UNKNOWN")
TIME_HORIZONS = ("0_1_YEAR", "1_3_YEARS", "3_5_YEARS", "5_PLUS_YEARS", "UNKNOWN")

PATH_TYPES = ("BASE_PATH", "ACCELERATION_PATH", "CONSTRAINT_PATH", "REVERSAL_PATH",
              "FRAGMENTATION_PATH", "DIFFUSION_PATH", "CONCENTRATION_PATH",
              "SUBSTITUTION_PATH", "REGULATORY_PATH", "TECHNOLOGICAL_BREAKTHROUGH_PATH", "OTHER")

SCENARIO_TYPES = ("BASE", "ACCELERATION", "CONSTRAINT", "REVERSAL", "FRAGMENTATION",
                   "CONCENTRATION", "DIFFUSION", "TRANSFORMATION", "OTHER")
SCENARIO_STATES = ("ACTIVE", "STRENGTHENING", "WEAKENING", "RETIRED")

EFFECT_STATUS = "HYPOTHESIS_CANDIDATE"  # 운영자 지시 27번: Human Confirmed 전까지 Fact 승격 금지

FORECAST_STATUS = ("ACTIVE", "PARTIALLY_SUPPORTED", "SUPPORTED", "WEAKENED", "CONTRADICTED",
                    "EXPIRED", "REVISED", "RETIRED")

REAL_DOMAINS = ("TECHNOLOGY_INFRASTRUCTURE", "SCIENCE_RESEARCH", "POLICY_LAW_GOVERNANCE",
                "ECONOMY_INDUSTRY_LABOR", "HUMAN_SOCIETY_EDUCATION", "CULTURE_ARTS_MEDIA",
                "SECURITY_GEOPOLITICS", "PLANET")


def _base(obj_id, id_field):
    return {
        id_field: obj_id, "supporting_evidence_ids": [], "counter_evidence_ids": [],
        "uncertainty_ids": [], "assumption_ids": [], "falsifier_ids": [],
        "epistemic_ceiling": "UNKNOWN", "confidence": "LOW",
        "status": "AUTO_CANDIDATE", "override_status": "AUTO_CANDIDATE",
        "history": [], "created_at": None, "updated_at": None,
    }


def new_trajectory_shell(tid, target_object_type, target_object_id, trajectory_type,
                          direction, maturity, time_horizon):
    shell = _base(tid, "trajectory_id")
    shell.update({
        "target_object_type": target_object_type, "target_object_id": target_object_id,
        "trajectory_type": trajectory_type, "direction": direction, "maturity": maturity,
        "first_observed": None, "last_observed": None, "time_horizon": time_horizon,
        "supporting_change_ids": [], "supporting_signal_ids": [], "supporting_pattern_ids": [],
        "supporting_structural_change_ids": [], "alternative_explanation_ids": [],
        "speculation_level": "LOW",
    })
    return shell


def new_outlook_shell(oid, trajectory_ids, structural_change_ids, outlook_type, condition, direction, time_horizon):
    shell = _base(oid, "outlook_id")
    shell.update({
        "trajectory_ids": trajectory_ids, "structural_change_ids": structural_change_ids,
        "outlook_type": outlook_type, "condition": condition, "direction": direction,
        "time_horizon": time_horizon, "speculation_level": "LOW",
    })
    return shell


def new_alternative_path_shell(pid, trajectory_ids, path_name, path_type, trigger_conditions,
                                required_assumptions, time_horizon):
    shell = _base(pid, "alternative_path_id")
    shell.update({
        "trajectory_ids": trajectory_ids, "path_name": path_name, "path_type": path_type,
        "trigger_conditions": trigger_conditions, "required_assumptions": required_assumptions,
        "time_horizon": time_horizon, "speculation_level": "MEDIUM",
        "early_indicators": [], "path_dependency_ids": [],
    })
    return shell


def new_scenario_shell(sid, scenario_name, scenario_type, trajectory_ids, alternative_path_ids,
                        structural_change_ids, trigger_conditions, time_horizon):
    shell = _base(sid, "scenario_id")
    shell.update({
        "scenario_name": scenario_name, "scenario_type": scenario_type,
        "trajectory_ids": trajectory_ids, "alternative_path_ids": alternative_path_ids,
        "structural_change_ids": structural_change_ids, "trigger_conditions": trigger_conditions,
        "time_horizon": time_horizon, "scenario_state": "ACTIVE",
        "speculation_level": "MEDIUM", "assumption_count": 0, "path_dependency_ids": [],
    })
    return shell


def new_second_order_effect_shell(eid, source_object_type, source_object_id, effect_type,
                                   affected_domain, mechanism, required_conditions):
    shell = _base(eid, "effect_id")
    shell["status"] = EFFECT_STATUS
    shell.update({
        "source_object_type": source_object_type, "source_object_id": source_object_id,
        "effect_order": 2, "effect_type": effect_type, "affected_domain": affected_domain,
        "mechanism": mechanism, "required_conditions": required_conditions,
        "analogy_ids": [], "speculation_level": "MEDIUM",
    })
    return shell


def new_third_order_effect_shell(eid, source_second_order_effect_id, effect_type,
                                  affected_domains, mechanism, required_conditions):
    shell = _base(eid, "effect_id")
    shell["status"] = EFFECT_STATUS
    shell.update({
        "source_second_order_effect_id": source_second_order_effect_id, "effect_order": 3,
        "effect_type": effect_type, "affected_domains": affected_domains, "mechanism": mechanism,
        "required_conditions": required_conditions, "analogy_ids": [], "speculation_level": "HIGH",
    })
    return shell


def new_forecast_shell(fid, forecast_statement, target, baseline_date, time_horizon,
                        expected_direction, conditions, observable_indicators):
    shell = _base(fid, "forecast_id")
    shell["status"] = "ACTIVE"
    del shell["history"]  # Forecast 자체는 Revision/Observation이 별도 로그를 갖는다
    shell.update({
        "forecast_statement": forecast_statement, "target": target, "baseline_date": baseline_date,
        "time_horizon": time_horizon, "expected_direction": expected_direction,
        "conditions": conditions, "observable_indicators": observable_indicators,
        "speculation_level": "MEDIUM",
    })
    return shell


def new_forecast_observation_shell(foid, forecast_id, observation_date, observed_indicators,
                                    assessment, confidence_change, notes_code):
    return {
        "forecast_observation_id": foid, "forecast_id": forecast_id,
        "observation_date": observation_date, "observed_indicators": observed_indicators,
        "supporting_evidence_ids": [], "contradicting_evidence_ids": [],
        "assessment": assessment, "confidence_change": confidence_change,
        "notes_code": notes_code, "created_at": None,
    }


def new_forecast_revision_shell(frid, forecast_id, previous_statement, new_statement,
                                 previous_confidence, new_confidence, revision_reason):
    return {
        "forecast_revision_id": frid, "forecast_id": forecast_id,
        "previous_statement": previous_statement, "new_statement": new_statement,
        "previous_confidence": previous_confidence, "new_confidence": new_confidence,
        "revision_reason": revision_reason, "trigger_evidence_ids": [], "counter_evidence_ids": [],
        "timestamp": None, "human_validated": False,
    }


def new_futures_assessment_shell(faid, target_structural_change_ids):
    return {
        "futures_assessment_id": faid, "target_structural_change_ids": target_structural_change_ids,
        "trajectory_ids": [], "outlook_ids": [], "alternative_path_ids": [], "scenario_ids": [],
        "second_order_effect_ids": [], "third_order_effect_ids": [], "forecast_ids": [],
        "counter_evidence_ids": [], "uncertainty_ids": [], "assumption_ids": [], "falsifier_ids": [],
        "epistemic_ceiling": "UNKNOWN", "assessment_status": "AUTO_CANDIDATE",
        "history": [], "created_at": None, "updated_at": None,
    }
