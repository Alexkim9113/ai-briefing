# STAGE 1-5 INTEGRATION CHECKPOINT — EVIDENCE EXTRACTION & INTERPRETATION PIPELINE.
# CLAIM/EVIDENCE RECORD 스키마(운영자 지시 섹션 7, 9). CODE ONLY.
#
# 핵심 원칙(운영자 지시 4번): EVIDENCE EXTRACTION("원문이 실제로 뭐라고 썼는가")과
# EVIDENCE INTERPRETATION("이게 어떤 구조적 의미일 수 있는가")은 절대 하나로 합치지 않는다.
# 이 파일은 두 계층의 스키마를 모두 담되, claim_extractor.py/interpretation.py가 서로
# 다른 모듈로 분리되어 있어야 한다는 원칙은 코드 구조로도 지킨다(파일 자체는 분리).

# --- CLAIM (섹션 7) ---
CLAIM_TYPES = ("MEASURED", "RESEARCH_FINDING", "GOVERNMENT_REPORTED", "COMPANY_REPORTED",
               "COURT_FINDING", "LEGISLATIVE_TEXT", "REGULATORY_TEXT", "ESTIMATED", "FORECAST",
               "ALLEGATION", "MEDIA_REPORTED", "EXPERT_OPINION", "OTHER")

# claim_status(섹션 7): SOURCE_VERIFIED는 매우 보수적으로만 부여(섹션 8) — 이 Pipeline은
# 원문 전체 대조 없이는 절대 SOURCE_VERIFIED를 주지 않는다(20개 금지 중 1,2번).
CLAIM_STATUS = ("SOURCE_VERIFIED", "SOURCE_LOCATED", "PRIMARY_UNREAD", "SECONDARY_ONLY",
                "SUMMARY_DERIVED", "INSUFFICIENT_SOURCE", "DISPUTED", "RETRACTED", "NOT_VERIFIED")

# --- EVIDENCE SOURCE HIERARCHY (섹션 5) ---
EVIDENCE_SOURCE_HIERARCHY = ("PRIMARY_OFFICIAL", "PRIMARY_RESEARCH", "PRIMARY_COMPANY",
                             "PRIMARY_COURT", "PRIMARY_LEGISLATIVE", "PRIMARY_REGULATORY",
                             "PRIMARY_DATASET", "SECONDARY_WIRE", "SECONDARY_MAJOR_MEDIA",
                             "SECONDARY_SPECIALIST", "SECONDARY_OTHER", "METAXIS_INTERNAL")

# --- EVIDENCE TYPE (섹션 10) — FACTUAL 계열 + 5D Interpretation 계열 + 확장 대기 계열 ---
EVIDENCE_TYPES = ("FACTUAL", "MEASUREMENT", "RESEARCH_RESULT", "LEGAL", "POLICY", "REGULATORY",
                  "COURT", "COMPANY_CLAIM", "EXPERT_CLAIM",
                  "DRIVER", "DEPENDENCY", "CONTROL", "VALUE_SHIFT", "SCARCITY_SHIFT", "BOTTLENECK",
                  "ACCESS", "AUTHORITY", "RESPONSIBILITY", "RIGHTS", "LABOR", "INFRASTRUCTURE",
                  "RESOURCE_PRESSURE", "ENVIRONMENTAL_PRESSURE", "CULTURAL_NORM", "HUMAN_AGENCY")

# 5D 어댑터가 실제로 소비하는 타입만(운영자 지시 섹션 29) — structural_analysis_layer 스키마와
# 정확히 일치해야 한다(구조 분석 Layer 코드는 절대 수정하지 않으므로, 이쪽에서 맞춘다).
FIVE_D_TARGET_TYPES = ("DRIVER", "DEPENDENCY", "CONTROL", "VALUE_SHIFT", "SCARCITY_SHIFT", "BOTTLENECK")

SUPPORT_TYPES = ("DIRECT_SUPPORT", "INDIRECT_SUPPORT", "CONTEXT_ONLY", "ASSOCIATED",
                 "COUNTER_EVIDENCE", "CONTRADICTORY", "UNKNOWN")

EPISTEMIC_STATUS = ("SOURCE_VERIFIED", "SOURCE_LOCATED", "SUMMARY_DERIVED", "INSUFFICIENT_SOURCE",
                    "DISPUTED", "NOT_VERIFIED")
