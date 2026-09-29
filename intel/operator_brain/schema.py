# STAGE 7 — OPERATOR BRAIN / ASK METAXIS: PHASE A (Query Foundation) 스키마.
# 이 디렉터리는 OWNER-ONLY Private Intelligence다. Stage 1-6의 어떤 파일도 이 Stage에서
# 수정하지 않는다 - 여기서 만드는 것은 순수 조회/조합 계층이다(섹션 59).
ASK_MODES = ("RETRIEVE", "ANALYZE", "DEEP_THINK", "TEST_HYPOTHESIS")

QUERY_INTENTS = (
    "FACT_LOOKUP", "EVENT_LOOKUP", "CHANGE_ANALYSIS", "TREND_ANALYSIS",
    "STRUCTURAL_ANALYSIS", "CONNECTION_DISCOVERY", "CONTRADICTION_SEARCH",
    "QUESTION_EXPLORATION", "HYPOTHESIS_TEST", "COUNTER_EVIDENCE_SEARCH",
    "UNCERTAINTY_ANALYSIS", "TEMPORAL_COMPARISON", "VIEW_REVISION",
    "POLICY_EXPLORATION", "RESEARCH_GAP", "FUTURES_EXPLORATION",
    "GENERAL_SYNTHESIS", "UNKNOWN",
)

# 섹션 13: intent classifier는 deterministic foundation 우선. 애매하면 UNKNOWN/GENERAL_SYNTHESIS 허용.
_MODE_DEFAULT_INTENT_FALLBACK = "GENERAL_SYNTHESIS"

SCOPE_DIMENSIONS = (
    "TIME", "GEOGRAPHY", "JURISDICTION", "INDUSTRY", "ENTITY", "TOPIC",
    "CONCEPT", "POPULATION", "DOMAIN", "EPISTEMIC_SCOPE",
)

# 섹션 15: Retrieval Planner - intent -> 조회할 object type 목록. 이 매핑 자체가
# retrieval_planner.py의 근거가 된다(코드가 아니라 스펙에서 온 매핑이라는 점을 스키마에
# 명시적으로 남겨 추적 가능하게 한다).
INTENT_RETRIEVAL_TARGETS = {
    "FACT_LOOKUP": ("FACT", "EVIDENCE", "SOURCE"),
    "EVENT_LOOKUP": ("EVENT", "DOCUMENT", "SOURCE"),
    "CHANGE_ANALYSIS": ("EVENT", "CHANGE", "TIMELINE", "FACT"),
    "TREND_ANALYSIS": ("CHANGE", "SIGNAL", "PATTERN", "TIMELINE"),
    "STRUCTURAL_ANALYSIS": ("PATTERN", "STRUCTURAL_CHANGE", "STRUCTURAL_ANALYSIS"),
    "CONNECTION_DISCOVERY": ("FACT", "EVENT", "CHANGE", "RELATION"),
    "CONTRADICTION_SEARCH": ("COUNTER_EVIDENCE", "CHANGE", "EVENT"),
    "QUESTION_EXPLORATION": ("QUESTION", "KNOWLEDGE_MEMORY"),
    "HYPOTHESIS_TEST": ("FACT", "EVENT", "CHANGE", "SUPPORTING_EVIDENCE", "COUNTER_EVIDENCE", "UNCERTAINTY"),
    "COUNTER_EVIDENCE_SEARCH": ("COUNTER_EVIDENCE", "EVIDENCE"),
    "UNCERTAINTY_ANALYSIS": ("UNCERTAINTY", "EVIDENCE"),
    "TEMPORAL_COMPARISON": ("EVENT", "CHANGE", "TIMELINE"),
    "VIEW_REVISION": ("KNOWLEDGE_MEMORY", "CHANGE"),
    "POLICY_EXPLORATION": ("POLICY", "LAW", "EVENT", "EVIDENCE", "CONSTRAINT", "TRADEOFF"),
    "RESEARCH_GAP": ("RESEARCH", "EVIDENCE_GAP", "QUESTION"),
    "FUTURES_EXPLORATION": ("STRUCTURAL_CHANGE", "DRIVER", "UNCERTAINTY", "FUTURES"),
    "GENERAL_SYNTHESIS": ("FACT", "EVENT", "CHANGE", "KNOWLEDGE_MEMORY"),
    "UNKNOWN": (),
}

