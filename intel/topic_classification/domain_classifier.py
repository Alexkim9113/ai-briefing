# M.5F SECTIONS 3-6 -- Topic Classification Coverage audit. Te's finding (re-confirmed by direct
# count): intel/documents.json's `field` is populated only for category="papers"/"research"
# documents (via that document's arxiv/nature source_id, which already embeds a Korean topic
# suffix, e.g. src_arxiv_eess_sy_에너지_환경) -- it is None for ALL news_ko/news_global/policy
# documents (391/601 = 65.1% of the corpus), because no classification step was ever run for
# them. This module is purely ADDITIVE: it never writes documents.json or the `field` key, and
# never forces a single label -- a document can carry zero, one, or several domains, and
# DOMAIN_UNKNOWN is reported plainly rather than guessed away.
#
# DOMAIN != TOPIC (Te's distinction): this module assigns broad DOMAINs only (reusing the
# already-built, already-tested REAL_DOMAINS/PLANET_SUBDOMAINS taxonomy from
# intel/evidence_pipeline/schema.py -- per Te's "reuse existing modules maximally" instruction,
# this does NOT invent a new ~40-name taxonomy from scratch). The specific named TOPIC within a
# domain (e.g. "AI 에너지 수요") is a separate, finer-grained concern this module does not attempt.
#
# Evidence basis, in strict priority order (never fabricated, never assumed from LINK_ONLY alone):
#   1. EXISTING_FIELD   -- this document's own real `field` value (Korean editorial tag already
#                           assigned upstream for papers/research docs). Highest confidence: a
#                           human/upstream-pipeline-assigned label, not inferred by this module.
#   2. SOURCE_TOPIC_SUFFIX -- this document's source_id itself encodes a topic suffix (the arxiv/
#                           nature feed names, e.g. "..._로봇_피지컬_ai"). Same semantic strength as
#                           EXISTING_FIELD; kept as a fallback for the rare case field is missing
#                           but the source_id still carries the signal.
#   3. TITLE_KEYWORD    -- a conservative, documented keyword match against this document's own
#                           title text. LOWER confidence than 1/2 (keyword matches are
#                           topic-adjacent, not an editorial judgment) -- reported as such, never
#                           silently merged into the HIGH-confidence bucket.
# A document with no signal from any of the three gets domains=[] and confidence="NONE"
# (DOMAIN_UNKNOWN) -- never a baseless guess.
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
DOCUMENTS_PATH = INTEL_DIR / "documents.json"
OUT_PATH = HERE / "domain_classification_result.json"

sys.path.insert(0, str(INTEL_DIR / "evidence_pipeline"))
import schema as _evidence_pipeline_schema  # noqa: E402

REAL_DOMAINS = _evidence_pipeline_schema.REAL_DOMAINS
PLANET_SUBDOMAINS = _evidence_pipeline_schema.PLANET_SUBDOMAINS


def load_documents(documents_path=DOCUMENTS_PATH):
    return json.loads(Path(documents_path).read_text(encoding="utf-8"))


