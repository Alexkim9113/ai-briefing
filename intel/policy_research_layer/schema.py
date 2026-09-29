# PHASE 5G — Policy/Research Intelligence Schema(운영자 지시 4~62번). CODE ONLY, LLM 미사용.
#
# 핵심 원칙(운영자 지시 1번): POLICY QUESTION != RECOMMENDATION, POLICY OPTION != RECOMMENDATION/
# PREFERRED OPTION, TRADE-OFF != DISADVANTAGE ONLY, STAKEHOLDER IMPACT != VALUE JUDGMENT,
# RESEARCH QUESTION != FINDING, RESEARCH GAP != EVIDENCE OF ABSENCE, EVIDENCE NEED != COUNTER
# EVIDENCE, MONITORING INDICATOR != FORECAST, FEASIBILITY != DESIRABILITY, EFFECTIVENESS !=
# LEGITIMACY, EFFICIENCY != FAIRNESS, CURRENT LAW != NORMATIVE IDEAL, SCENARIO != POLICY
# JUSTIFICATION. 11개 객체는 서로 독립적이며 generic recommendation 객체로 뭉뚱그리지 않는다.

CONFIDENCE_LEVELS = ("LOW", "MEDIUM", "HIGH")
OVERRIDE_STATUS = ("AUTO_CANDIDATE", "HUMAN_CONFIRMED", "HUMAN_REJECTED")
EPISTEMIC_CEILING_LEVELS = ("LOW", "MEDIUM", "HIGH", "UNKNOWN")
SEVERITY_LEVELS = ("LOW", "MEDIUM", "HIGH", "UNKNOWN")
PRIORITY_LEVELS = ("LOW", "MEDIUM", "HIGH")

POLICY_QUESTION_TYPES = ("ACCOUNTABILITY", "LIABILITY", "ACCESS", "COMPETITION", "INTEROPERABILITY",
                          "SAFETY", "RIGHTS", "PRIVACY", "DATA_GOVERNANCE", "TRANSPARENCY", "LABOR",
                          "CULTURE", "CREATIVE_RIGHTS", "EDUCATION", "RESEARCH_GOVERNANCE",
                          "INFRASTRUCTURE", "ENERGY", "ENVIRONMENT", "PUBLIC_SERVICE", "SECURITY",
                          "INTERNATIONAL_COORDINATION", "INSTITUTIONAL_DESIGN", "OTHER")
DECISION_LEVELS = ("LOCAL", "NATIONAL", "REGIONAL", "INTERNATIONAL", "INSTITUTIONAL", "INDUSTRY",
                    "PLATFORM", "MULTI_LEVEL", "UNKNOWN")

OPTION_TYPES = ("NO_ACTION", "INFORMATION_DISCLOSURE", "VOLUNTARY_STANDARD", "TECHNICAL_STANDARD",
                "INTEROPERABILITY_REQUIREMENT", "AUDIT_REQUIREMENT", "LICENSING", "CERTIFICATION",
                "LIABILITY_RULE", "RIGHTS_PROTECTION", "ACCESS_RULE", "COMPETITION_MEASURE",
                "PROCUREMENT_RULE", "PUBLIC_INFRASTRUCTURE", "RESEARCH_SUPPORT", "SANDBOX",
                "REPORTING_REQUIREMENT", "RESTRICTION", "PROHIBITION", "INTERNATIONAL_COORDINATION",
                "INSTITUTIONAL_REFORM", "OTHER")

TRADEOFF_DIMENSIONS = ("INNOVATION", "SAFETY", "ACCESS", "COMPETITION", "PRIVACY", "SECURITY",
                        "RIGHTS", "ACCOUNTABILITY", "TRANSPARENCY", "EFFICIENCY", "COST", "EQUITY",
                        "FAIRNESS", "AUTONOMY", "HUMAN_AGENCY", "CULTURAL_DIVERSITY",
                        "CREATIVE_FREEDOM", "LABOR_PROTECTION", "ENVIRONMENTAL_IMPACT", "ENERGY_USE",
                        "INTERNATIONAL_COMPETITIVENESS", "ADMINISTRATIVE_CAPACITY", "ENFORCEABILITY", "OTHER")
