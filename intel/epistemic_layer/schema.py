# PHASE 5E — Epistemic Checking Layer Schema(운영자 지시 4~35번). CODE ONLY, LLM 미사용.
#
# 핵심 원칙(운영자 지시 2번): MORE EVIDENCE != MORE CERTAINTY, COUNTER EVIDENCE != REFUTATION,
# CONTRADICTION != TENSION != PARADOX, UNKNOWN != FALSE/0, MISSING EVIDENCE != COUNTER EVIDENCE,
# CORRELATION != CAUSATION, CONFIDENCE != UNCERTAINTY, SOURCE COUNT != SOURCE INDEPENDENCE.
# 11개 객체는 서로 독립적이며 하나의 generic uncertainty로 뭉뚱그리지 않는다(운영자 지시 4번).

CONFIDENCE_LEVELS = ("LOW", "MEDIUM", "HIGH")  # 가짜 확률 금지
OVERRIDE_STATUS = ("AUTO_CANDIDATE", "HUMAN_CONFIRMED", "HUMAN_REJECTED")

COUNTER_EVIDENCE_RELATIONS = ("CHALLENGES", "WEAKENS", "LIMITS", "QUALIFIES",
                               "OFFERS_ALTERNATIVE_EXPLANATION", "DIRECTLY_CONTRADICTS", "UNKNOWN")

CONTRADICTION_SEVERITY = ("LOW", "MEDIUM", "HIGH")
CONTRADICTION_CONFLICT_TYPES = ("DIRECT_CONTRADICTION", "NO_DIRECT_CONTRADICTION",
                                 "TEMPORAL_REVERSAL_CANDIDATE", "CONTEXT_DEPENDENT")

PARADOX_TYPES = ("ACCESS_CONTROL_PARADOX", "CAPABILITY_DEPENDENCY_PARADOX",
                  "ABUNDANCE_SCARCITY_PARADOX", "AUTOMATION_RESPONSIBILITY_PARADOX",
                  "DECENTRALIZATION_CONCENTRATION_PARADOX", "OTHER")
# 운영자 지시 16번: Rule은 candidate 생성용, 최종 의미판단 아님. (dim_a, dim_b) 순서 무관 매칭.
PARADOX_RULE_MATRIX = {
    frozenset({"ACCESS", "CONTROL"}): "ACCESS_CONTROL_PARADOX",
    frozenset({"CAPABILITY", "DEPENDENCY"}): "CAPABILITY_DEPENDENCY_PARADOX",
    frozenset({"ABUNDANCE", "SCARCITY"}): "ABUNDANCE_SCARCITY_PARADOX",
    frozenset({"AUTOMATION", "HUMAN_RESPONSIBILITY"}): "AUTOMATION_RESPONSIBILITY_PARADOX",
    frozenset({"DECENTRALIZED_USE", "INFRASTRUCTURE_CONCENTRATION"}): "DECENTRALIZATION_CONCENTRATION_PARADOX",
}

UNCERTAINTY_TYPES = ("EVIDENCE_INSUFFICIENT", "SOURCE_INDEPENDENCE_UNKNOWN", "DOMAIN_MAPPING_INCOMPLETE",
                      "TEMPORAL_COVERAGE_LIMITED", "GEOGRAPHIC_COVERAGE_LIMITED", "POPULATION_SCOPE_UNKNOWN",
                      "MEASUREMENT_UNCERTAIN", "CAUSALITY_UNCERTAIN", "MECHANISM_UNCERTAIN",
                      "ENTITY_RESOLUTION_UNCERTAIN", "EVENT_MERGE_UNCERTAIN", "PATTERN_OVERLAP_HIGH",
                      "STRUCTURAL_INTERPRETATION_UNCERTAIN", "COUNTER_EVIDENCE_PRESENT",
                      "ALTERNATIVE_EXPLANATION_PRESENT", "DATA_STALE", "MISSING_PRIMARY_EVIDENCE", "OTHER")
