# POST-INTEGRATION EVIDENCE, INTERPRETIVE & APPLIED INTELLIGENCE CONTRACT v3.0.
#
# 이 파일은 "새 Intelligence Layer"가 아니다(운영자 지시 섹션 61-62). Stage 6도, Report
# Engine도, Philosophy/Humanities Agent도 아니다. 여기 있는 것은 전부:
#   (a) 향후 Report/Knowledge Engine이 참조할 공통 어휘(vocabulary) 상수와
#   (b) 향후 그 Engine이 채워 넣을 객체의 "모양"만 정의하는 shell 함수
# 뿐이다. 이 파일의 어떤 함수도 Claim/Evidence/Interpretation을 자동 생성하지 않으며,
# 어떤 기존 pipeline.py도 이 모듈을 import하지 않는다(운영자 지시 섹션 2: 기존 Architecture
# 절대 보호). 5A-5G/Evidence Pipeline이 이미 지원하는 개념은 여기서 다시 만들지 않고
# 원래 위치를 그대로 가리킨다(아래 각 절의 주석 참조) — 이 파일은 "이미 있는 것"을
# 재구현하지 않고 "아직 이름/자리조차 없는 것"에만 이름과 자리를 준다.
#
# 핵심 원칙(운영자 지시 섹션 1): EVIDENCE IS THE FLOOR. INTERPRETATION IS NECESSARY.
# INTERPRETATION IS NOT FACT. ABSTRACTION MUST RETURN TO REALITY.

# ==========================================================================
# 8. REPORT CLAIM LADDER — Evidence로부터의 거리가 커질수록 요구되는 근거 수준도 커진다.
# 지금 이 순간 이 9단계로 뭔가를 "승격"시키는 코드는 어디에도 없다(운영자 지시 섹션 62:
# Report Generator 구현 금지) — 이것은 향후 Report Engine이 반드시 따라야 할 어휘일 뿐이다.
# ==========================================================================
CLAIM_STRENGTH_LEVELS = (
    "OBSERVED_FACT",                          # LEVEL 1
    "OBSERVED_CHANGE",                        # LEVEL 2
    "EMERGING_DIRECTION",                     # LEVEL 3
    "SUPPORTED_TREND",                        # LEVEL 4
    "STRUCTURAL_INTERPRETATION",              # LEVEL 5
    "CONCEPTUAL_HUMANISTIC_INTERPRETATION",   # LEVEL 6
    "FORWARD_IMPLICATION",                    # LEVEL 7
    "HYPOTHESIS_FUTURES",                     # LEVEL 8
    "APPLIED_OPTION",                         # LEVEL 9
)
CLAIM_STRENGTH_LEVEL_INDEX = {name: i + 1 for i, name in enumerate(CLAIM_STRENGTH_LEVELS)}

# --------------------------------------------------------------------------
# 10. CLAIM STRENGTH CEILING — Evidence Pack이 허용하는 "최대" Claim Strength.
# LLM은 이 값을 상향 조정할 수 없다(운영자 지시 섹션 10 마지막) — 즉 이 표는 코드가
# 정하고, Level 3 Gemini Candidate를 포함한 어떤 LLM 산출물도 이 표를 우회해서 더 높은
# 레벨을 자칭할 수 없다(evidence_pipeline/fact_validator.py의 LEVEL3_GEMINI_CANDIDATE
# 승격 금지 가드와 동일한 원칙 — 그 코드를 다시 만들지 않고 원칙만 여기서도 어휘로 반복).
# 값은 "그 ceiling 아래에서 허용되는 가장 높은 CLAIM_STRENGTH_LEVELS 인덱스(1-based)".
# --------------------------------------------------------------------------
CLAIM_STRENGTH_CEILINGS = {
    "OBSERVATION_CEILING": CLAIM_STRENGTH_LEVEL_INDEX["OBSERVED_CHANGE"],                # Trend/구조/개념 해석 금지
    "EMERGING_CEILING": CLAIM_STRENGTH_LEVEL_INDEX["EMERGING_DIRECTION"],                # Supported Trend 이상 금지
    "STRUCTURAL_INTERPRETATION_CEILING": CLAIM_STRENGTH_LEVEL_INDEX["STRUCTURAL_INTERPRETATION"],
    "UNKNOWN_CEILING": CLAIM_STRENGTH_LEVEL_INDEX["OBSERVED_FACT"],                      # 판정 불가 시 가장 보수적
}


