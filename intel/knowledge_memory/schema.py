# STAGE 6 — KNOWLEDGE MEMORY v1.0 (Te 2026-09-29). Atomic Note / Relation / Concept
# 어휘. 이 파일은 정의만 담는다 — 판정 로직은 atomizer.py/relation_service.py에 있다.
# 절대 원칙(섹션 9): Evidence-backed(FACT/CLAIM/EVENT/CHANGE)와 Interpretive(QUESTION/
# HYPOTHESIS/INSIGHT/POLICY_IDEA/RESEARCH_IDEA)를 같은 것으로 취급하지 않는다.

NOTE_TYPES = (
    "FACT", "CLAIM", "CONCEPT", "EVENT", "CHANGE",  # Evidence-backed 계열
    "RELATION",
    "QUESTION", "HYPOTHESIS", "INSIGHT", "POLICY_IDEA", "RESEARCH_IDEA",  # Interpretive 계열
)
EVIDENCE_BACKED_TYPES = frozenset({"FACT", "CLAIM", "EVENT", "CHANGE"})
INTERPRETIVE_TYPES = frozenset({"QUESTION", "HYPOTHESIS", "INSIGHT", "POLICY_IDEA", "RESEARCH_IDEA"})
assert not (EVIDENCE_BACKED_TYPES & INTERPRETIVE_TYPES)

# 섹션 23: 삭제보다 상태 변경.
NOTE_STATUSES = ("ACTIVE", "REVISED", "WEAKENING", "CONTRADICTED", "REJECTED", "ARCHIVED", "SUPERSEDED")
HYPOTHESIS_STATUSES = ("CANDIDATE", "SUPPORTED", "WEAKENING", "CONTRADICTED", "REVISED", "REJECTED")
HUMAN_REVIEW_STATUSES = ("AUTO_CANDIDATE", "HUMAN_CONFIRMED", "HUMAN_REJECTED", "HUMAN_REVISED")
GENERATED_BY_VALUES = ("CODE_DETERMINISTIC", "LLM_CANDIDATE", "HUMAN")

# 섹션 14: 관계 타입은 통제된 vocabulary만 쓴다. RELATED_TO는 fallback일 뿐 주력이 아니다
# (섹션 34: 나쁜 그래프 = 수천 개의 RELATED_TO).
RELATION_TYPES = (
    "CAUSES", "INCREASES", "DECREASES", "ENABLES", "REQUIRES", "DEPENDS_ON", "PRESSURES",
    "REGULATES", "CHALLENGES", "CONTRADICTS", "SUPPORTS", "TRANSFORMS", "REPLACES",
    "CREATES", "LEADS_TO", "MAY_ENABLE", "RELATED_TO",
)
# 섹션 15: 약한 연관성으로 CAUSES를 자동 생성하지 않는다 — 이 어댑터/atomizer가 코드로
# 스스로 만들 수 있는 관계 타입은 이 서브셋뿐이다(전부 구조적으로 명시된 관계에서만 나온다).
_CODE_DERIVABLE_RELATION_TYPES = frozenset({"RELATED_TO", "SUPPORTS", "LEADS_TO"})

# PRODUCTIONIZATION v1.0 섹션 8-9: Lineage/Provenance 관계와 Semantic/Structural 관계를
# 구분한다. Lineage는 upstream에서 deterministic하게(예: fact.document_id가 event의
# related_document_ids 안에 있다) 그대로 가져올 수 있다 — 새 추론이 아니라 이미 존재하는
# 소속 관계를 손실 없이 옮기는 것뿐이다. Semantic은 upstream이 이미 명시적으로 갖고 있을
# 때만(예: change.supporting_event_ids/contradicting_event_ids) 가져오고, Stage 6이
# 스스로 CAUSES 등을 새로 판단하지 않는다.
RELATION_CLASSES = ("LINEAGE", "EVIDENCE", "SEMANTIC", "REVISION")
LINEAGE_RELATION_TYPES = frozenset({"DERIVED_FROM", "SUPPORTED_BY", "REPORTED_BY",
                                     "PART_OF_EVENT", "OBSERVED_IN", "BASED_ON", "SUPERSEDES"})
SEMANTIC_RELATION_TYPES = frozenset({"CAUSES", "ENABLES", "REQUIRES", "DEPENDS_ON", "PRESSURES",
                                      "REGULATES", "TRANSFORMS", "CONTRADICTS", "RELATED_TO"})
# 위 두 집합을 기존 RELATION_TYPES에 병합(중복은 자연히 합집합으로 처리).
RELATION_TYPES = tuple(sorted(set(RELATION_TYPES) | LINEAGE_RELATION_TYPES | SEMANTIC_RELATION_TYPES))