UNCERTAINTY_STATUS = ("OPEN", "PARTIALLY_RESOLVED", "RESOLVED", "REOPENED")
EVIDENCE_GAP_STATUS = ("OPEN", "PARTIALLY_FILLED", "FILLED", "NO_LONGER_NEEDED")
FALSIFIER_STATUS = ("UNTESTED", "PARTIALLY_OBSERVED", "OBSERVED", "NOT_OBSERVED", "INVALIDATED")
PRIORITY_LEVELS = ("LOW", "MEDIUM", "HIGH")

REVISION_REASONS = ("NEW_SUPPORTING_EVIDENCE", "NEW_COUNTER_EVIDENCE", "DIRECT_CONTRADICTION",
                     "SCOPE_CORRECTION", "ENTITY_CORRECTION", "EVENT_MERGE_CORRECTION",
                     "NEW_DOMAIN_EVIDENCE", "NEW_TEMPORAL_EVIDENCE", "ALTERNATIVE_EXPLANATION",
                     "FALSIFIER_OBSERVED", "HUMAN_REVIEW", "OTHER")

EPISTEMIC_CEILING_LEVELS = ("LOW", "MEDIUM", "HIGH", "UNKNOWN")


def _base(obj_id, id_field, target_object_type, target_object_id):
    return {
        id_field: obj_id, "target_object_type": target_object_type, "target_object_id": target_object_id,
        "evidence_ids": [], "confidence": "LOW",
        "status": "OPEN" if id_field in ("uncertainty_id", "evidence_gap_id") else "AUTO_CANDIDATE",
        "override_status": "AUTO_CANDIDATE",
        "first_seen": None, "last_seen": None, "history": [],
        "created_at": None, "updated_at": None,
    }


def new_counter_evidence_shell(ce_id, target_object_type, target_object_id, evidence_type, relationship, scope):
    shell = _base(ce_id, "counter_evidence_id", target_object_type, target_object_id)
    shell["status"] = "AUTO_CANDIDATE"
    shell.update({"evidence_type": evidence_type, "relationship": relationship, "scope": scope})
    return shell


def new_contradiction_shell(cid, object_a_type, object_a_id, object_b_type, object_b_id, dimension,
                             scope_flags, conflict_type, severity):
    shell = {
        "contradiction_id": cid, "object_a_type": object_a_type, "object_a_id": object_a_id,
        "object_b_type": object_b_type, "object_b_id": object_b_id, "dimension": dimension,
        **scope_flags,
        "conflict_type": conflict_type, "evidence_ids": [], "severity": severity, "confidence": "LOW",
        "status": "AUTO_CANDIDATE", "override_status": "AUTO_CANDIDATE",
        "history": [], "created_at": None, "updated_at": None,
    }
    return shell


def new_tension_shell(tid, object_a_type, object_a_id, object_b_type, object_b_id, tension_type,
                       dimensions, relationship, scope):
    return {
        "tension_id": tid, "object_a_type": object_a_type, "object_a_id": object_a_id,
        "object_b_type": object_b_type, "object_b_id": object_b_id, "tension_type": tension_type,
        "dimensions": dimensions, "relationship": relationship,
        "supporting_evidence_ids": [], "counter_evidence_ids": [], "scope": scope,
        "confidence": "LOW", "status": "AUTO_CANDIDATE", "override_status": "AUTO_CANDIDATE",
        "history": [], "created_at": None, "updated_at": None,
    }


def new_paradox_candidate_shell(pid, object_a_type, object_a_id, object_b_type, object_b_id,
                                 paradox_type, dimensions, scope):
    return {
        "paradox_candidate_id": pid, "object_a_type": object_a_type, "object_a_id": object_a_id,
        "object_b_type": object_b_type, "object_b_id": object_b_id, "paradox_type": paradox_type,
        "dimensions": dimensions, "scope": scope,
        "supporting_evidence_ids": [], "confidence": "LOW",
        "status": "AUTO_CANDIDATE", "override_status": "AUTO_CANDIDATE",
        "history": [], "created_at": None, "updated_at": None,
    }