# --- Priority 1: existing `field` value -> domain(s). Every one of the 40 real field values this
# corpus actually uses (direct count against intel/documents.json), mapped by its own meaning --
# not guessed. A field can map to more than one domain (e.g. "로봇·피지컬 AI" is both a technology
# and, loosely, a science/research topic) when that is honestly what the label describes.
_FIELD_TO_DOMAINS = {
    "AI 일반": ("TECHNOLOGY_INFRASTRUCTURE",),
    "AI 철학": ("TECHNOLOGY_INFRASTRUCTURE", "HUMAN_SOCIETY_EDUCATION"),
    "MIT 연구": ("SCIENCE_RESEARCH",),
    "가족·출산": ("HUMAN_SOCIETY_EDUCATION",),
    "경제": ("ECONOMY_INDUSTRY_LABOR",),
    "국내 연구": ("SCIENCE_RESEARCH",),
    "국방·안보": ("SECURITY_GEOPOLITICS",),
    "국방·전쟁": ("SECURITY_GEOPOLITICS",),
    "동물": ("PLANET:ANIMALS",),
    "로봇": ("TECHNOLOGY_INFRASTRUCTURE",),
    "로봇·피지컬 AI": ("TECHNOLOGY_INFRASTRUCTURE",),
    "문화·미디어": ("CULTURE_ARTS_MEDIA",),
    "문화·예술": ("CULTURE_ARTS_MEDIA",),
    "법·윤리·정책": ("POLICY_LAW_GOVERNANCE",),
    "법률": ("POLICY_LAW_GOVERNANCE",),
    "사회": ("HUMAN_SOCIETY_EDUCATION",),
    "사회·경제": ("HUMAN_SOCIETY_EDUCATION", "ECONOMY_INDUSTRY_LABOR"),
    "사회·노동": ("HUMAN_SOCIETY_EDUCATION", "ECONOMY_INDUSTRY_LABOR"),
    "사회·미디어": ("HUMAN_SOCIETY_EDUCATION", "CULTURE_ARTS_MEDIA"),
    "스탠퍼드 연구": ("SCIENCE_RESEARCH",),
    "언어·LLM": ("TECHNOLOGY_INFRASTRUCTURE",),
    "에너지·환경": ("PLANET:ENERGY", "PLANET:ENVIRONMENT"),
    "에이전트": ("TECHNOLOGY_INFRASTRUCTURE",),
    "여성": ("HUMAN_SOCIETY_EDUCATION",),
    "윤리·철학": ("HUMAN_SOCIETY_EDUCATION",),
    "윤리·철학·법": ("HUMAN_SOCIETY_EDUCATION", "POLICY_LAW_GOVERNANCE"),
    "저작권": ("POLICY_LAW_GOVERNANCE",),
    "저작권·미디어": ("POLICY_LAW_GOVERNANCE", "CULTURE_ARTS_MEDIA"),
    "정신건강": ("HUMAN_SOCIETY_EDUCATION",),
    "정치": ("POLICY_LAW_GOVERNANCE",),
    "정치·국방": ("POLICY_LAW_GOVERNANCE", "SECURITY_GEOPOLITICS"),
    "철학·윤리": ("HUMAN_SOCIETY_EDUCATION",),
    "철학·윤리·예술": ("HUMAN_SOCIETY_EDUCATION", "CULTURE_ARTS_MEDIA"),
    "청소년": ("HUMAN_SOCIETY_EDUCATION",),
    "청소년·가족": ("HUMAN_SOCIETY_EDUCATION",),
    "청소년·가족·여성": ("HUMAN_SOCIETY_EDUCATION",),
    "청소년·정신건강": ("HUMAN_SOCIETY_EDUCATION",),
    "피지컬 AI": ("TECHNOLOGY_INFRASTRUCTURE",),
    "환경·동물": ("PLANET:ENVIRONMENT", "PLANET:ANIMALS"),
    "환경·에너지·동물": ("PLANET:ENVIRONMENT", "PLANET:ENERGY", "PLANET:ANIMALS"),
}

# --- Priority 2: the arxiv/nature-style source_id itself carries the same Korean topic suffix as
# `field` (e.g. src_arxiv_eess_sy_에너지_환경). Fallback only -- in this corpus `field` already
# covers every such document, so this path is a safety net for a future document that arrives
# with a recognized source_id but no `field` yet set.
_SOURCE_TOPIC_SUFFIX_TO_DOMAINS = {
    "에너지_환경": ("PLANET:ENERGY", "PLANET:ENVIRONMENT"),
    "로봇_피지컬_ai": ("TECHNOLOGY_INFRASTRUCTURE",),
    "에이전트": ("TECHNOLOGY_INFRASTRUCTURE",),
    "언어_llm": ("TECHNOLOGY_INFRASTRUCTURE",),
    "법_윤리_정책": ("POLICY_LAW_GOVERNANCE",),
    "사회_미디어": ("HUMAN_SOCIETY_EDUCATION", "CULTURE_ARTS_MEDIA"),
    "경제": ("ECONOMY_INDUSTRY_LABOR",),
    "사회": ("HUMAN_SOCIETY_EDUCATION",),
    "ai_일반": ("TECHNOLOGY_INFRASTRUCTURE",),
    "문화_예술": ("CULTURE_ARTS_MEDIA",),
}

