# N-3 -- Report Engine data contract. A Report is a VIEW over the existing Evidence Graph
# (Source/Document -> Statistic/Research/Event -> Evidence -> Claim -> Hypothesis ->
# Intelligence Object), never a new truth store. Nothing here invents evidence -- every value is
# either copied from an existing object or an explicit UNKNOWN/INSUFFICIENT_EVIDENCE/NOT_APPLICABLE.
SECTION_TYPES = (
    "COVER", "EXECUTIVE_INTELLIGENCE", "KEY_QUESTION", "CURRENT_STATE", "WHAT_CHANGED",
    "KEY_CLAIMS", "EVIDENCE", "STATISTICAL_CONTEXT", "RESEARCH_EVIDENCE", "POLICY_CONTEXT",
    "HISTORICAL_CONTEXT", "COUNTEREVIDENCE", "ALTERNATIVE_EXPLANATIONS", "GEOGRAPHIC_CONTEXT",
    "TEMPORAL_CONTEXT", "HYPOTHESES", "UNCERTAINTIES", "WHAT_WE_KNOW", "WHAT_WE_DO_NOT_KNOW",
    "EVIDENCE_GAPS", "METAXIS_POINT", "IMPLICATIONS", "EVIDENCE_MAP", "SOURCE_PROVENANCE",
    "METHODOLOGY_LIMITATIONS",
)

SECTION_STATUSES = ("AVAILABLE", "PARTIAL", "INSUFFICIENT_EVIDENCE", "NOT_APPLICABLE")

CONTENT_BLOCK_TYPES = (
    "FACT", "EVIDENCE_SUMMARY", "INTERPRETATION", "HYPOTHESIS", "COUNTEREVIDENCE",
    "UNCERTAINTY", "GAP", "METAXIS_POINT",
)

# Section 5 -- claim-aware sentence templates. Every CLAIM_STATUSES value from claim_model.py
# (OPEN/SUPPORTED/PARTIALLY_SUPPORTED/CONTESTED/WEAKENED/INSUFFICIENT_EVIDENCE/REJECTED) maps to
# exactly one template; OPEN (not yet evaluated) and REJECTED/WEAKENED fall back to the most
# conservative phrasing rather than a stronger one.
CLAIM_STATUS_TEMPLATES = {
    "SUPPORTED": "현재 확보된 증거는 {scope}을(를) 뒷받침한다.",
    "PARTIALLY_SUPPORTED": "일부 증거는 {scope}와(과) 일치하지만 충분하지 않다.",
    "CONTESTED": "증거는 서로 엇갈린다.",
    "WEAKENED": "기존에 제기된 {scope}은(는) 후속 증거로 약화되었다.",
    "REJECTED": "{scope}은(는) 현재 증거로 기각되었다.",
    "INSUFFICIENT_EVIDENCE": "현재 증거만으로 판단하기 어렵다.",
    "OPEN": "현재 확인되지 않았다.",
    "UNKNOWN": "현재 확인되지 않았다.",
}

ALTERNATIVE_EXPLANATION_STATUSES = (
    "UNSUPPORTED_ALTERNATIVE", "EVIDENCE_CONNECTED", "SUPPORTED", "WEAKENED", "CONTESTED",
)

UNCERTAINTY_CAUSES = (
    "ATTRIBUTION_UNCERTAINTY", "TEMPORAL_UNCERTAINTY", "SOURCE_UNCERTAINTY",
    "GEOGRAPHIC_UNCERTAINTY", "MEASUREMENT_UNCERTAINTY",
)

REPORT_READINESS_VALUES = ("READY", "CONDITIONALLY_READY", "INSUFFICIENT_EVIDENCE", "BLOCKED")

REPORT_DIFF_TYPES = (
    "NEW_EVIDENCE", "REMOVED_EVIDENCE_REFERENCE", "CLAIM_STATUS_CHANGED",
    "HYPOTHESIS_STATUS_CHANGED", "UNCERTAINTY_CHANGED", "GAP_CLOSED", "GAP_ADDED",
    "METAXIS_POINT_CHANGED",
)

REPORT_VIEWS = ("PUBLIC_REPORT", "OPERATOR_REPORT")

# Section 2 -- minimum Intelligence Object fields a Report is built from. Missing fields are
# treated as empty list / UNKNOWN -- never fabricated.
REQUIRED_INTELLIGENCE_OBJECT_FIELDS = (
    "intelligence_id", "topic", "question", "key_claims", "supporting_evidence", "statistics",
    "research_context", "policy_context", "historical_context", "counterevidence",
    "alternative_explanations", "geographic_context", "temporal_chain", "uncertainties",
    "known_gaps", "provenance", "revision_history",
)