def new_uncertainty_shell(uid, target_object_type, target_object_id, uncertainty_type, description_code, scope):
    shell = _base(uid, "uncertainty_id", target_object_type, target_object_id)
    shell.update({"uncertainty_type": uncertainty_type, "description_code": description_code, "scope": scope,
                  "severity": "LOW", "resolvable": "unknown", "required_evidence_types": [],
                  "related_counter_evidence_ids": [], "related_contradiction_ids": [], "related_evidence_gap_ids": [],
                  "status": "OPEN"})
    del shell["confidence"]
    return shell


def new_assumption_shell(aid, target_object_type, target_object_id, assumption_type, statement,
                          required_for_interpretation):
    shell = _base(aid, "assumption_id", target_object_type, target_object_id)
    shell.update({"assumption_type": assumption_type, "assumption_statement": statement,
                  "required_for_interpretation": required_for_interpretation, "evidence_status": "UNVERIFIED",
                  "supporting_evidence_ids": [], "challenging_evidence_ids": []})
    return shell


def new_falsifier_shell(fid, target_object_type, target_object_id, condition_type, condition,
                         observable_indicator, required_scope):
    shell = _base(fid, "falsifier_id", target_object_type, target_object_id)
    shell["status"] = "UNTESTED"
    shell.update({"condition_type": condition_type, "condition": condition,
                  "observable_indicator": observable_indicator, "required_scope": required_scope})
    del shell["confidence"]
    return shell


def new_evidence_gap_shell(gid, target_object_type, target_object_id, gap_type, missing_evidence_type,
                            why_needed_code, priority):
    shell = _base(gid, "evidence_gap_id", target_object_type, target_object_id)
    shell.update({"gap_type": gap_type, "missing_evidence_type": missing_evidence_type,
                  "why_needed_code": why_needed_code, "priority": priority, "resolvable": "unknown",
                  "related_uncertainty_ids": []})
    del shell["confidence"]
    return shell


def new_alternative_explanation_shell(eid, target_object_type, target_object_id, explanation_code_or_statement):
    shell = _base(eid, "alternative_explanation_id", target_object_type, target_object_id)
    shell.update({"explanation_code_or_statement": explanation_code_or_statement,
                  "supporting_evidence_ids": [], "challenging_evidence_ids": []})
    return shell


def new_view_revision_shell(vid, target_object_type, target_object_id, previous_state, new_state,
                             previous_confidence, new_confidence, revision_reason_type):
    return {
        "view_revision_id": vid, "target_object_type": target_object_type, "target_object_id": target_object_id,
        "previous_state": previous_state, "new_state": new_state,
        "previous_confidence": previous_confidence, "new_confidence": new_confidence,
        "revision_reason_type": revision_reason_type,
        "trigger_evidence_ids": [], "counter_evidence_ids": [], "falsifier_ids": [],
        "timestamp": None, "human_validated": False,
    }


def new_epistemic_assessment_shell(eaid, target_object_type, target_object_id):
    return {
        "epistemic_assessment_id": eaid, "target_object_type": target_object_type, "target_object_id": target_object_id,
        "supporting_evidence_count": 0, "counter_evidence_count": 0,
        "contradiction_ids": [], "tension_ids": [], "paradox_candidate_ids": [],
        "uncertainty_ids": [], "assumption_ids": [], "falsifier_ids": [], "evidence_gap_ids": [],
        "alternative_explanation_ids": [],
        "confidence_before": "LOW", "confidence_after": "LOW",
        "epistemic_ceiling": "UNKNOWN", "assessment_status": "AUTO_CANDIDATE",
        "history": [], "created_at": None, "updated_at": None,
    }
