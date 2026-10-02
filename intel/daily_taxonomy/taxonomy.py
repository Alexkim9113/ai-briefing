# O-3C -- Daily Intelligence Discovery taxonomy. Fixes the 11 top-level fields from Te's O-3C
# spec (section E) and assigns primary_field/secondary_fields[] to each AI-relevant document.
#
# Reuses, does not replace:
#   intel/ai_relevance_gate/gate.py            -- O-3B PASS/FAIL/NEEDS_REVIEW gate (corpus input)
#   intel/topic_classification/domain_classifier.py -- existing REAL_DOMAINS/PLANET_SUBDOMAINS
#                                                       classifier (EXISTING_FIELD/SOURCE_TOPIC_
#                                                       SUFFIX/TITLE_KEYWORD evidence chain)
#   intel/geographic_evidence/geography_inference.py -- existing TLD/SOURCE_ID_COUNTRY region
#                                                        inference chain
# No new classification engine is built from scratch; this module is a MAPPING layer on top of
# the above three, translating their outputs into Te's exact 11-field vocabulary and adding the
# few keyword refinements Te's spec explicitly calls for (section L: literal-"AI"-absent vocab
# expansion; the 노동·고용 vs 산업·경제 split and 의료·헬스케어 extraction that REAL_DOMAINS does
# not carry on its own).
#
# PASS -> this module only ever runs on documents that are ai_relevance_gate.GATE_PASS. FAIL/
# NEEDS_REVIEW documents are never field-classified (Discovery is an AI-relevant-events-only
# surface, section D).
#
# Additive and read-only: never writes documents.json/facts.json/production_events.json. Never
# creates a Claim/Hypothesis/Intelligence Object/Report (section AD, Canonical Boundary).
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
ROOT = INTEL_DIR.parent

sys.path.insert(0, str(INTEL_DIR / "ai_relevance_gate"))
sys.path.insert(0, str(INTEL_DIR / "topic_classification"))
sys.path.insert(0, str(INTEL_DIR / "geographic_evidence"))
import gate as _gate  # noqa: E402
import domain_classifier as _domain  # noqa: E402
import geography_inference as _geo  # noqa: E402

# Te's O-3C section E: exactly 11 top-level fields, fixed. No sub-splitting into separate
# top-level menu items (section F) -- 법·제도 absorbs 저작권/개인정보/판결/AI기본법 etc. as one
# category; those stay internal tags only (TAGS dict below), never a UI menu entry.
FIELDS = (
    "기술", "산업·경제", "노동·고용", "법·제도", "의료·헬스케어", "에너지·환경",
    "국방·안보", "교육·사회", "문화·예술", "미디어·콘텐츠", "정책·국제질서",
)

# REAL_DOMAINS/PLANET_SUBDOMAINS -> Te's 11 fields. A REAL_DOMAINS value can map to more than one
# Te-field when the existing domain genuinely spans more than one of Te's finer categories (e.g.
# HUMAN_SOCIETY_EDUCATION spans both 교육·사회 and, after the keyword split below, 노동·고용).
_DOMAIN_TO_FIELDS = {
    "TECHNOLOGY_INFRASTRUCTURE": ("기술",),
    "SCIENCE_RESEARCH": ("기술",),
    "POLICY_LAW_GOVERNANCE": ("법·제도",),
    "ECONOMY_INDUSTRY_LABOR": ("산업·경제",),  # 노동·고용 키워드 매치 시 아래서 추가
    "HUMAN_SOCIETY_EDUCATION": ("교육·사회",),
    "CULTURE_ARTS_MEDIA": ("문화·예술",),  # 미디어 키워드 매치 시 미디어·콘텐츠 추가/대체
    "SECURITY_GEOPOLITICS": ("국방·안보", "정책·국제질서"),
    "PLANET:ENERGY": ("에너지·환경",),
    "PLANET:ENVIRONMENT": ("에너지·환경",),
    "PLANET:WATER": ("에너지·환경",),
    "PLANET:CLIMATE": ("에너지·환경",),
    "PLANET:ECOLOGY": ("에너지·환경",),
    "PLANET:ANIMALS": (),  # Te's 11 fields have no slot for this -- left unmapped on purpose,
    "PLANET:BIODIVERSITY": (),  # never force-fit into an unrelated field.
}

# Section L -- deterministic vocabulary expansion for AI-central topics that don't contain a
# literal "AI"/"인공지능" token (O-3B known false negatives: "Amazon Nova Act", "agent runtime
# security"). Used only to REFINE field assignment for documents the AI Relevance Gate has
# ALREADY passed -- this module never re-decides AI relevance itself (that stays gate.py's job,
# section M: REMOVE_AI_TEST is preserved, not reimplemented here).
_TECH_VOCAB = (
    "llm", "large language model", "foundation model", "agent", "agentic", "generative",
    "inference", "transformer", "multimodal", "machine learning", "neural", "model training",
    "ai accelerator", "npu", "gpu inference", "에이전트", "생성형", "거대언어모델", "추론",
    "트랜스포머", "멀티모달", "신경망",
)