def max_allowed_claim_strength_index(ceiling_name):
    """ceiling_name이 허용하는 최대 레벨(1-based index)을 반환. 모르는 ceiling은 가장
    보수적인 UNKNOWN_CEILING으로 취급한다(모르면 관대해지지 않는다)."""
    return CLAIM_STRENGTH_CEILINGS.get(ceiling_name, CLAIM_STRENGTH_CEILINGS["UNKNOWN_CEILING"])


def is_claim_strength_within_ceiling(level_name, ceiling_name):
    level_idx = CLAIM_STRENGTH_LEVEL_INDEX.get(level_name)
    if level_idx is None:
        return False
    return level_idx <= max_allowed_claim_strength_index(ceiling_name)


# ==========================================================================
# 9. EVIDENCE SUFFICIENCY DIMENSIONS — 하나의 composite score로 절대 합치지 않는다
# (운영자 지시 섹션 9 마지막). 이 튜플은 "평가 차원의 이름"만 나열하며, 이미 코드로
# 계산 가능한 차원은 옆 주석에 실제 위치를 적는다. 계산 함수를 여기서 새로 만들지 않는다
# — 이미 있는 계산은 이미 있는 파일이 한다(중복 구현 금지, 운영자 지시 섹션 2).
# ==========================================================================
EVIDENCE_SUFFICIENCY_DIMENSIONS = (
    "SOURCE_QUALITY",              # evidence_pipeline/schema.py EVIDENCE_SOURCE_HIERARCHY
    "PRIMARY_EVIDENCE_COVERAGE",   # evidence_pipeline/source_resolver.py
    "EVIDENCE_DIRECTNESS",         # evidence_pipeline/schema.py SUPPORT_TYPES
    "SOURCE_INDEPENDENCE",         # evidence_pipeline/independence.py
    "DOCUMENT_INDEPENDENCE",       # evidence_pipeline/independence.py
    "EVENT_INDEPENDENCE",          # 미계산 — event_matching/*에 event_id는 있으나 독립성 지표 없음
    "TEMPORAL_PERSISTENCE",        # 부분 — first_seen/last_seen만 있고 지속성 판정 없음
    "ENTITY_DIVERSITY",            # 부분 — entities 필드는 있으나 다양성 지표 없음
    "INSTITUTION_DIVERSITY",       # 부분 — institutions 필드는 있으나 다양성 지표 없음
    "DOMAIN_DIVERSITY",            # 부분 — domains 필드는 있으나 다양성 지표 없음
    "GEOGRAPHIC_SCOPE",            # evidence_pipeline/schema.py geographic_scope 필드
    "POPULATION_SCOPE",            # evidence_pipeline/schema.py population_scope 필드
    "MEASUREMENT_QUALITY",         # 미계산
    "TEMPORAL_VALIDITY",           # 미계산
    "SUPPORTING_EVIDENCE",         # evidence_pipeline/schema.py supports_ids
    "COUNTER_EVIDENCE",            # evidence_pipeline/counter_evidence.py, epistemic_layer/counter_evidence.py
    "CONTRADICTIONS",              # epistemic_layer/contradiction.py
    "ALTERNATIVE_EXPLANATIONS",    # epistemic_layer/alternative_explanation.py
    "EVIDENCE_GAPS",               # epistemic_layer/evidence_gap.py
)

# 기사 수(article/document count)는 그 자체로 어떤 sufficiency dimension도 아니다
# (운영자 지시 섹션 9: "기사 수는 Evidence Strength가 아니다"). 이 이름은 절대
# EVIDENCE_SUFFICIENCY_DIMENSIONS에 추가하지 않는다 — Contract Test 03/09가 이를 지킨다.
FORBIDDEN_SUFFICIENCY_PROXIES = ("ARTICLE_COUNT", "DOCUMENT_COUNT", "RAW_MENTION_COUNT")