TRADEOFF_STATUS = ("CONFIRMED_TRADEOFF", "POTENTIAL_TRADEOFF")

STAKEHOLDER_TYPES = ("INDIVIDUAL", "CONSUMER", "WORKER", "CREATOR", "RESEARCHER", "STUDENT", "CHILD",
                      "VULNERABLE_GROUP", "COMPANY", "STARTUP", "PLATFORM", "AI_PROVIDER",
                      "PUBLIC_INSTITUTION", "REGULATOR", "COURT", "EDUCATIONAL_INSTITUTION",
                      "CULTURAL_INSTITUTION", "CIVIL_SOCIETY", "LOCAL_COMMUNITY", "ENVIRONMENT",
                      "FUTURE_GENERATIONS", "OTHER")
IMPACT_DIRECTIONS = ("BENEFIT", "COST", "RISK", "OPPORTUNITY", "MIXED", "UNCLEAR")

CONSTRAINT_TYPES = ("LEGAL", "CONSTITUTIONAL", "JURISDICTIONAL", "ADMINISTRATIVE", "TECHNICAL",
                     "ECONOMIC", "BUDGETARY", "INSTITUTIONAL", "POLITICAL", "INTERNATIONAL",
                     "INFRASTRUCTURAL", "ENFORCEMENT", "DATA", "EVIDENCE", "TIMING", "OTHER")

POLICY_UNCERTAINTY_TYPES = ("IMPLEMENTATION_UNCERTAINTY", "BEHAVIORAL_RESPONSE_UNCERTAINTY",
                             "ENFORCEMENT_UNCERTAINTY", "TECHNOLOGY_RESPONSE_UNCERTAINTY",
                             "MARKET_RESPONSE_UNCERTAINTY", "LEGAL_INTERPRETATION_UNCERTAINTY",
                             "DISTRIBUTIONAL_UNCERTAINTY", "INTERNATIONAL_RESPONSE_UNCERTAINTY",
                             "MEASUREMENT_UNCERTAINTY", "OTHER")

RESEARCH_QUESTION_TYPES = ("DESCRIPTIVE", "CAUSAL", "COMPARATIVE", "MECHANISM", "MEASUREMENT",
                            "EVALUATION", "FORECAST_VALIDATION", "POLICY_EVALUATION", "DISTRIBUTIONAL",
                            "BEHAVIORAL", "INSTITUTIONAL", "HISTORICAL", "CROSS_NATIONAL",
                            "ENVIRONMENTAL", "CULTURAL", "ETHICAL_EMPIRICAL", "OTHER")

RESEARCH_GAP_TYPES = ("NO_PRIMARY_EVIDENCE", "INSUFFICIENT_PRIMARY_EVIDENCE", "NO_LONGITUDINAL_DATA",
                       "NO_COMPARATIVE_DATA", "NO_CAUSAL_EVIDENCE", "NO_MECHANISM_EVIDENCE",
                       "NO_DISTRIBUTIONAL_DATA", "NO_CROSS_NATIONAL_EVIDENCE",
                       "NO_REAL_WORLD_VALIDATION", "NO_STANDARD_MEASUREMENT", "OUTDATED_EVIDENCE",
                       "CONFLICTING_EVIDENCE", "POPULATION_GAP", "GEOGRAPHIC_GAP", "DOMAIN_GAP", "OTHER")
RESEARCH_GAP_STATUS = ("OPEN", "PARTIALLY_FILLED", "FILLED", "NO_LONGER_RELEVANT")

EVIDENCE_NEED_STATUS = ("NEEDED", "COLLECTING", "PARTIALLY_AVAILABLE", "AVAILABLE", "NO_LONGER_NEEDED")

REAL_DOMAINS = ("TECHNOLOGY_INFRASTRUCTURE", "SCIENCE_RESEARCH", "POLICY_LAW_GOVERNANCE",
                "ECONOMY_INDUSTRY_LABOR", "HUMAN_SOCIETY_EDUCATION", "CULTURE_ARTS_MEDIA",
                "SECURITY_GEOPOLITICS", "PLANET")