# 섹션 34: Readiness를 READY/PARTIAL/NOT_READY 세 값만으로는 "구조는 됐는데 자연 발생
# Production 사례가 아직 없다"를 표현할 수 없다 — READY_FOR_NATURAL_DATA를 추가한다.
READINESS_VALUES = ("READY", "READY_FOR_NATURAL_DATA", "PARTIAL", "NOT_READY")

# 섹션 47: Interpretation Distance(기존 interpretive_contract.schema와 값 재사용, 재정의 아님).
INTERPRETATION_DISTANCE_LEVELS = (0, 1, 2, 3, 4, 5)  # 0=Fact ... 5=Hypothesis/Scenario

# 섹션 26-28: Concept과 Entity/Topic을 구별한다. 이번 Foundation은 극소수의 canonical
# concept만 등록한다(섹션 26: 너무 많이 자동 생성하지 않는다) — 실제 corpus에서 반복
# 관측되는 것만, 그리고 그 매핑 자체는 concept_registry.py가 명시적으로 관리한다.
CANONICAL_CONCEPTS = (
    "AI_AGENT", "COMPUTE", "ENERGY", "GRID_CAPACITY", "DELEGATED_AUTHORITY",
    "HUMAN_AGENCY", "COPYRIGHT", "REGULATION", "AI_SAFETY",
)


def new_atomic_note_shell(note_id, note_type, title, statement, now_iso):
    assert note_type in NOTE_TYPES, f"unknown note_type: {note_type}"
    return {
        "note_id": note_id,
        "note_type": note_type,
        "title": title,
        "statement": statement,
        "status": "ACTIVE",
        "confidence": None,
        "created_at": now_iso,
        "updated_at": now_iso,
        "source_object_type": None,
        "source_object_ids": [],
        "document_ids": [],
        "fact_ids": [],
        "event_ids": [],
        "change_ids": [],
        "signal_ids": [],
        "pattern_ids": [],
        "structural_change_ids": [],
        "source_urls": [],
        "entities": [],
        "topics": [],
        "domains": [],
        "concepts": [],
        "relations": [],
        "supporting_evidence_ids": [],
        "counter_evidence_ids": [],
        "uncertainties": [],
        # PRODUCTIONIZATION v1.0 섹션 13-14: upstream에 실제로 있을 때만 채운다 — 없으면
        # null로 두고 추측하지 않는다(섹션 14: "event_date가 없다고 published date를
        # 무조건 쓰지 않는다"). 각 필드의 의미가 다르므로 서로 대체하지 않는다.
        "first_seen": None, "last_seen": None,
        "valid_from": None, "valid_to": None,
        "observed_at": None, "event_date": None, "evidence_date": None,
        "source_published_at": None,
        "time_window_start": None, "time_window_end": None,
        # 섹션 17-19: scope는 upstream에 없으면 UNKNOWN/None으로 두고 GLOBAL 등으로 확대하지
        # 않는다.
        "geographic_scope": None, "jurisdiction": None,
        "population_scope": None, "industry_scope": None, "institution_scope": None,
        "domain_scope": None, "temporal_scope": None, "measurement_scope": None,
        "interpretation_distance": 0 if note_type in EVIDENCE_BACKED_TYPES else None,
        "human_review_status": "AUTO_CANDIDATE",
        "generated_by": "CODE_DETERMINISTIC",
        "version": 1,
        "history": [],
        "supersedes": None,
        "superseded_by": None,
    }


def _infer_relation_class(relation_type):
    if relation_type in LINEAGE_RELATION_TYPES:
        return "LINEAGE"
    if relation_type in SEMANTIC_RELATION_TYPES:
        return "SEMANTIC"
    return "SEMANTIC"


def new_relation_shell(relation_id, subject_id, relation_type, object_id, now_iso,
                        relation_class=None, source_stage=None, source_relation_id=None):
    assert relation_type in RELATION_TYPES, f"unknown relation_type: {relation_type}"
    relation_class = relation_class or _infer_relation_class(relation_type)
    assert relation_class in RELATION_CLASSES
    return {
        "relation_id": relation_id,
        "subject_id": subject_id,
        "relation_type": relation_type,
        "object_id": object_id,
        "relation_class": relation_class,
        "source_stage": source_stage,        # 이 관계가 유래한 upstream layer(예: "event_production")
        "source_relation_id": source_relation_id,  # upstream 자신의 관계/필드 식별자(있다면)
        "evidence_ids": [],
        "confidence": None,
        "status": "ACTIVE",
        "created_at": now_iso,
        "updated_at": now_iso,
    }
