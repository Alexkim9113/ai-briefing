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
        "interpretation_distance": 0 if note_type in EVIDENCE_BACKED_TYPES else None,
        "human_review_status": "AUTO_CANDIDATE",
        "generated_by": "CODE_DETERMINISTIC",
        "version": 1,
        "history": [],
        "supersedes": None,
        "superseded_by": None,
    }


def new_relation_shell(relation_id, subject_id, relation_type, object_id, now_iso):
    assert relation_type in RELATION_TYPES, f"unknown relation_type: {relation_type}"
    return {
        "relation_id": relation_id,
        "subject_id": subject_id,
        "relation_type": relation_type,
        "object_id": object_id,
        "evidence_ids": [],
        "confidence": None,
        "status": "ACTIVE",
        "created_at": now_iso,
        "updated_at": now_iso,
    }