# 섹션 19: 단일 Truth Score 금지 - 가능한 상태 목록.
EVIDENCE_SUFFICIENCY_STATES = (
    "SUFFICIENT_FOR_FACT_LOOKUP", "SUFFICIENT_FOR_DESCRIPTIVE_ANALYSIS",
    "SUFFICIENT_FOR_LIMITED_INTERPRETATION", "SUFFICIENT_FOR_HYPOTHESIS_TEST",
    "INSUFFICIENT_EVIDENCE", "CONFLICTING_EVIDENCE", "PRIMARY_SOURCE_MISSING",
    "SCOPE_TOO_NARROW", "TOO_EARLY", "CAUSALITY_NOT_ESTABLISHED",
    "CONCEPTUAL_PREMATURE", "POLICY_FEASIBILITY_UNKNOWN", "NO_MATERIAL_CHANGE",
)

# 섹션 20: Claim Ladder(interpretive_contract의 9단계와 동일 계열 - 재정의가 아니라 재사용).
CLAIM_LADDER = (
    "OBSERVED_FACT", "OBSERVED_CHANGE", "EMERGING_DIRECTION", "SUPPORTED_TREND",
    "STRUCTURAL_INTERPRETATION", "CONCEPTUAL_HUMANISTIC_INTERPRETATION",
    "FORWARD_IMPLICATION", "HYPOTHESIS_FUTURES", "APPLIED_OPTION",
)

# 섹션 21.
INTERPRETATION_DISTANCE_LEVELS = (0, 1, 2, 3, 4, 5)

# 섹션 37: Hypothesis Test Contract 판정.
HYPOTHESIS_ASSESSMENTS = (
    "SUPPORTED", "PARTIALLY_SUPPORTED", "MIXED", "WEAKLY_SUPPORTED",
    "INSUFFICIENT", "CONTRADICTED",
)

# 섹션 39.
CONNECTION_KINDS = ("OBSERVED_CONNECTION", "SUPPORTED_CONNECTION",
                    "INTERPRETIVE_CONNECTION", "HYPOTHESIZED_CONNECTION")

# 섹션 52: Candidate Memory - Stage 6 canonical memory로 자동 승격 금지.
CANDIDATE_TYPES = ("QUESTION", "HYPOTHESIS", "INSIGHT", "POLICY_IDEA", "RESEARCH_IDEA")
CANDIDATE_STATUSES = ("CANDIDATE", "SAVED_TO_MEMORY", "DISCARDED")

# 섹션 68: Readiness vocabulary (Stage 6와 동일 계열 + CURATED_KNOWLEDGE 상태 추가).
READINESS_VALUES = ("READY", "READY_FOR_NATURAL_DATA", "READY_FOR_CURATED_KNOWLEDGE",
                    "PARTIAL", "NOT_READY")


def new_query_record(query_id, question_text, mode, now_iso):
    assert mode in ASK_MODES, f"unknown mode: {mode}"
    return {
        "query_id": query_id,
        "question_text": question_text,
        "mode": mode,
        "intent": "UNKNOWN",
        "scope": {dim: None for dim in SCOPE_DIMENSIONS},
        "created_at": now_iso,
    }


def new_context_pack_shell():
    """섹션 22: Claude에게 raw DB dump 금지 - 빈 영역은 비운다(빈 리스트/None), 채우지 않는다."""
    return {
        "question": None, "intent": None, "mode": None, "scope": {},
        "known_facts": [], "source_claims": [],
        "key_events": [], "observed_changes": [], "signals": [], "patterns": [],
        "structural_changes": [],
        "related_concepts": [], "related_entities": [],
        "supporting_evidence": [], "counter_evidence": [], "contradictions": [],
        "uncertainties": [], "alternative_explanations": [],
        "timeline": [],
        "research": [], "policy_law": [],
        "metrics": {},
        "operator_memory": [], "past_questions": [], "past_hypotheses": [],
        "past_insights": [], "view_revisions": [],
        "evidence_gaps": [],
        "claim_ceiling": None, "interpretation_ceiling": None,
        "source_references": [], "object_references": [],
    }


def new_structured_response_shell(response_id, query_id, now_iso, mode, intent, scope):
    """섹션 51: machine-readable metadata. human-readable response와 분리."""
    return {
        "response_id": response_id, "query_id": query_id, "timestamp": now_iso,
        "mode": mode, "intent": intent, "scope": scope,
        "factual_claims": [], "interpretations": [], "hypotheses": [],
        "counter_evidence": [], "uncertainties": [], "new_questions": [],
        "monitoring_indicators": [],
        "used_fact_ids": [], "used_event_ids": [], "used_change_ids": [],
        "used_signal_ids": [], "used_pattern_ids": [], "used_structural_change_ids": [],
        "used_memory_note_ids": [], "used_evidence_ids": [], "used_source_ids": [],
        "used_concept_ids": [],
        "claim_ceiling": None, "interpretation_ceiling": None, "evidence_sufficiency": None,
        "model": None, "prompt_version": None, "context_hash": None, "cache_status": "MISS",
    }