INTERPRETATION_STATUS = ("NOT_INTERPRETED", "CANDIDATE", "HUMAN_CONFIRMED", "HUMAN_REJECTED")

EXTRACTION_METHODS = ("LEVEL1_STRUCTURED", "LEVEL2_RULE", "LEVEL3_GEMINI_CANDIDATE")
INTERPRETATION_METHODS = ("RULE_MAPPING", "GEMINI_CANDIDATE")

HUMAN_REVIEW_STATUS = ("NOT_REQUIRED", "PENDING", "HUMAN_CONFIRMED", "HUMAN_REJECTED", "HUMAN_EDITED")
REVIEW_PRIORITY = ("HIGH", "MEDIUM", "LOW")
REVIEW_SCORES = ("CORRECT", "PARTIAL", "WRONG", "OVERCLAIMED", "UNDERCLAIMED",
                 "SCOPE_ERROR", "SOURCE_ERROR", "RELATION_ERROR")

CONFIDENCE_LEVELS = ("LOW", "MEDIUM", "HIGH")  # 가짜 확률 금지

# --- Domain Normalization (섹션 19) — 실제 세계 영역. event_type과 절대 혼용 금지. ---
REAL_DOMAINS = ("TECHNOLOGY_INFRASTRUCTURE", "SCIENCE_RESEARCH", "POLICY_LAW_GOVERNANCE",
                "ECONOMY_INDUSTRY_LABOR", "HUMAN_SOCIETY_EDUCATION", "CULTURE_ARTS_MEDIA",
                "SECURITY_GEOPOLITICS", "PLANET")
PLANET_SUBDOMAINS = ("ENERGY", "WATER", "CLIMATE", "ENVIRONMENT", "ECOLOGY", "BIODIVERSITY", "ANIMALS")

# Scope Guard 판정 결과(5E와 동일 어휘 — Evidence Pipeline은 5E보다 아래 계층이므로 자체 구현하되
# 같은 결과 어휘를 써서 나중에 5E가 이 Layer의 Counter Evidence를 그대로 읽을 수 있게 한다).
SCOPE_VERDICT = ("DIRECT_CONTRADICTION", "NO_DIRECT_CONTRADICTION", "CONTEXT_DEPENDENT", "TENSION")


def new_claim_shell(claim_id, document_id, source_id):
    return {
        "claim_id": claim_id, "document_id": document_id, "source_id": source_id,
        "evidence_id": None,  # 기존 evidence_service.py의 evidence_id(ev_<doc>)와 연결(있으면)
        "claim_text": None, "normalized_claim": None,
        "subject": None, "predicate": None, "object": None, "value": None, "unit": None,
        "claim_type": None, "speaker": None, "claiming_organization": None,
        "reported_by": None, "original_source_id": None,
        "temporal_scope": None, "geographic_scope": None, "population_scope": None, "domain_scope": [],
        "claim_status": "NOT_VERIFIED",
        "evidence_locator": None, "evidence_text_hash": None,
        "extraction_method": None, "extraction_version": EXTRACTION_VERSION,
        "confidence": "LOW",
        "created_at": None, "updated_at": None,
    }


def new_evidence_record_shell(evidence_record_id, source_id, document_id, claim_id):
    return {
        "evidence_record_id": evidence_record_id, "source_id": source_id,
        "document_id": document_id, "claim_id": claim_id, "fact_id": None,
        "evidence_type": None, "subject": None, "relation": None, "object": None,
        "value": None, "unit": None, "direction": None,
        "temporal_scope": None, "geographic_scope": None, "population_scope": None, "domain_scope": [],
        "claim_type": None, "source_type": None, "support_type": "UNKNOWN",
        "supports_ids": [], "contradicts_ids": [],
        "evidence_strength": "LOW", "epistemic_status": "NOT_VERIFIED",
        "interpretation_status": "NOT_INTERPRETED",
        "extraction_method": None, "interpretation_method": None,
        "human_review_status": "NOT_REQUIRED",
        # 5D 어댑터/상위 Layer 연결용(구조 분석 Layer가 기대하는 공통 필드는 adapters.py에서 매핑).
        "structural_change_id_hint": None,
        "domains": [], "entities": [], "institutions": [], "resources": [],
        "first_seen": None, "last_seen": None,
        "history": [],
        "created_at": None, "updated_at": None,
    }


EXTRACTION_VERSION = "evpipe_v1"