# ==========================================================================
# 11. INTERPRETATION DISTANCE — Evidence로부터의 추론 거리. 거리가 멀수록 독립 근거
# 요구치가 올라간다(운영자 지시 섹션 11 마지막: "단일 Event로 Distance 3-5 결론 생성 금지").
# ==========================================================================
INTERPRETATION_DISTANCE_LEVELS = (
    "FACT",                                    # 0
    "DIRECT_INTERPRETATION",                   # 1
    "STRUCTURAL_INTERPRETATION",               # 2
    "CONCEPTUAL_HUMANISTIC_INTERPRETATION",    # 3
    "FORWARD_IMPLICATION",                     # 4
    "HYPOTHESIS_SCENARIO",                     # 5
)
INTERPRETATION_DISTANCE_INDEX = {name: i for i, name in enumerate(INTERPRETATION_DISTANCE_LEVELS)}

# Distance 3 이상은 단일 Event/단일 문서로 생성 금지 — 최소 2개의 독립적인(=같은 문서가
# 아닌) 근거가 필요하다. Distance가 실제로 이 값을 강제하는 자동 파이프라인은 아직 없다
# (Report Engine 미구현) — 이것은 향후 그 파이프라인이 지켜야 할 최소 요구치 표다.
MIN_INDEPENDENT_EVIDENCE_FOR_DISTANCE = {0: 1, 1: 1, 2: 1, 3: 2, 4: 2, 5: 2}


def min_independent_evidence_required(distance_level_name):
    idx = INTERPRETATION_DISTANCE_INDEX.get(distance_level_name)
    if idx is None:
        return MIN_INDEPENDENT_EVIDENCE_FOR_DISTANCE[5]  # 모르면 가장 엄격하게
    return MIN_INDEPENDENT_EVIDENCE_FOR_DISTANCE[idx]


# ==========================================================================
# 13. PHILOSOPHICAL / HUMANISTIC DIMENSIONS — 답을 미리 정하는 taxonomy가 아니라
# "질문을 발견하기 위한 Lens"다(운영자 지시 섹션 13 마지막). 이 중 AUTHORITY,
# RESPONSIBILITY, HUMAN_AGENCY(=AGENCY/AUTONOMY와 인접), FAIRNESS, AUTHENTICITY, TRUST,
# ACCESS는 이미 structural_change_layer/pattern_layer/structural_analysis_layer/
# policy_research_layer의 STRUCTURAL_DIMENSIONS·TRADEOFF_DIMENSIONS 등에 흩어져 존재한다
# (운영자 지시 섹션 61: "이미 지원하면 수정하지 않는다"). 여기서는 그 흩어진 것들과 아직
# 어디에도 없는 것(KNOWLEDGE/TRUTH/IDENTITY/MEANING/HUMAN_VALUE/FREEDOM/CREATIVITY/
# MEMORY/RELATIONSHIP/EMBODIMENT)을 하나의 완전한 참조 목록으로 모아만 둔다.
# ==========================================================================
PHILOSOPHICAL_DIMENSIONS = (
    "AGENCY", "AUTONOMY", "AUTHORITY", "RESPONSIBILITY", "KNOWLEDGE", "TRUTH",
    "AUTHENTICITY", "IDENTITY", "MEANING", "LEGITIMACY", "HUMAN_VALUE", "FREEDOM",
    "CREATIVITY", "MEMORY", "RELATIONSHIP", "EMBODIMENT",
)

# 14. PHILOSOPHICAL TRIGGER RULE — ARTICLE -> PHILOSOPHY 직결 금지. 반드시
# EVIDENCE -> OBSERVED_CHANGE -> STRUCTURAL_CONSEQUENCE -> CONCEPTUAL_TENSION ->
# PHILOSOPHICAL_QUESTION 순서를 거친다. QUESTION과 CONCLUSION은 다른 종류이며,
# 이 계약상 자동 생성이 허용되는 것은 QUESTION뿐이다(CONCLUSION은 인간 판단 영역).
PHILOSOPHICAL_OUTPUT_KINDS = ("PHILOSOPHICAL_QUESTION", "PHILOSOPHICAL_CONCLUSION")
AUTO_GENERATABLE_PHILOSOPHICAL_OUTPUT_KINDS = ("PHILOSOPHICAL_QUESTION",)
PHILOSOPHICAL_TRIGGER_CHAIN = (
    "EVIDENCE", "OBSERVED_CHANGE", "STRUCTURAL_CONSEQUENCE", "CONCEPTUAL_TENSION",
    "PHILOSOPHICAL_QUESTION",
)