_LABOR_VOCAB = (
    "고용", "실업", "임금", "직무", "자동화", "노동 대체", "layoff", "job loss", "unemployment",
    "wage", "reskilling", "upskilling", "workforce", "노동시장", "일자리",
)

_HEALTH_VOCAB = (
    "진단", "신약", "임상", "병원", "의료기기", "헬스케어", "healthcare", "clinical", "diagnosis",
    "drug discovery", "hospital", "patient", "환자", "의료 ai", "의료진", "biotech", "바이오",
)

_DEFENSE_VOCAB = (
    "군사", "국방", "자율무기", "military", "defense", "weapon", "사이버 안보", "cyberwarfare",
    "국가안보", "national security", "정보전", "surveillance", "감시",
)

_MEDIA_VOCAB = (
    "언론", "방송", "출판", "플랫폼 콘텐츠", "광고", "creator economy", "합성미디어", "deepfake",
    "딥페이크", "ai 검색", "콘텐츠", "streaming", "newsroom",
)

_CULTURE_VOCAB = (
    "art", "예술", "전시", "미술관", "박물관", "music", "음악", "film", "영화", "game", "게임",
    "design", "디자인", "architecture", "건축", "creativ", "창작", "aesthetic", "미학",
)

_POLICY_INTL_VOCAB = (
    "export control", "수출통제", "sovereign ai", "ai 패권", "미중", "semiconductor control",
    "반도체 통제", "national ai strategy", "국가 ai 전략", "trade war", "geopolit",
)


# Guards against the classic short-substring false positive discovered during real-data QA
# (section AJ): plain `"art" in text` matches "Artificial"/"Partner"/"smart", `"game" in text`
# matches "education game" with no actual game-industry meaning. English vocabulary terms are
# matched on a word boundary; Korean terms (no word-boundary concept in the same sense, and
# compound nouns like 건축공학 would otherwise collide with 건축 as architecture-the-art) are
# matched as whole particle-delimited tokens instead of bare substrings.
def _compile_vocab(vocab):
    patterns = []
    for term in vocab:
        if re.search(r"[a-zA-Z]", term) and " " not in term:
            patterns.append(re.compile(r"(?<![a-zA-Z0-9])" + re.escape(term) + r"(?![a-zA-Z0-9])"))
        elif re.search(r"[a-zA-Z]", term):
            patterns.append(re.compile(re.escape(term)))  # multi-word English phrase, no collision risk
        else:
            patterns.append(re.compile(r"(?<![가-힣])" + re.escape(term) + r"(?![가-힣])"))
    return patterns


def _text_hits(text_lower, vocab, _cache={}):
    key = id(vocab)
    if key not in _cache:
        _cache[key] = _compile_vocab(vocab)
    return any(p.search(text_lower) for p in _cache[key])


# Real-data QA (section U/AJ) found: domain_classifier.py's CULTURE_ARTS_MEDIA domain is fed by
# several upstream collection-time Korean `field` tags that conflate two things Te's O-3C
# taxonomy now explicitly separates (section 10) -- actual arts/culture content (문화·예술,
# 철학·윤리·예술) vs. general media/content-industry business (문화·미디어, 사회·미디어,
# 저작권·미디어 collection queries, which in practice surfaced items like ad-revenue earnings
# calls and SEO course listings that merely matched that Google News query, not genuine culture
# content). Rather than trust CULTURE_ARTS_MEDIA -> 문화·예술 blindly, this module reads the
# document's own original `field` tag (already available on every document, no new classifier)
# to route the broad/ambiguous tags to 미디어·콘텐츠 by default, promoting to 문화·예술 only when
# the original tag was already a genuine arts-specific one, or the title itself carries a real
# arts/culture keyword (_CULTURE_VOCAB, checked separately below regardless of this routing).
_NARROW_CULTURE_FIELD_TAGS = {"문화·예술", "철학·윤리·예술", "문화_예술"}
_BROAD_MEDIA_FIELD_TAGS = {"문화·미디어", "사회·미디어"}


