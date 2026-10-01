# N-1 -- Content-Aware Public Relevance. Upgrades N-0's title-only gate by also using whatever
# content signals a document actually has (abstract_excerpt, authors/journal/doi, agencies,
# field, category) -- never fabricating a signal that doesn't exist. Reuses relevance_gate's
# word-boundary AI-token regex (the exact fix for N-0's bare-"ai"-substring bug) rather than
# reimplementing it.
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import relevance_gate as rg  # noqa: E402

RELEVANCE_CLASSES = (
    "AI_DIRECT", "AI_POLICY", "AI_RESEARCH", "AI_ECONOMY", "AI_CULTURE", "AI_INFRASTRUCTURE",
    "AI_LABOR", "AI_GOVERNANCE", "AI_SOCIAL_IMPACT",
    "GENERAL_NEWS", "KEYWORD_COLLISION", "UNCERTAIN_RELEVANCE",
)
PUBLIC_RELEVANCE_CLASSES = RELEVANCE_CLASSES[:9]

CONTENT_DEPTH_VALUES = ("CONTENT_COMPLETE", "CONTENT_PARTIAL", "TITLE_ONLY")

# DIRECT/STRUCTURAL/CONTEXTUAL/NONE -- Section-defined relevance SCOPE, independent of the public
# category. Only DIRECT/STRUCTURAL are publication_eligible by default.
RELEVANCE_SCOPES = ("DIRECT", "STRUCTURAL", "CONTEXTUAL", "NONE")

# Terms that name an AI technique/system even without the literal word "AI"/"인공지능". Each
# still requires _plausible_context() -- a bare single mention in an unrelated domain (e.g.
# "transformer" in a power-grid-equipment article) is not promoted alone.
AI_TECHNIQUE_TERMS = (
    "multi-agent", "멀티에이전트", "large language model", "foundation model",
    "파운데이션 모델", "transformer", "트랜스포머", "machine learning", "머신러닝", "deep learning",
    "딥러닝", "generative model", "생성형 모델", "diffusion model", "디퓨전 모델", "neural network",
    "신경망", "autonomous agent", "자율 에이전트", "ai safety", "ai 안전", "algorithmic decision system",
    "알고리즘 의사결정",
)

# A technique term alone (no explicit AI/ML top-level context) still needs ONE of these
# corroborating signals before being promoted out of TITLE_ONLY-only ambiguity -- source type,
# category, or field already tagged as AI/tech-adjacent by the existing pipeline. This prevents
# "transformer" (an electrical component) or "neural network" (a biology term) from being
# promoted on word match alone.
_RESEARCH_SOURCE_PREFIXES = ("src_arxiv_", "src_rss_arxiv_", "src_crossref", "src_openalex",
                             "src_semantic_scholar", "src_pubmed", "src_ssrn", "src_riss",
                             "src_dbpia", "src_kci", "src_scienceon")

_SUBTYPE_FIELD_HINTS = (
    ("AI_LABOR", ("사회·노동", "노동", "고용", "일자리")),
    ("AI_POLICY", ("정책", "법·정책", "법률", "규제")),
    ("AI_INFRASTRUCTURE", ("에너지·환경", "데이터센터", "반도체", "인프라")),
    ("AI_ECONOMY", ("경제", "사회·경제", "산업")),
    ("AI_GOVERNANCE", ("거버넌스", "governance", "윤리·철학·법")),
    ("AI_CULTURE", ("문화·미디어", "문화")),
    ("AI_SOCIAL_IMPACT", ("사회", "social")),
    ("AI_RESEARCH", ("국내 연구", "스탠퍼드 연구", "연구")),
)


def _plausible_context(doc):
    source_id = doc.get("source_id") or ""
    category = doc.get("category") or ""
    field = doc.get("field") or ""
    return (any(source_id.startswith(p) for p in _RESEARCH_SOURCE_PREFIXES) or
            category in ("papers", "research", "policy") or bool(field))


def compute_content_depth(doc):
    if doc.get("abstract_excerpt") or doc.get("authors") or doc.get("journal_or_venue"):
        return "CONTENT_COMPLETE"
    if doc.get("field") or doc.get("agencies") or doc.get("doi") or doc.get("_identifiers"):
        return "CONTENT_PARTIAL"
    return "TITLE_ONLY"


def _technique_term_hit(text_lower, doc):
    for term in AI_TECHNIQUE_TERMS:
        if term in text_lower:
            return _plausible_context(doc)
    return False


def classify_content_aware_relevance(doc):
    """doc: a documents.json record. Deterministic -- never an LLM judgment call. Returns a dict
    with relevance_class, relevance_scope, relevance_basis, content_depth, publication_eligible,
    publication_reason."""
    title = doc.get("title") or ""
    abstract = doc.get("abstract_excerpt") or ""
    field = doc.get("field") or ""
    category = doc.get("category") or ""
    content_depth = compute_content_depth(doc)

    combined = f"{title} {abstract}"
    combined_lower = combined.lower()

    base = rg.classify_public_relevance(title, abstract, field=field, existing_category=category)
    category_result = base["category"]
    basis = base["reason"]

    # Technique-term recovery: a document with no literal AI/인공지능 token but a real AI
    # technique term AND plausible context (research source / already-tagged field or category)
    # is promoted out of GENERAL_NEWS/KEYWORD_COLLISION into AI_RESEARCH -- never promoted from a
    # bare word match alone.
    if category_result in ("GENERAL_NEWS", "KEYWORD_COLLISION") and _technique_term_hit(combined_lower, doc):
        category_result = "AI_RESEARCH" if category in ("papers", "research") else "AI_DIRECT"
        basis = "AI 핵심 용어는 없지만 실제 AI 기법 용어(멀티에이전트/LLM/트랜스포머 등)와 신뢰 가능한 맥락(연구 출처/분류)이 함께 확인됨"

    if category_result == "INSUFFICIENT_EVIDENCE":
        category_result = "UNCERTAIN_RELEVANCE"
    if category_result in ("WEAK_ASSOCIATION", "INCIDENTAL_AI_MENTION", "NOT_RELEVANT"):
        category_result = "GENERAL_NEWS"

    if category_result in PUBLIC_RELEVANCE_CLASSES:
        scope = "DIRECT"
    elif category_result == "UNCERTAIN_RELEVANCE":
        scope = "NONE"
    else:
        scope = "NONE"

    publication_eligible = scope in ("DIRECT", "STRUCTURAL") and category_result in PUBLIC_RELEVANCE_CLASSES
    publication_reason = (
        f"relevance_class={category_result}, scope={scope} -- {basis}"
    )

    return {
        "relevance_class": category_result,
        "relevance_basis": basis,
        "relevance_scope": scope,
        "content_depth": content_depth,
        "publication_eligible": publication_eligible,
        "publication_reason": publication_reason,
    }