# ==========================================================================
# 15-19. SOCIAL SCIENCE LENSES — 모든 Lens를 매번 쓰는 것은 금지(운영자 지시 섹션 15).
# 현상과 관련된 Lens만 선택해서 쓴다는 원칙을 지키기 위해, 이 목록은 "선택 가능한 메뉴"일
# 뿐 자동 적용 순서가 아니다.
# ==========================================================================
SOCIAL_SCIENCE_LENSES = (
    "ECONOMICS", "SOCIOLOGY", "POLITICAL_SCIENCE", "PUBLIC_POLICY", "LAW", "ANTHROPOLOGY",
    "PSYCHOLOGY", "MEDIA_STUDIES", "SCIENCE_TECHNOLOGY_STUDIES", "INSTITUTIONAL_ANALYSIS",
    "GEOPOLITICS", "ENVIRONMENTAL_STUDIES",
)

# 21. STS 원칙 — 기술결정론 금지: "AI 기술이 사회를 바꾼다"만으로 끝내지 않고
# TECHNOLOGY<->INSTITUTION<->MARKET<->LAW<->CULTURE<->HUMAN_PRACTICE 상호작용으로 본다.
STS_INTERACTION_NODES = ("TECHNOLOGY", "INSTITUTION", "MARKET", "LAW", "CULTURE", "HUMAN_PRACTICE")


# ==========================================================================
# 25. CONCEPTUAL CHANGE CANDIDATE — "저자의 의미가 변했다"는 Fact가 아니다. 자동 생성
# Engine은 이번 작업에서 만들지 않는다(운영자 지시 섹션 25 마지막) — 아래는 향후 그런
# Engine이 생기더라도 결과 객체가 반드시 CANDIDATE 상태로만 시작해야 한다는 계약(shell)뿐.
# ==========================================================================
CONCEPTUAL_CHANGE_TARGETS = (
    "AUTHOR", "EXPERT", "WORK", "CREATIVITY", "INTELLIGENCE", "AGENCY", "RESPONSIBILITY",
    "TRUST", "AUTHENTICITY", "PRIVACY", "KNOWLEDGE", "PUBLIC",
)
CONCEPTUAL_CHANGE_STATUS = ("CANDIDATE", "HUMAN_CONFIRMED", "HUMAN_REJECTED")
MIN_EVIDENCE_FOR_CONCEPTUAL_CHANGE_CANDIDATE = 2  # 섹션 29: multi-evidence 요구


def conceptual_change_candidate_is_eligible(supporting_evidence_ids):
    """섹션 29: 단일 근거로는 Conceptual Change Candidate조차 만들 수 없다(다른 Candidate류보다
    엄격) — 최소 MIN_EVIDENCE_FOR_CONCEPTUAL_CHANGE_CANDIDATE개의 근거가 필요."""
    return len(supporting_evidence_ids or []) >= MIN_EVIDENCE_FOR_CONCEPTUAL_CHANGE_CANDIDATE


def new_conceptual_change_candidate_shell(candidate_id, concept_target, statement,
                                           supporting_evidence_ids, philosophical_dimensions):
    """concept_target은 CONCEPTUAL_CHANGE_TARGETS 중 하나. status는 항상 CANDIDATE로
    시작하며, 이 shell을 실제로 만들어 파일에 쓰는 pipeline은 아직 없다(Engine 미구현)."""
    return {
        "conceptual_change_candidate_id": candidate_id,
        "concept_target": concept_target,
        "statement": statement,
        "supporting_evidence_ids": list(supporting_evidence_ids or []),
        "philosophical_dimensions": list(philosophical_dimensions or []),
        "status": "CANDIDATE",
        "override_status": "AUTO_CANDIDATE",
        "created_at": None, "updated_at": None,
    }


