# SOURCE INTELLIGENCE CORRECTION v1.0 — Phase K(spec 섹션 20/29/66). REMOVE_AI_TEST를
# 결정론적으로 구현한다: "AI 언급을 제거해도 central event의 의미가 본질적으로 같다면
# AI는 주변적(PERIPHERAL)"이라는 반사실적 검사. 단어 하나만으로 AI 관련성을 판정하지
# 않는다(섹션 29 마지막). 이 모듈은 SHADOW 상태다 - briefing.py의 실제 mx_note()/
# is_ai_related()에는 아직 배선하지 않았다(운영 중인 production 콘텐츠 생성 함수를
# 실사 없이 바로 바꾸는 위험을 피하기 위함 - 최종 보고서에 이 경계를 명시한다).
import re

_SENT_SPLIT = re.compile(r"(?<=[.!?다요])\s+|\n+")


def _sentences(text):
    return [s.strip() for s in _SENT_SPLIT.split(text or "") if s.strip()]


def _contains_keyword(text, keywords):
    t = (text or "").lower()
    return any(k.lower() in t for k in keywords)


def assess_ai_relevance(title, summary, ai_keywords):
    """섹션 29 REMOVE_AI_TEST. 반환: {"status": CENTRAL/PERIPHERAL/NONE,
    "ai_mention_count": int, "reason": str} - status와 함께 반드시 reason(근거)을
    남긴다(섹션 29: "score/status AND evidence/reason")."""
    title = title or ""
    summary = summary or ""
    title_hit = _contains_keyword(title, ai_keywords)
    sentences = _sentences(summary)
    ai_sentences = [s for s in sentences if _contains_keyword(s, ai_keywords)]
    non_ai_sentences = [s for s in sentences if not _contains_keyword(s, ai_keywords)]
    mention_count = (1 if title_hit else 0) + len(ai_sentences)

    if mention_count == 0:
        return {"status": "NONE", "ai_mention_count": 0,
                "reason": "제목·소개글 어디에도 AI 관련 키워드가 없음"}

    if title_hit:
        return {"status": "CENTRAL", "ai_mention_count": mention_count,
                "reason": "제목에 AI 관련 키워드가 직접 등장 - 주변부 언급으로 보기 어려움"}

    if len(ai_sentences) >= 2:
        return {"status": "CENTRAL", "ai_mention_count": mention_count,
                "reason": "소개글에서 AI 관련 언급이 2회 이상 반복됨"}

    # 단일 언급(섹션 29: 단어 하나로 판정 금지) - REMOVE_AI_TEST를 실제로 수행한다:
    # AI를 언급한 문장을 빼고 나머지가 여전히 실질적인 내용을 담고 있으면(=central event가
    # AI 없이도 성립하면) PERIPHERAL로 본다.
    remaining_text = " ".join(non_ai_sentences)
    remaining_substantive = len(re.sub(r"\s+", "", remaining_text))
    if remaining_substantive >= 10:
        return {"status": "PERIPHERAL", "ai_mention_count": mention_count,
                "reason": ("AI 언급 문장을 제거해도 나머지 소개글이 central event를 "
                           f"독립적으로 설명함(남은 실질 텍스트 {remaining_substantive}자)")}

    return {"status": "CENTRAL", "ai_mention_count": mention_count,
            "reason": "AI 언급 문장을 제거하면 남는 내용이 거의 없음 - AI가 central event 자체로 보임"}