def classify_fields(title, existing_domains, source_field=None):
    """Returns (primary_field, secondary_fields[]). Never forces more than one label when the
    signal doesn't support it (section G: "모든 자료에 억지로 여러 label을 붙이지 않는다")."""
    title_lower = (title or "").lower()
    candidate_fields = []
    for dom in existing_domains:
        for f in _DOMAIN_TO_FIELDS.get(dom, ()):
            if f == "문화·예술" and source_field in _BROAD_MEDIA_FIELD_TAGS:
                f = "미디어·콘텐츠"
            if f == "문화·예술" and source_field == "저작권·미디어":
                # Te section 10: copyright's own legal question belongs to 법·제도, the
                # content-industry angle to 미디어·콘텐츠 -- not 문화·예술 either way.
                for alt in ("법·제도", "미디어·콘텐츠"):
                    if alt not in candidate_fields:
                        candidate_fields.append(alt)
                continue
            if f not in candidate_fields:
                candidate_fields.append(f)

    # Keyword refinements, additive only -- never remove a field the domain classifier already
    # gave real evidence for.
    if _text_hits(title_lower, _LABOR_VOCAB) and "노동·고용" not in candidate_fields:
        candidate_fields.append("노동·고용")
    if _text_hits(title_lower, _HEALTH_VOCAB) and "의료·헬스케어" not in candidate_fields:
        candidate_fields.append("의료·헬스케어")
    if _text_hits(title_lower, _DEFENSE_VOCAB) and "국방·안보" not in candidate_fields:
        candidate_fields.append("국방·안보")
    if _text_hits(title_lower, _MEDIA_VOCAB) and "미디어·콘텐츠" not in candidate_fields:
        candidate_fields.append("미디어·콘텐츠")
    if _text_hits(title_lower, _CULTURE_VOCAB) and "문화·예술" not in candidate_fields:
        candidate_fields.append("문화·예술")
    if _text_hits(title_lower, _POLICY_INTL_VOCAB) and "정책·국제질서" not in candidate_fields:
        candidate_fields.append("정책·국제질서")
    if not candidate_fields and _text_hits(title_lower, _TECH_VOCAB):
        candidate_fields.append("기술")

    if not candidate_fields:
        return None, []
    return candidate_fields[0], candidate_fields[1:]


def run(out_path=None):
    """Real-data runner. Only classifies documents the AI Relevance Gate PASSed (section D).
    Joins: ai_relevance_gate result (which docs qualify) + domain_classifier result (base
    domain signal) + geography_inference result (region, section H/I/J) -- three existing,
    independently-tested modules, never re-implemented here."""
    out_path = Path(out_path or HERE / "daily_taxonomy_result.json")

    documents = json.loads((INTEL_DIR / "documents.json").read_text(encoding="utf-8"))
    gate_result = _gate.run_on_documents(out_path=HERE / "_gate_scratch.json")
    domain_result = json.loads((INTEL_DIR / "topic_classification" / "domain_classification_result.json").read_text(encoding="utf-8"))
    geo_result = json.loads((INTEL_DIR / "geographic_evidence" / "geography_inference_result.json").read_text(encoding="utf-8"))
    (HERE / "_gate_scratch.json").unlink(missing_ok=True)

    # geography_inference_result.json only lists NEWLY classified docs; the rest of the "before"
    # picture (already-known country, still from admission_gate) is not reproduced here -- this
    # module asks documents.json directly for any pre-existing country field, then layers the
    # newly_classified_documents on top, exactly as geography_inference.py itself does to produce
    # "after_geographic_distribution".
    newly_classified = {d["document_id"]: d for d in geo_result.get("newly_classified_documents", [])}

    per_document = {}
    field_counts_primary = {f: 0 for f in FIELDS}
    field_counts_any = {f: 0 for f in FIELDS}  # primary + secondary -- the real per-field coverage
    region_counts = {}
    multi_field_count = 0
    unknown_region_count = 0

    for doc_id, doc in documents.items():
        gv = gate_result["results"].get(doc_id)
        if not gv or gv["gate"] != _gate.GATE_PASS:
            continue
        title = doc.get("title") or ""
        dom_info = domain_result["per_document"].get(doc_id, {"domains": []})
        primary, secondary = classify_fields(title, dom_info["domains"], doc.get("field"))

        country = doc.get("country") or (newly_classified.get(doc_id) or {}).get("country") or "UNKNOWN"
        region_counts[country] = region_counts.get(country, 0) + 1
        if country == "UNKNOWN":
            unknown_region_count += 1
        if secondary:
            multi_field_count += 1
        if primary:
            field_counts_primary[primary] += 1
            for f in (primary, *secondary):
                field_counts_any[f] += 1

        per_document[doc_id] = {
            "title": title,
            "ai_relevance": gv,
            "primary_field": primary,
            "secondary_fields": secondary,
            "country": country,
            "source_id": doc.get("source_id"),
        }

    output = {
        "fields": list(FIELDS),
        "total_pass_documents": len(per_document),
        "field_counts_primary": field_counts_primary,
        "field_counts_any": field_counts_any,
        "unclassified_field_count": sum(1 for v in per_document.values() if v["primary_field"] is None),
        "region_counts": region_counts,
        "unknown_region_count": unknown_region_count,
        "multi_field_count": multi_field_count,
        "per_document": per_document,
    }
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


if __name__ == "__main__":
    result = run()
    print(json.dumps({
        "total_pass_documents": result["total_pass_documents"],
        "field_counts_primary": result["field_counts_primary"],
        "field_counts_any": result["field_counts_any"],
        "unclassified_field_count": result["unclassified_field_count"],
        "region_counts": result["region_counts"],
        "unknown_region_count": result["unknown_region_count"],
        "multi_field_count": result["multi_field_count"],
    }, ensure_ascii=False, indent=2))