# --- Priority 3: conservative title-keyword evidence, used ONLY when no structured signal (1/2)
# exists for this document. Keywords were chosen from a real random sample of this corpus's own
# unclassified (field=None) titles (see M.5F Section 3-6 audit), not guessed abstractly. Lower
# confidence than 1/2 -- reported as TITLE_KEYWORD basis, never silently merged into HIGH.
_TITLE_KEYWORD_TO_DOMAIN = {
    # TECHNOLOGY_INFRASTRUCTURE
    "ai": "TECHNOLOGY_INFRASTRUCTURE", "인공지능": "TECHNOLOGY_INFRASTRUCTURE",
    "데이터센터": "TECHNOLOGY_INFRASTRUCTURE", "data center": "TECHNOLOGY_INFRASTRUCTURE",
    "반도체": "TECHNOLOGY_INFRASTRUCTURE", "semiconductor": "TECHNOLOGY_INFRASTRUCTURE",
    "chip": "TECHNOLOGY_INFRASTRUCTURE", "클라우드": "TECHNOLOGY_INFRASTRUCTURE",
    "소프트웨어": "TECHNOLOGY_INFRASTRUCTURE", "robot": "TECHNOLOGY_INFRASTRUCTURE",
    "로봇": "TECHNOLOGY_INFRASTRUCTURE",
    # POLICY_LAW_GOVERNANCE
    "regulation": "POLICY_LAW_GOVERNANCE", "규제": "POLICY_LAW_GOVERNANCE",
    "policy": "POLICY_LAW_GOVERNANCE", "정책": "POLICY_LAW_GOVERNANCE",
    "법안": "POLICY_LAW_GOVERNANCE", "lawsuit": "POLICY_LAW_GOVERNANCE",
    "소송": "POLICY_LAW_GOVERNANCE", "congress": "POLICY_LAW_GOVERNANCE",
    "국회": "POLICY_LAW_GOVERNANCE", "정부": "POLICY_LAW_GOVERNANCE",
    "government": "POLICY_LAW_GOVERNANCE",
    # ECONOMY_INDUSTRY_LABOR
    "acquiring": "ECONOMY_INDUSTRY_LABOR", "acquisition": "ECONOMY_INDUSTRY_LABOR",
    "인수": "ECONOMY_INDUSTRY_LABOR", "투자": "ECONOMY_INDUSTRY_LABOR",
    "investment": "ECONOMY_INDUSTRY_LABOR", "실적": "ECONOMY_INDUSTRY_LABOR",
    "earnings": "ECONOMY_INDUSTRY_LABOR", "공장": "ECONOMY_INDUSTRY_LABOR",
    "factory": "ECONOMY_INDUSTRY_LABOR", "고용": "ECONOMY_INDUSTRY_LABOR",
    "employment": "ECONOMY_INDUSTRY_LABOR", "노동": "ECONOMY_INDUSTRY_LABOR",
    "일자리": "ECONOMY_INDUSTRY_LABOR", "주가": "ECONOMY_INDUSTRY_LABOR", "stock": "ECONOMY_INDUSTRY_LABOR",
    # HUMAN_SOCIETY_EDUCATION
    "교육": "HUMAN_SOCIETY_EDUCATION", "education": "HUMAN_SOCIETY_EDUCATION",
    "학교": "HUMAN_SOCIETY_EDUCATION", "school": "HUMAN_SOCIETY_EDUCATION",
    # CULTURE_ARTS_MEDIA
    "문화": "CULTURE_ARTS_MEDIA", "culture": "CULTURE_ARTS_MEDIA",
    "미디어": "CULTURE_ARTS_MEDIA", "예술": "CULTURE_ARTS_MEDIA", "영화": "CULTURE_ARTS_MEDIA",
    # SECURITY_GEOPOLITICS
    "안보": "SECURITY_GEOPOLITICS", "security": "SECURITY_GEOPOLITICS",
    "국방": "SECURITY_GEOPOLITICS", "defense": "SECURITY_GEOPOLITICS",
    "military": "SECURITY_GEOPOLITICS", "전쟁": "SECURITY_GEOPOLITICS", "war": "SECURITY_GEOPOLITICS",
    "외교": "SECURITY_GEOPOLITICS", "diplomatic": "SECURITY_GEOPOLITICS",
    # PLANET
    "에너지": "PLANET:ENERGY", "energy": "PLANET:ENERGY", "전력": "PLANET:ENERGY",
    "기후": "PLANET:CLIMATE", "climate": "PLANET:CLIMATE", "탄소": "PLANET:CLIMATE", "carbon": "PLANET:CLIMATE",
    "환경": "PLANET:ENVIRONMENT", "environment": "PLANET:ENVIRONMENT",
    "동물": "PLANET:ANIMALS", "animal": "PLANET:ANIMALS",
}
_TITLE_KEYWORD_PATTERN = re.compile(
    "|".join(re.escape(k) for k in sorted(_TITLE_KEYWORD_TO_DOMAIN, key=len, reverse=True)),
    re.IGNORECASE,
)