# ==========================================================================
# 27. REALITY RETURN MAPPING — 고차원 해석은 가능하면 현실 요소로 다시 연결되어야 한다.
# 연결할 수 없으면 CONCEPTUAL_QUESTION 또는 HYPOTHESIS로 남기고 강한 현실 결론으로
# 쓰지 않는다. 이 요소들의 상당수는 이미 policy_research_layer(target_actor, mechanism,
# stakeholder_type, constraint_type)와 structural_analysis_layer(GRAPH_NODE_TYPES)에
# 흩어져 있다 — 여기서는 "이 해석이 현실로 돌아왔는가"를 점검할 때 쓸 완전한 체크리스트만
# 모은다.
# ==========================================================================
REALITY_RETURN_ELEMENTS = (
    "ACTOR", "INCENTIVE", "RESOURCE", "INSTITUTION", "RULE", "LAW", "INFRASTRUCTURE",
    "BEHAVIOR", "CAPABILITY", "CONSTRAINT", "COST", "BENEFIT", "DISTRIBUTION",
    "ENFORCEMENT", "FEASIBILITY", "TRADE_OFF", "POLICY_OPTION", "INSTITUTIONAL_OPTION",
    "RESEARCH_NEED", "MONITORING_INDICATOR",
)
NO_REALITY_LINK_FALLBACK_STATUS = ("CONCEPTUAL_QUESTION", "HYPOTHESIS")


def reality_return_fields_present(obj):
    """obj(dict) 안에 REALITY_RETURN_ELEMENTS 중 값이 채워진(=None/[]/""가 아닌) 필드가
    최소 하나라도 있는지 점검하는 읽기 전용 checker. obj의 키 이름이 REALITY_RETURN_ELEMENTS
    소문자와 정확히 같을 때만 인식한다 — 무리하게 의미를 추측하지 않는다(정확도 우선).
    아무것도 생성하지 않고, 참/거짓만 돌려준다."""
    for key in REALITY_RETURN_ELEMENTS:
        val = obj.get(key.lower())
        if val:
            return True
    return False


# ==========================================================================
# 28. SO WHAT? / THEN WHAT? / CAN IT ACTUALLY WORK? — 세 관문의 이름만 정의한다.
# ==========================================================================
THREE_TEST_GATES = ("SO_WHAT", "THEN_WHAT", "CAN_IT_ACTUALLY_WORK")


# ==========================================================================
# 45. REPORT CLAIM LINEAGE — "왜 이 문장을 썼는가"에 답할 수 있어야 한다. Report Engine은
# 이번 작업에서 구현하지 않는다(운영자 지시 섹션 62) — 그러나 그 Engine이 나중에 반드시
# 채워야 할 lineage 객체의 "모양"은 지금 확정해 둔다. 이 shell을 실제 파이프라인에서
# 호출하는 곳은 없다(테스트에서만 모양을 검증).
# ==========================================================================
REPORT_CLAIM_LINEAGE_FIELDS = (
    "report_claim_id",
    "supporting_evidence_ids", "counter_evidence_ids", "uncertainty_ids",
    "alternative_explanation_ids", "assumption_ids", "falsifier_ids",
    "event_ids", "change_ids", "signal_ids", "pattern_ids", "structural_change_ids",
    "claim_ids", "fact_ids", "document_ids", "source_ids", "original_urls",
    "claim_strength_level", "interpretation_distance",
)


def new_report_claim_lineage_shell(report_claim_id):
    shell = {name: None for name in REPORT_CLAIM_LINEAGE_FIELDS}
    shell["report_claim_id"] = report_claim_id
    for list_field in REPORT_CLAIM_LINEAGE_FIELDS[1:17]:
        shell[list_field] = []
    shell["claim_strength_level"] = None
    shell["interpretation_distance"] = None
    shell["status"] = "NOT_GENERATED"  # Report Engine이 없으므로 실제로 채워진 적이 없다는 표식
    shell["created_at"] = None
    return shell


def lineage_reaches_source(lineage):
    """report_claim lineage가 최소한 하나의 document_id/source_id까지 내려가는지
    구조적으로만 확인한다(내용 검증 아님, 필드 존재/비어있지 않음만 확인)."""
    return bool(lineage.get("document_ids")) and bool(lineage.get("source_ids"))


def lineage_reaches_evidence(lineage):
    """report_claim lineage가 최소한 하나의 evidence(supporting_evidence_ids)까지
    연결되는지 구조적으로만 확인한다 — claim_ids/fact_ids만 있고 evidence_ids가 없는
    lineage는 '왜 이 문장을 썼는가'에 끝까지 답하지 못한 것으로 본다(섹션 45)."""
    return bool(lineage.get("supporting_evidence_ids"))