JURISDICTIONS = ("GLOBAL", "KR", "EU", "US", "CN", "JP", "OTHER", "MULTI", "UNKNOWN")
POLICY_OBJECT_STATUS_VOCAB = ("CURRENT_LAW", "PROPOSED_POLICY", "POLICY_OPTION",
                               "REGULATORY_DISCUSSION", "COURT_INTERPRETATION")
NOT_ASSESSED = "NOT_ASSESSED"
EVALUATION_VALUES = ("POSITIVE", "NEGATIVE", "MIXED", "UNCLEAR", NOT_ASSESSED)


def _base(obj_id, id_field, extra_status_default="AUTO_CANDIDATE"):
    return {
        id_field: obj_id, "supporting_evidence_ids": [], "counter_evidence_ids": [],
        "uncertainty_ids": [], "confidence": "LOW",
        "status": extra_status_default, "override_status": "AUTO_CANDIDATE",
        "history": [], "created_at": None, "updated_at": None,
    }


def new_policy_question_shell(pid, question, question_type, target_structural_change_ids,
                               futures_assessment_ids, affected_domains, decision_level):
    shell = _base(pid, "policy_question_id")
    del shell["confidence"]  # Policy Question 자체는 참/거짓이 아니라 질문이므로 confidence 없음
    shell.update({
        "question": question, "question_type": question_type,
        "target_structural_change_ids": target_structural_change_ids,
        "futures_assessment_ids": futures_assessment_ids, "affected_domains": affected_domains,
        "decision_level": decision_level, "decision_horizon": None, "trigger_conditions": [],
        "assumption_ids": [], "falsifier_ids": [], "evidence_gap_ids": [], "stakeholder_ids": [],
        "epistemic_ceiling": "UNKNOWN", "jurisdiction": "UNKNOWN",
    })
    return shell


def new_policy_option_shell(oid, policy_question_id, option_name, option_type, mechanism, target_actor,
                             implementation_level):
    shell = _base(oid, "policy_option_id")
    shell.update({
        "policy_question_id": policy_question_id, "option_name": option_name, "option_type": option_type,
        "mechanism": mechanism, "target_actor": target_actor, "implementation_level": implementation_level,
        "required_conditions": [], "expected_first_order_effects": [],
        "related_second_order_effect_ids": [], "related_third_order_effect_ids": [],
        "affected_stakeholder_ids": [], "tradeoff_ids": [], "constraint_ids": [],
        "assumption_ids": [], "falsifier_ids": [], "monitoring_indicator_ids": [],
        "epistemic_ceiling": "UNKNOWN", "jurisdiction": "UNKNOWN",
        "valid_from": None, "valid_to": None, "last_verified_at": None,
        "policy_object_status": "POLICY_OPTION",
        "evaluation": {k: NOT_ASSESSED for k in (
            "effectiveness", "feasibility", "enforceability", "cost", "rights_impact",
            "equity_impact", "innovation_impact", "competition_impact", "human_agency_impact",
            "environmental_impact", "administrative_burden")},
        "normative_assumption_ids": [],
    })
    return shell


def new_policy_tradeoff_shell(tid, policy_option_id, dimension_a, direction_a, dimension_b, direction_b,
                               mechanism, status):
    shell = _base(tid, "tradeoff_id")
    shell.update({
        "policy_option_id": policy_option_id, "dimension_a": dimension_a, "direction_a": direction_a,
        "dimension_b": dimension_b, "direction_b": direction_b, "mechanism": mechanism,
        "affected_stakeholder_ids": [], "status": status,
    })
    return shell


def new_stakeholder_impact_shell(sid, policy_option_id, stakeholder_type, stakeholder_id_or_label,
                                  impact_dimension, direction, mechanism, time_horizon):
    shell = _base(sid, "stakeholder_impact_id")
    shell.update({
        "policy_option_id": policy_option_id, "stakeholder_type": stakeholder_type,
        "stakeholder_id_or_label": stakeholder_id_or_label, "impact_dimension": impact_dimension,
        "direction": direction, "mechanism": mechanism, "time_horizon": time_horizon,
    })
    return shell


def new_policy_constraint_shell(cid, policy_option_id, constraint_type, constraint, severity):
    shell = _base(cid, "constraint_id")
    del shell["confidence"]
    shell.update({
        "policy_option_id": policy_option_id, "constraint_type": constraint_type,
        "constraint": constraint, "severity": severity,
    })
    return shell


