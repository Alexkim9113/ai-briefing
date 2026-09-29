# STAGE 7 PHASE I — Epistemic Guard. Te의 CONTINUE 지시 섹션 6/7/9/14/15: FACT vs
# INTERPRETATION vs HYPOTHESIS 분리, Claim Ceiling, Anti-Convergence, Intellectual
# Novelty Gate, Anti-Generic-Insight(섹션 48, 8개 검사). LLM이 아니라 순수 코드로 검사한다
# (섹션 3 CODE BEFORE AI) - Claude의 출력을 "믿고" 넘기지 않고 이 게이트를 통과시킨다.
import re

from schema import CLAIM_LADDER

# 섹션 7: Anti-Convergence - 새 Evidence/Mechanism 없이 반복되면 새 Insight로 인정하지
# 않을 상투구. 표면형은 최소한만(사람이 명시적으로 확장) - 자동 확장 없음.
GENERIC_CONCLUSION_PATTERNS = [
    r"human judgment (is|becomes) (important|more important)",
    r"인간의? 판단.{0,10}중요",
    r"trust becomes important",
    r"신뢰.{0,10}중요해지",
    r"responsibility becomes important",
    r"책임.{0,10}중요해지",
    r"ai (becomes|is becoming) infrastructure",
    r"ai.{0,5}인프라",
    r"new regulation is required",
    r"새로운 규제.{0,10}필요",
    r"critical thinking is important",
    r"비판적 사고.{0,10}중요",
    r"ai literacy is important",
    r"information becomes abundant",
    r"정보.{0,10}풍부해지",
]

NOVELTY_KINDS = (
    "NEW_FACT", "NEW_CHANGE", "NEW_CONNECTION", "NEW_MECHANISM", "NEW_CONTRADICTION",
    "NEW_QUESTION", "NEW_CONCEPTUAL_FRAME", "NEW_STRUCTURAL_INTERPRETATION",
    "NEW_COUNTER_EVIDENCE", "BOUNDARY_CONDITION", "REVISION_OF_EXISTING_VIEW",
    "NO_MATERIAL_INTELLECTUAL_CHANGE", "SUPPORTING_EVIDENCE_FOR_EXISTING_VIEW",
)


def detect_generic_convergence(text):
    """텍스트가 Evidence 없이도 나올 수 있는 상투적 결론과 일치하는지 - 일치하면
    "too generic" 신호(섹션 48의 1번 질문과 동일 정신: retrieved evidence 없이도 쓸 수
    있었는가?)."""
    text_l = (text or "").lower()
    hits = [p for p in GENERIC_CONCLUSION_PATTERNS if re.search(p, text_l)]
    return hits


def check_claim_ceiling(stated_ceiling, allowed_ceiling):
    """Claude가 자기 신고한 claim 강도가 Evidence Sufficiency가 허용한 ceiling을
    넘는지 검사한다(섹션 20). 넘으면 강제로 allowed_ceiling으로 낮춘다 - 무시하지 않고
    실제로 캡을 씌운다."""
    if stated_ceiling not in CLAIM_LADDER or allowed_ceiling not in CLAIM_LADDER:
        return allowed_ceiling, True
    if CLAIM_LADDER.index(stated_ceiling) > CLAIM_LADDER.index(allowed_ceiling):
        return allowed_ceiling, True  # capped=True: 실제로 낮췄다
    return stated_ceiling, False


def anti_generic_insight_test(analysis_text, context_pack, used_object_ids):
    """섹션 48의 8개 질문 중 코드로 검증 가능한 부분만 자동화한다(나머지는 사람 리뷰
    섹션 66 몫). 자동화 가능한 것: (1)(2)(6) 정도 - retrieved evidence citation 존재 여부,
    counter evidence 언급 여부, generic 문구 존재 여부."""
    findings = []
    if not used_object_ids:
        findings.append("NO_EVIDENCE_CITED — 분석이 실제 retrieved object를 인용하지 않음")
    generic_hits = detect_generic_convergence(analysis_text)
    if generic_hits:
        findings.append(f"GENERIC_CONCLUSION_DETECTED — {generic_hits}")
    if context_pack.get("counter_evidence") and "counter" not in (analysis_text or "").lower() \
            and "반박" not in (analysis_text or "") and "반증" not in (analysis_text or ""):
        findings.append("COUNTER_EVIDENCE_AVAILABLE_BUT_NOT_ADDRESSED")
    return {"passed": not findings, "findings": findings}


def assess_novelty(candidate_kind, existing_memory_statements, new_statement):
    """섹션 9(Te CONTINUE): 기존 Stage 6 Memory/Operator History와 비교해 실제로 새로운지
    검사. 최소 구현: 정규화된 문자열이 기존 statement와 동일/거의 동일하면
    SUPPORTING_EVIDENCE_FOR_EXISTING_VIEW로 낮춘다 - 억지로 NEW_*를 만들지 않는다."""
    from common import normalize_query
    norm_new = normalize_query(new_statement)
    for existing in existing_memory_statements:
        if normalize_query(existing) == norm_new:
            return "SUPPORTING_EVIDENCE_FOR_EXISTING_VIEW"
    assert candidate_kind in NOVELTY_KINDS
    return candidate_kind
