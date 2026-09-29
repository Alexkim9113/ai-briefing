# STAGE 7 PHASE B — Retrieval Planner. 섹션 15: intent -> object type 매핑은
# schema.INTENT_RETRIEVAL_TARGETS(스펙 섹션 15 표 그대로)를 따른다. 이 모듈은 그 매핑을
# 실제 조회 가능한 retriever 함수 이름으로 번역만 한다 - 새 매핑을 만들지 않는다.
from schema import INTENT_RETRIEVAL_TARGETS

# 현재 이 sandbox에서 실제로 조회 가능한 대상은 knowledge_memory(FACT/EVENT/CHANGE Note)와
# 그 provenance(DOCUMENT)뿐이다(Stage 5의 SIGNAL/PATTERN/STRUCTURAL_CHANGE/POLICY/LAW/
# RESEARCH 등은 이번 corpus에 real production data가 없거나 별도 파일 구조라 이번 Phase B
# 에서는 조회 함수가 없다 - 있는 척하지 않는다). 지원되는 대상만 True로 표시한다.
_SUPPORTED_TARGETS = {"FACT", "EVENT", "CHANGE", "DOCUMENT", "SOURCE", "KNOWLEDGE_MEMORY"}


def plan_retrieval(intent):
    targets = INTENT_RETRIEVAL_TARGETS.get(intent, ())
    supported = [t for t in targets if t in _SUPPORTED_TARGETS]
    unsupported = [t for t in targets if t not in _SUPPORTED_TARGETS]
    return {
        "intent": intent,
        "targets": list(targets),
        "supported_targets": supported,
        "unsupported_targets": unsupported,
    }