# 46. REPORT EVIDENCE PACK — Report Section이 최소 지원해야 할 필드 이름만 나열.
REPORT_EVIDENCE_PACK_FIELDS = (
    "report_period", "domain", "verified_facts", "verified_claims", "major_events", "changes",
    "signals", "patterns", "structural_changes", "supporting_evidence", "counter_evidence",
    "contradictions", "research", "policy_law", "historical_context", "structural_dimensions",
    "conceptual_dimensions", "actors", "incentives", "institutions", "resources", "constraints",
    "alternative_explanations", "uncertainties", "assumptions", "falsifiers", "evidence_gaps",
    "policy_options", "institutional_options", "stakeholder_impacts", "tradeoffs", "feasibility",
    "monitoring_indicators", "source_independence", "event_independence", "temporal_coverage",
    "geographic_scope", "population_scope", "claim_strength_ceiling",
)


# ==========================================================================
# 59. NORMAL STOP STATES — "모른다"는 것도 Intelligence다. 이 이름들은 이미 여러 layer의
# 빈 결과/override_status="AUTO_CANDIDATE" 0건 등으로 암묵적으로 표현되고 있으나, 향후
# Report Engine이 사람이 읽을 수 있는 명시적 코드로 이 상태를 보고할 때 쓸 공통 어휘다.
# ==========================================================================
NORMAL_STOP_STATES = (
    "INSUFFICIENT_EVIDENCE", "TOO_EARLY_TO_ASSESS", "CONFLICTING_EVIDENCE", "SCOPE_TOO_NARROW",
    "PRIMARY_SOURCE_MISSING", "CAUSALITY_NOT_ESTABLISHED", "CONCEPTUAL_INTERPRETATION_PREMATURE",
    "POLICY_FEASIBILITY_UNKNOWN", "NO_MATERIAL_CHANGE_DETECTED",
)


# ==========================================================================
# 11장(Actor/Incentive/Institution/Resource) 보강 — structural_analysis_layer/schema.py의
# GRAPH_NODE_TYPES(ACTOR, INSTITUTION, RESOURCE, INFRASTRUCTURE, PLATFORM, STANDARD, RIGHT,
# PERMISSION)에는 없는 INCENTIVE만 이 계약에서 보강해 참조 목록을 완전하게 한다. 기존
# GRAPH_NODE_TYPES 자체는 수정하지 않는다(운영자 지시 섹션 2 — 5D 코드 불변).
# ==========================================================================
ACTOR_INCENTIVE_INSTITUTION_RESOURCE_NODE_TYPES = (
    "ACTOR", "INCENTIVE", "INSTITUTION", "RESOURCE", "INFRASTRUCTURE", "PLATFORM",
    "STANDARD", "RIGHT", "PERMISSION",
)


# ==========================================================================
# 60. 해석 회피 금지 — 여기 열거된 질문들을 "충분한 Evidence가 있을 때" 던지지 않고
# A/B/C만 나열하는 것도 실패다. 이 목록은 향후 Report Engine의 체크리스트일 뿐,
# 지금 이 파일이 자동으로 답을 만들지 않는다.
# ==========================================================================
INTERPRETIVE_OBLIGATION_QUESTIONS = (
    "WHAT_CONNECTS_THEM", "WHAT_MECHANISM_EXPLAINS_THEM", "WHAT_STRUCTURE_IS_CHANGING",
    "WHO_GAINS_POWER", "WHO_LOSES_CONTROL", "WHAT_BECOMES_VALUABLE", "WHAT_BECOMES_SCARCE",
    "WHAT_NEW_DEPENDENCY_APPEARS", "WHAT_HUMAN_ROLE_CHANGES", "WHAT_ASSUMPTION_IS_CHALLENGED",
    "WHAT_HAPPENS_NEXT", "WHAT_CAN_REALISTICALLY_BE_DONE", "WHAT_ARE_THE_TRADEOFFS",
    "WHAT_EVIDENCE_WOULD_CHANGE_THE_CONCLUSION",
)
