# STAGE 7 PHASE A — Scope Parser. 섹션 14: 명시되지 않은 범위를 추측하지 않는다 -
# 텍스트에 실제로 있는 신호만 추출한다. 없으면 None(UNSPECIFIED) 그대로 둔다.
import re

from schema import SCOPE_DIMENSIONS

# knowledge_memory/concept_registry.py의 CANONICAL_CONCEPTS 표면형 맵과 동일한 값을
# 의도적으로 여기 복제한다 - operator_brain과 knowledge_memory 둘 다 최상위 모듈명이
# "schema"라서 직접 import하면 sys.modules 충돌이 발생한다(두 패키지가 각자
# 섹션 59가 요구하는 schema.py를 갖는 구조라 이름이 겹친다). Stage 1-6 파일은 수정하지
# 않는다는 원칙을 지키기 위해 이쪽에서 값을 중복 보유한다 - 두 표가 갈라지면 사람이
# 명시적으로 동기화해야 한다(자동 동기화 없음, 섹션 27 "자동 확장 없음" 원칙과 동일 정신).
CANONICAL_CONCEPTS = ("AI_AGENT", "COMPUTE", "ENERGY", "GRID_CAPACITY", "COPYRIGHT",
                      "REGULATION", "AI_SAFETY")
_SURFACE_TO_CONCEPT = {
    "ai agent": "AI_AGENT", "에이전트": "AI_AGENT",
    "compute": "COMPUTE", "gpu": "COMPUTE",
    "electricity": "ENERGY", "전력": "ENERGY",
    "grid": "GRID_CAPACITY", "전력망": "GRID_CAPACITY",
    "copyright": "COPYRIGHT", "저작권": "COPYRIGHT",
    "regulation": "REGULATION", "규제": "REGULATION",
    "ai safety": "AI_SAFETY", "ai 안전": "AI_SAFETY",
}


def concepts_in_text(text):
    text_l = (text or "").lower()
    found = set()
    for surface, concept in _SURFACE_TO_CONCEPT.items():
        if surface in text_l:
            assert concept in CANONICAL_CONCEPTS
            found.add(concept)
    return sorted(found)

# Stage 6 concept_registry와 동일 원칙 - 최소한만, 사람이 명시적으로 확장.
_ENTITY_SURFACE = ["Nvidia", "OpenAI", "Anthropic", "Trump", "Meta", "LG", "네이버", "Google", "Microsoft"]
_TIME_MARKERS = {"최근": "RECENT", "올해": "THIS_YEAR", "작년": "LAST_YEAR", "이번 주": "THIS_WEEK",
                 "이번 달": "THIS_MONTH"}
_YEAR_RE = re.compile(r"\b(20\d{2})\b")


def extract_scope(text):
    scope = {dim: None for dim in SCOPE_DIMENSIONS}

    entities = [e for e in _ENTITY_SURFACE if e.lower() in text.lower()]
    if entities:
        scope["ENTITY"] = sorted(set(entities))

    concepts = concepts_in_text(text)
    if concepts:
        scope["CONCEPT"] = concepts

    for marker, value in _TIME_MARKERS.items():
        if marker in text:
            scope["TIME"] = value
            break
    year_match = _YEAR_RE.search(text)
    if year_match and scope["TIME"] is None:
        scope["TIME"] = year_match.group(1)

    # GEOGRAPHY/JURISDICTION/INDUSTRY/POPULATION/DOMAIN/TOPIC/EPISTEMIC_SCOPE: 이번 Phase A
    # 에서는 신뢰할 수 있는 표면형 목록이 없으므로 추측하지 않고 None(UNSPECIFIED)으로 둔다 -
    # 섹션 14 원칙. 향후 사람이 명시적으로 표면형을 등록하면 확장한다.
    return scope
