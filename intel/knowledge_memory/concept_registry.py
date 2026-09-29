# STAGE 6 — Concept Registry(섹션 26-28). CANONICAL_CONCEPTS만 인정한다 — 임의 키워드를
# 전부 Concept으로 승격하지 않는다(섹션 26: "너무 많이 자동 생성하지 않는다"). 매핑은
# 사람이 명시적으로 검토한 표면형만 등록한다(추측 매칭 없음, 퍼지매칭 없음).
from schema import CANONICAL_CONCEPTS

# entity(고유명사)나 topic(수집 분류)이 아니라, 실제로 여러 Change/Question을 오래
# 연결하는 "사고 축"에만 매핑한다(섹션 27-28). 표면형은 최소한만 등록 — 늘리려면
# 사람이 명시적으로 이 표를 수정해야 한다(자동 확장 없음).
_SURFACE_TO_CONCEPT = {
    "ai agent": "AI_AGENT",
    "에이전트": "AI_AGENT",
    "compute": "COMPUTE",
    "gpu": "COMPUTE",
    "electricity": "ENERGY",
    "전력": "ENERGY",
    "grid": "GRID_CAPACITY",
    "전력망": "GRID_CAPACITY",
    "copyright": "COPYRIGHT",
    "저작권": "COPYRIGHT",
    "regulation": "REGULATION",
    "규제": "REGULATION",
    "ai safety": "AI_SAFETY",
    "ai 안전": "AI_SAFETY",
}


def report_concept_candidates(notes, path):
    """섹션 43-44: CANDIDATE != CANONICAL. 실제 85 Note의 entities/domains 중 canonical
    concept로 등록되지 않은, 반복 등장하는 표면형만 후보로 별도 파일에 적는다 — 이 함수는
    CANONICAL_CONCEPTS를 절대 건드리지 않는다(자동 등록 없음, 사람이 검토해야 함)."""
    from collections import Counter
    import json as _json
    counts = Counter()
    for n in notes:
        for d in (n.get("domains") or []):
            counts[d] += 1
    candidates = [{"candidate": k, "occurrences": v} for k, v in counts.items() if v >= 2]
    candidates.sort(key=lambda c: -c["occurrences"])
    with open(path, "w", encoding="utf-8") as f:
        _json.dump(candidates, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return candidates


def concepts_in_text(text):
    """statement/title 안에 등록된 표면형이 있을 때만 그 Concept을 반환한다 — 새 Concept을
    즉석에서 만들지 않는다(CANONICAL_CONCEPTS에 없는 건 절대 반환하지 않는다)."""
    text_l = (text or "").lower()
    found = set()
    for surface, concept in _SURFACE_TO_CONCEPT.items():
        if surface in text_l:
            assert concept in CANONICAL_CONCEPTS
            found.add(concept)
    return sorted(found)
