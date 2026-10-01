# N-0 SLICE 1 -- PUBLIC_RELEVANCE_GATE. Separates Collection Admission (a document existing in
# intel/documents.json) from Public Publication Admission (a document being allowed to appear in
# the Public Feed). Reuses the existing, already-deterministic
# intel/source_intelligence/ai_relevance.py::assess_ai_relevance() (CENTRAL/PERIPHERAL/NONE/
# AMBIGUOUS) as its base signal instead of reinventing relevance detection -- this module only
# adds the Public-facing category vocabulary and the weak-keyword-is-not-evidence rule on top.
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "source_intelligence"))
import ai_relevance  # noqa: E402

PUBLIC_CATEGORIES = (
    "AI_DIRECT", "AI_RESEARCH", "AI_POLICY", "AI_REGULATION", "AI_INFRASTRUCTURE",
    "AI_ECONOMY", "AI_LABOR", "AI_SAFETY", "AI_GOVERNANCE", "AI_CULTURE",
    "AI_SOCIAL_IMPACT", "AI_MATERIAL_IMPACT",
)

EXCLUDED_CATEGORIES = (
    "GENERAL_NEWS", "WEAK_ASSOCIATION", "INCIDENTAL_AI_MENTION", "KEYWORD_COLLISION",
    "USEFUL_BUT_UNCLASSIFIED", "NOT_RELEVANT", "INSUFFICIENT_EVIDENCE",
)

# Words that, alone, are never sufficient evidence of AI relevance (Section 2's explicit list).
# A title/summary hit on ONLY these words (no real AI term) is a KEYWORD_COLLISION, never a
# promotion to any AI_* category.
WEAK_ASSOCIATION_WORDS = (
    "data", "algorithm", "digital", "technology", "automation", "robot", "energy", "climate",
    "platform", "chip", "cloud", "innovation", "데이터", "알고리즘", "디지털", "기술", "자동화",
    "로봇", "에너지", "기후", "플랫폼", "반도체", "클라우드", "혁신",
)

# Real AI terms -- the only terms assess_ai_relevance() is ever called with here. A document that
# only contains WEAK_ASSOCIATION_WORDS and none of these can never reach CENTRAL.
# Deliberately EXCLUDES the bare 2-letter string "ai": as a substring it false-positives on
# ordinary English words (maintain/contain/remain/again/claim/email/...). A standalone "AI" token
# is instead matched separately via _AI_TOKEN_RE (word-boundary, so it only matches the real
# acronym, never a substring of a longer word).
# N-1 narrowing: "neural network"/"딥러닝"/"머신러닝"/"multi-agent"/"foundation model" etc. were
# REMOVED from this unambiguous list after N-1's negative-control audit found "neural network"
# promoting a coral-reef biology article to AI_DIRECT on a bare substring match -- these terms are
# real AI signals only WITH supporting context (source/category/field), so they live in
# content_aware_relevance.AI_TECHNIQUE_TERMS (gated by _plausible_context()) instead. This list
# keeps only terms that are not ambiguous with a non-AI domain.
AI_CORE_TERMS = (
    "인공지능", "artificial intelligence", "llm", "대규모 언어모델", "생성형 ai", "chatgpt",
    "gpt", "gemini", "claude", "agentic ai", "에이전틱 ai", "ai agent", "ai 에이전트",
)

_AI_TOKEN_RE = re.compile(r"(?<![a-zA-Z0-9])ai(?![a-zA-Z0-9])", re.IGNORECASE)


def _has_ai_token(text):
    return bool(_AI_TOKEN_RE.search(text or ""))

_SUBTYPE_FIELD_HINTS = (
    ("AI_LABOR", ("사회·노동", "노동", "고용", "일자리")),
    ("AI_POLICY", ("정책", "법·정책", "법률", "규제")),
    ("AI_REGULATION", ("규제", "regulation")),
    ("AI_INFRASTRUCTURE", ("에너지·환경", "데이터센터", "반도체", "인프라")),
    ("AI_ECONOMY", ("경제", "사회·경제", "산업")),
    ("AI_SAFETY", ("안전", "safety", "위험")),
    ("AI_GOVERNANCE", ("거버넌스", "governance", "윤리·철학·법")),
    ("AI_CULTURE", ("문화·미디어", "문화")),
    ("AI_SOCIAL_IMPACT", ("사회", "social")),
    ("AI_RESEARCH", ("국내 연구", "스탠퍼드 연구", "연구")),
)


def _has_weak_only(text_lower, has_core_term):
    if has_core_term:
        return False
    return any(w in text_lower for w in WEAK_ASSOCIATION_WORDS)


def classify_public_relevance(title, summary, field=None, existing_category=None):
    """Deterministic classification into PUBLIC_CATEGORIES or EXCLUDED_CATEGORIES. Never an LLM
    judgment call. `field`/`existing_category` are used only to pick an AI_* subtype AFTER
    assess_ai_relevance() has already confirmed real relevance -- they never grant relevance by
    themselves."""
    combined = f"{title or ''} {summary or ''}"
    combined_lower = combined.lower()
    has_core_term = any(term in combined_lower for term in AI_CORE_TERMS) or _has_ai_token(combined)

    if _has_ai_token(title or ""):
        # Standalone "AI" token in the title -- treat exactly like assess_ai_relevance()'s own
        # title_hit path (CENTRAL), without ever substring-matching "ai" inside another word.
        result = {"status": "CENTRAL", "ai_mention_count": 1,
                   "reason": "제목에 독립된 AI 토큰이 등장"}
    else:
        # Re-inject a safe synonym only when the body contains a standalone AI token, so
        # assess_ai_relevance()'s own (non-regex) substring matching never has to touch "ai"
        # directly.
        probe_terms = AI_CORE_TERMS + (("__ai_token_present__",) if _has_ai_token(summary or "") else ())
        probe_summary = (summary or "")
        if _has_ai_token(summary or ""):
            probe_summary = probe_summary + " __ai_token_present__"
        result = ai_relevance.assess_ai_relevance(title, probe_summary, probe_terms)
    status = result["status"]

    if status == "NONE":
        if _has_weak_only(combined_lower, has_core_term):
            return {"category": "KEYWORD_COLLISION", "basis": result,
                     "reason": "제목/소개글에 약한 연관 단어만 있고 실제 AI 핵심 용어가 없음"}
        return {"category": "GENERAL_NEWS", "basis": result,
                 "reason": "AI 관련 근거 없음 -- 일반 뉴스"}

    if status == "AMBIGUOUS":
        return {"category": "INSUFFICIENT_EVIDENCE", "basis": result,
                 "reason": result["reason"]}

    if status == "PERIPHERAL":
        return {"category": "WEAK_ASSOCIATION" if result["ai_mention_count"] > 0 else
                 "INCIDENTAL_AI_MENTION", "basis": result, "reason": result["reason"]}

    # status == "CENTRAL" -- real AI relevance confirmed; pick a subtype. Default AI_DIRECT.
    subtype = "AI_DIRECT"
    if field:
        for cat, hints in _SUBTYPE_FIELD_HINTS:
            if any(h in field for h in hints):
                subtype = cat
                break
    if existing_category == "papers" and subtype == "AI_DIRECT":
        subtype = "AI_RESEARCH"
    if existing_category == "policy" and subtype == "AI_DIRECT":
        subtype = "AI_POLICY"
    return {"category": subtype, "basis": result, "reason": result["reason"]}


def is_public_eligible(category):
    return category in PUBLIC_CATEGORIES