def classify_document(doc):
    """Returns {"domains": [...], "basis": "EXISTING_FIELD"|"SOURCE_TOPIC_SUFFIX"|
    "TITLE_KEYWORD"|"NONE", "confidence": "HIGH"|"MEDIUM"|"LOW"|"NONE"}. Never forces a single
    label; domains is a sorted, deduplicated list and can be empty (DOMAIN_UNKNOWN)."""
    field = doc.get("field")
    if field and field in _FIELD_TO_DOMAINS:
        return {"domains": sorted(_FIELD_TO_DOMAINS[field]), "basis": "EXISTING_FIELD", "confidence": "HIGH"}

    source_id = (doc.get("source_id") or "").lower()
    for suffix, domains in _SOURCE_TOPIC_SUFFIX_TO_DOMAINS.items():
        if source_id.endswith(suffix) or f"_{suffix}" in source_id:
            return {"domains": sorted(domains), "basis": "SOURCE_TOPIC_SUFFIX", "confidence": "HIGH"}

    title = doc.get("title") or ""
    matches = set(_TITLE_KEYWORD_TO_DOMAIN[m.lower()] for m in _TITLE_KEYWORD_PATTERN.findall(title))
    if matches:
        return {"domains": sorted(matches), "basis": "TITLE_KEYWORD", "confidence": "LOW"}

    return {"domains": [], "basis": "NONE", "confidence": "NONE"}


def build_coverage_report(documents=None):
    documents = documents if documents is not None else load_documents()
    per_document = {did: classify_document(doc) for did, doc in documents.items()}

    domain_counts = Counter()
    for result in per_document.values():
        for d in result["domains"]:
            domain_counts[d] += 1
    basis_counts = Counter(r["basis"] for r in per_document.values())
    confidence_counts = Counter(r["confidence"] for r in per_document.values())
    unclassified = sum(1 for r in per_document.values() if not r["domains"])
    multi_label = sum(1 for r in per_document.values() if len(r["domains"]) > 1)
    total = len(documents)

    return {
        "note": (
            "M.5F Sections 3-6 Topic Classification Coverage audit. Additive only -- never "
            "writes documents.json/`field`. Multi-label (a document may carry 0+ domains). "
            "Reuses the existing, already-tested REAL_DOMAINS/PLANET_SUBDOMAINS taxonomy from "
            "intel/evidence_pipeline/schema.py rather than inventing a new one, per Te's "
            "'reuse existing modules maximally' instruction. Evidence basis is always reported "
            "per document (EXISTING_FIELD/SOURCE_TOPIC_SUFFIX HIGH confidence, TITLE_KEYWORD LOW "
            "confidence) -- never silently merged."
        ),
        "total_documents": total,
        "documents_unclassified": unclassified,
        "documents_unclassified_fraction": round(unclassified / total, 4) if total else None,
        "documents_multi_label": multi_label,
        "domain_distribution": dict(domain_counts.most_common()),
        "evidence_basis_distribution": dict(basis_counts),
        "confidence_distribution": dict(confidence_counts),
        "per_document": per_document,
    }


def main():
    report = build_coverage_report()
    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {OUT_PATH}: total={report['total_documents']} "
        f"unclassified={report['documents_unclassified']} "
        f"({report['documents_unclassified_fraction']*100:.1f}%)"
    )


if __name__ == "__main__":
    main()
