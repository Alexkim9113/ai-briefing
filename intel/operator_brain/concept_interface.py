# STAGE 7 PHASE F — Conceptual Knowledge Layer 인터페이스. 섹션 27: 절대 LLM으로 수천 개
# Concept를 자동 생성하지 않는다. 이번 Phase는 스키마/인터페이스만 준비하고, 지적 기반을
# 자동 생성된 개념사전으로 오염시키지 않는다(섹션 27 명시). 현재는 curated concept corpus가
# 아예 없으므로 이 인터페이스는 항상 빈 결과 + READY_FOR_CURATED_KNOWLEDGE를 반환한다.
CONCEPT_OBJECT_FIELDS = (
    "concept_id", "name", "discipline", "definition", "scope", "key_questions",
    "related_concepts", "tensions", "empirical_triggers", "misuse_warnings",
    "historical_context", "observable_indicators", "reality_return_questions",
    "sources", "review_status",
)


def new_concept_object_shell(concept_id, name, discipline):
    shell = {field: None for field in CONCEPT_OBJECT_FIELDS}
    shell.update({
        "concept_id": concept_id, "name": name, "discipline": discipline,
        "key_questions": [], "related_concepts": [], "tensions": [],
        "empirical_triggers": [], "misuse_warnings": [], "historical_context": [],
        "observable_indicators": [], "reality_return_questions": [], "sources": [],
        "review_status": "CANDIDATE",
    })
    return shell


# 섹션 27: "현재는 schema/interface 준비, existing concept retrieval 가능, 없으면
# READY_FOR_CURATED_KNOWLEDGE". 실제 curated corpus 파일이 없으므로 빈 store.
_CURATED_CONCEPTS_BY_ID = {}


def retrieve_concept(concept_id):
    return _CURATED_CONCEPTS_BY_ID.get(concept_id)


def readiness():
    if _CURATED_CONCEPTS_BY_ID:
        return "READY"
    return "READY_FOR_CURATED_KNOWLEDGE"