def new_policy_uncertainty_shell(uid, policy_question_id, policy_option_id, uncertainty_type, description_code):
    shell = _base(uid, "policy_uncertainty_id")
    del shell["confidence"]
    shell["status"] = "OPEN"
    shell.update({
        "policy_question_id": policy_question_id, "policy_option_id": policy_option_id,
        "uncertainty_type": uncertainty_type, "description_code": description_code,
    })
    return shell


def new_research_question_shell(rid, question, question_type, target_object_type, target_object_id,
                                 population, geography, time_scope, priority):
    shell = _base(rid, "research_question_id")
    del shell["confidence"]
    shell.update({
        "question": question, "question_type": question_type,
        "target_object_type": target_object_type, "target_object_id": target_object_id,
        "related_policy_question_ids": [], "why_it_matters_code": None,
        "required_evidence_types": [], "population": population, "geography": geography,
        "time_scope": time_scope, "variables_or_constructs": [], "counter_hypothesis_ids": [],
        "evidence_gap_ids": [], "priority": priority,
    })
    return shell


def new_research_gap_shell(gid, target_object_type, target_object_id, gap_type, gap_description_code,
                            scope, priority):
    shell = _base(gid, "research_gap_id")
    del shell["confidence"]
    shell["status"] = "OPEN"
    shell.update({
        "target_object_type": target_object_type, "target_object_id": target_object_id,
        "gap_type": gap_type, "gap_description_code": gap_description_code,
        "known_evidence_ids": [], "missing_evidence_types": [], "affected_questions": [],
        "scope": scope, "priority": priority, "confidence": "LOW",
    })
    return shell


def new_evidence_need_shell(eid, target_object_type, target_object_id, evidence_type, description_code,
                             required_scope, priority, collection_method_type):
    shell = _base(eid, "evidence_need_id")
    del shell["confidence"]
    shell["status"] = "NEEDED"
    shell.update({
        "target_object_type": target_object_type, "target_object_id": target_object_id,
        "evidence_type": evidence_type, "description_code": description_code,
        "required_scope": required_scope, "priority": priority,
        "collection_method_type": collection_method_type,
        "related_research_question_ids": [], "related_policy_question_ids": [],
        "related_monitoring_indicator_ids": [],
    })
    return shell


def new_monitoring_indicator_shell(mid, indicator_name, indicator_type, target_object_type, target_object_id,
                                    measurement_definition, unit, direction_of_interest, data_source_type,
                                    collection_frequency, geography, population):
    shell = _base(mid, "monitoring_indicator_id")
    del shell["confidence"]
    shell.update({
        "indicator_name": indicator_name, "indicator_type": indicator_type,
        "target_object_type": target_object_type, "target_object_id": target_object_id,
        "measurement_definition": measurement_definition, "unit": unit,
        "direction_of_interest": direction_of_interest, "data_source_type": data_source_type,
        "collection_frequency": collection_frequency, "geography": geography, "population": population,
        "baseline_value": None, "latest_value": None, "baseline_date": None, "latest_date": None,
        "thresholds": [], "status": "MONITORING_CANDIDATE",
    })
    return shell


def new_policy_research_assessment_shell(paid, futures_assessment_ids, structural_change_ids):
    return {
        "policy_research_assessment_id": paid, "futures_assessment_ids": futures_assessment_ids,
        "structural_change_ids": structural_change_ids,
        "policy_question_ids": [], "policy_option_ids": [], "tradeoff_ids": [],
        "stakeholder_impact_ids": [], "constraint_ids": [], "policy_uncertainty_ids": [],
        "research_question_ids": [], "research_gap_ids": [], "evidence_need_ids": [],
        "monitoring_indicator_ids": [],
        "counter_evidence_ids": [], "uncertainty_ids": [], "assumption_ids": [], "falsifier_ids": [],
        "epistemic_ceiling": "UNKNOWN", "domains": [], "jurisdictions": [],
        "assessment_status": "AUTO_CANDIDATE", "history": [], "created_at": None, "updated_at": None,
    }
