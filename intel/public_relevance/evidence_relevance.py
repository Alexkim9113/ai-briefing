# N-2 -- PUBLIC_RELEVANCE and EVIDENCE_RELEVANCE are two independent axes (Te's explicit N-2
# mandate, Section 10). A document can be PUBLIC_RELEVANCE=NOT_PUBLIC_AI_CONTENT while still being
# EVIDENCE_RELEVANCE=RELEVANT_TO_<hypothesis> -- e.g. a general electricity-statistics article is
# not AI news, but is real counterevidence/alternative-explanation material for AI_ENERGY_INFRA.
# This module NEVER derives one field from the other.
import re

EVIDENCE_RELEVANCE_VALUES = ("RELEVANT_TO_HYPOTHESIS", "NOT_EVIDENCE_RELEVANT", "UNKNOWN")

# Keyword sets mirroring the two hypotheses this corpus already has a live Entry-Gate chain for
# (AI_ENERGY_INFRA from M.6, AI_LABOR from N-0) -- deliberately narrow and reused, not invented.
_HYPOTHESIS_KEYWORDS = {
    "AI_ENERGY_INFRA": (
        "전력", "전력망", "데이터센터", "반도체", "에너지", "발전소", "송전", "전력 수요",
        "electricity", "power grid", "power demand", "data center", "datacenter", "semiconductor",
        "energy consumption", "grid", "utility",
    ),
    "AI_LABOR": (
        "노동", "고용", "일자리", "실업률", "노동시장", "임금",
        "labor market", "employment", "unemployment", "workforce", "job market", "wages",
    ),
}


def _text(doc):
    return f"{doc.get('title') or ''} {doc.get('abstract_excerpt') or ''}".lower()


def classify_evidence_relevance(doc):
    """Deterministic keyword match against the hypotheses this corpus already tracks. Returns
    (evidence_relevance, matched_hypotheses). Never promotes a document to EVIDENCE_RELEVANCE based
    on its PUBLIC_RELEVANCE category -- the two checks never read each other's result."""
    text = _text(doc)
    if not text.strip():
        return "UNKNOWN", []
    matched = [h for h, kws in _HYPOTHESIS_KEYWORDS.items() if any(kw.lower() in text for kw in kws)]
    if matched:
        return "RELEVANT_TO_HYPOTHESIS", matched
    return "NOT_EVIDENCE_RELEVANT", []


def compute_relevance_scope(public_relevance_class, public_relevance_classes, evidence_relevance, content_depth):
    """RELEVANCE_SCOPES = DIRECT/STRUCTURAL/CONTEXTUAL/IRRELEVANT/UNKNOWN (Section 11). DIRECT:
    document is itself in a public AI category. STRUCTURAL: not public AI content, but matches a
    tracked hypothesis's evidence keywords (e.g. power-grid/labor statistics) -- real structural
    evidence for an AI Intelligence Object even though the article itself is not AI news.
    CONTEXTUAL: not public, not a direct hypothesis-keyword match, but has enough real content
    (not TITLE_ONLY) to plausibly serve as background. IRRELEVANT: none of the above. UNKNOWN:
    insufficient signal to decide (no title/abstract text at all)."""
    if public_relevance_class in public_relevance_classes:
        return "DIRECT"
    if evidence_relevance == "UNKNOWN":
        return "UNKNOWN"
    if evidence_relevance == "RELEVANT_TO_HYPOTHESIS":
        return "STRUCTURAL"
    if content_depth in ("CONTENT_COMPLETE", "CONTENT_PARTIAL"):
        return "CONTEXTUAL"
    return "IRRELEVANT"
