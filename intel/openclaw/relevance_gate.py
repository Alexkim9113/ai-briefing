# O-4B — AI RELEVANCE GATE (client directive section 1). Operator-only, read-only against
# intel/openclaw/discoveries.json; never touches Public briefing.py/data/*.json.
#
# PASS / NEEDS_REVIEW / FAIL, decided ONLY from the actual original_title + raw_description text
# (never from source_name/source_type alone -- "NIST의 일반 사이버보안 지원사업처럼, 출처가
# 신뢰도 높은 PRIMARY Source라도 내용이 AI와 무관하면 FAIL"). No LLM here: a transparent,
# auditable keyword gate is the honest zero-cost choice for a PASS/FAIL/NEEDS_REVIEW *gate*
# (Korean synthesis -- a genuinely generative task -- is a separate concern, see
# knowledge_synthesis.py). Every keyword list below is reviewable in a diff; nothing is hidden
# inside a model call that could silently drift.
#
# SOURCE QUALITY (source_type: PRIMARY/NEWS/RESEARCH) and AI RELEVANCE are kept as separate
# values on purpose (directive section 1): this module never reads source_type to raise or
# lower a verdict, only to label source_tier for display.

import re

# Strong, unambiguous AI signal -- presence of any ONE of these in title/description is
# sufficient for PASS on its own (directive section 1's PASS list: AI 모델/Agent/생성형AI/
# AI반도체/AI데이터센터/AI규제/AI저작권/AI노동시장/AI의료/AI교육/AI국방/AI예술/AI안전/AI연구).
_STRONG_AI_PATTERNS = [
    r"\bAI\b", r"\bA\.I\.\b",
    # Chinese headlines write "AI" in Latin letters glued directly onto Hanzi with no space
    # (e.g. "AI训练", "版权AI"), so \b does not fire there (CJK characters are \w under Python's
    # Unicode-aware regex). These two patterns catch AI directly touching a CJK character.
    r"AI(?=[一-鿿])", r"(?<=[一-鿿])AI",
    r"artificial intelligence", r"generative ai", r"genai",
    r"large language model", r"\bllm\b", r"machine learning", r"deep learning",
    r"neural network", r"\bchatgpt\b", r"\bgemini\b", r"\bclaude\b", r"\bcopilot\b",
    r"\bagentic\b", r"\bai agent\b", r"foundation model", r"\bai chip\b", r"\bai safety\b",
    r"\bai regulation\b", r"ai model",
    # Chinese
    "人工智能", "大模型", "生成式人工智能", "深度学习", "机器学习", "AI训练", "AI大模型",
    "AI剧", "AI芯片", "AI安全", "智能体",
    # Korean
    "인공지능", "생성형 ai", "생성형ai", "대규모 언어모델", "거대언어모델", "에이전트형 ai",
    "ai 에이전트", "ai 모델", "ai반도체", "ai 반도체", "ai규제", "ai 규제", "ai저작권",
    "ai 안전", "ai 윤리",
]

def _contains_any(text, patterns):
    if not text:
        return []
    hits = []
    for p in patterns:
        try:
            if re.search(p, text, re.IGNORECASE):
                hits.append(p)
        except re.error:
            if p in text:
                hits.append(p)
    return hits


# Topically adjacent but NOT on its own proof of AI-centrality -- these only ever produce
# NEEDS_REVIEW, and only when no strong AI keyword fired (directive section 1: "연관
# 가능성은 있으나 직접성 불명확"). Deliberately narrow: a generic word like "data" or
# "cybersecurity" is excluded on purpose, because the directive's own FAIL example is NIST's
# general cybersecurity workforce grant -- adjacency must still be a real, specific signal.
_ADJACENT_PATTERNS = [
    r"\bcopyright\b", r"\bintellectual property\b", "저작권", "지식재산", "版权", "著作权",
    r"\baccess token", r"\bidentity\b.*\btoken", "신원", "접근 토큰",
    r"\balgorithm", r"\bautomat(ed|ion)\b", r"\brobot", r"\bbiometric",
]


# Dynamic domain/topic hints reused by knowledge_synthesis.py so the relevance verdict and the
# domain assignment are derived from the same single source of truth (directive section 1 vs 8
# are related but distinct judgments -- this module owns the relevance half only).
def classify(original_title, raw_description=""):
    """Returns {"status": "PASS"|"NEEDS_REVIEW"|"FAIL", "matched_keywords": [...], "reason": str}.
    Looks only at the real text passed in -- never at source_name/source_type."""
    text = f"{original_title or ''} {raw_description or ''}"
    strong_hits = _contains_any(text, _STRONG_AI_PATTERNS)
    if strong_hits:
        return {
            "status": "PASS",
            "matched_keywords": strong_hits[:5],
            "reason": "제목/설명에 AI 핵심 키워드가 직접 등장함",
        }
    adj_hits = _contains_any(text, _ADJACENT_PATTERNS)
    if adj_hits:
        return {
            "status": "NEEDS_REVIEW",
            "matched_keywords": adj_hits[:5],
            "reason": "AI와 연관 가능한 주제(저작권/신원·토큰/알고리즘 등)는 있으나 AI가 핵심 "
                      "대상/원인이라는 직접적 표현은 없음 -- 사람 검토 필요",
        }
    return {
        "status": "FAIL",
        "matched_keywords": [],
        "reason": "제목/설명 어디에도 AI 관련 키워드가 없음 (출처 신뢰도와 무관하게 FAIL)",
    }


def source_tier(source_type):
    """SOURCE QUALITY, kept deliberately separate from ai_relevance (directive section 1)."""
    return {
        "PRIMARY": "TIER1_PRIMARY",
        "RESEARCH": "TIER1_RESEARCH",
        "NEWS": "TIER2_NEWS",
    }.get(source_type, "TIER3_UNVERIFIED")
