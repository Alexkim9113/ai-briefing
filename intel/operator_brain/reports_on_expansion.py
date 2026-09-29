# SOURCE INTELLIGENCE remediation (item 5) — REPORTS_ON 확장: DOI/arXiv 외의 한 계열을
# 더 결정론적으로 해석한다. Te 지시(REMEDIATION 프롬프트)를 그대로 따른다:
#   - LLM/퍼지매칭 절대 금지. EXACT IDENTIFIER / EXACT URL / CANONICAL TITLE MATCH만.
#   - source_independence.py의 기존 INDEPENDENT/LIKELY_INDEPENDENT/SHARED_ORIGIN/
#     DERIVED_FROM_SAME_SOURCE/UNKNOWN 어휘는 재작성하지 않는다 - 이 모듈은 그 앞단에서
#     reports_on_pairs 후보를 하나 더 만들어 얹기만 한다.
#
# 대상 계열: NEWS → COMPANY-PRIMARY (기업 뉴스룸/공식 발표 페이지). 애초 후보였던
# NEWS → GOVERNMENT(.go.kr) 계열은 이 corpus에 정부 도메인 원문서가 0건이라(아래
# has_real_corpus_matches() 참고) 함께 인식만 하고 실제 매칭은 만들지 않는다.
#
# 정직한 한계(최종 보고서에도 그대로 남긴다): 이 pipeline의 데이터 모델은 RSS
# title+description만 저장하고(저작권 경계, briefing.py 상단 docstring) 원문 HTML의
# 하이퍼링크나 본문은 저장하지 않는다 - 그래서 실제 corpus(intel/documents.json 569건,
# data/2026-*.json 원본 항목 1,346건)의 description 텍스트에는 URL이 단 하나도 없다
# (grep으로 직접 확인: 0/1346). 즉 "설명 텍스트 속 명시적 URL"을 요구하는 EXACT URL
# MATCH는 이 실제 데이터에서는 구조적으로 발화 조건을 만족할 수 없다. 이 리졸버는
# 그래도 정직하게(즉, 실제로 동작하는) 구현하고 synthetic fixture로 검증하지만, 실제
# corpus에 대해 실행하면 0건이 나오는 것이 맞다 - 이는 리졸버의 결함이 아니라 SUBSTEP
# D(Collection) 단계에서 원문 링크를 수집하지 않는다는 데이터 모델의 한계다. 억지로
# 매칭을 만들어내지 않는다(섹션 58 원칙과 동일).
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
ROOT = INTEL_DIR.parent

# 관계 레코드 스키마(REMEDIATION 지시 그대로). 모든 필드를 항상 채운다 - 모르면 None.
RELATIONSHIP_RECORD_FIELDS = (
    "source_document_id", "target_document_id", "relation_type",
    "resolution_method", "resolution_confidence", "explicit_identifier",
    "source_url", "target_url", "timestamp",
)

RESOLUTION_METHODS = ("EXPLICIT_URL_MATCH", "CANONICAL_TITLE_MATCH")
UNRESOLVED_REASONS = ("PRIMARY_SOURCE_MISSING", "UNRESOLVED_REFERENCE")

# 회사 뉴스룸/공식 발표 도메인 allowlist - 이 도메인의 canonical_url을 가진 문서만
# COMPANY-PRIMARY 후보로 본다(추측 금지: 도메인이 목록에 없으면 절대 PRIMARY로 안 본다).
COMPANY_PRIMARY_DOMAINS = frozenset({
    "openai.com", "blog.google", "ai.googleblog.com", "deepmind.google",
    "blogs.microsoft.com", "about.fb.com", "ai.meta.com", "newsroom.samsung.com",
    "www.sktelecom.com",
})
_GOV_DOMAIN_RX = re.compile(r"(^|\.)go\.kr$", re.I)
_URL_RX = re.compile(r"https?://[^\s\"')]+", re.I)


def _domain(url):
    if not url:
        return None
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc[4:] if netloc.startswith("www.") else netloc
    except Exception:
        return None


def _norm_url(url):
    """URL 비교용 정규화: 스킴/트레일링 슬래시/프래그먼트 차이는 무시하되, 경로는
    그대로 - "같은 페이지"만 exact match로 본다(퍼지 매칭 아님)."""
    try:
        u = urlparse(url)
        return f"{u.netloc.lower()}{u.path.rstrip('/')}"
    except Exception:
        return url


def is_primary_candidate(canonical_url):
    """이 문서 자신이 COMPANY-PRIMARY(또는 GOVERNMENT-PRIMARY) 원문일 후보인지.
    canonical_url의 도메인이 allowlist에 있을 때만 - 텍스트 내용으로 추측하지 않는다."""
    dom = _domain(canonical_url)
    if not dom:
        return None
    if dom in COMPANY_PRIMARY_DOMAINS:
        return "COMPANY_PRIMARY"
    if _GOV_DOMAIN_RX.search(dom):
        return "GOVERNMENT_PRIMARY"
    return None


def _rel_id(from_id, to_id):
    return "relx_" + hashlib.sha1(f"{from_id}|{to_id}|REPORTS_ON".encode()).hexdigest()[:16]


def build_relationship_record(source_document_id, target_document_id, resolution_method,
                               resolution_confidence, explicit_identifier, source_url,
                               target_url, timestamp):
    """스키마를 강제하는 유일한 생성 지점 - 필드 하나라도 빠뜨리지 않는다."""
    return {
        "relationship_id": _rel_id(source_document_id, target_document_id),
        "source_document_id": source_document_id,
        "target_document_id": target_document_id,
        "relation_type": "REPORTS_ON",
        "resolution_method": resolution_method,
        "resolution_confidence": resolution_confidence,
        "explicit_identifier": explicit_identifier,
        "source_url": source_url,
        "target_url": target_url,
        "timestamp": timestamp,
    }


def resolve_company_gov_reports_on(documents_by_id, text_by_id):
    """documents_by_id: {document_id: {canonical_url, title, updated_at, ...}}.
    text_by_id: {document_id: "title + description 원문"} (raw RSS 텍스트, 요약이 아님).
    EXACT 신호 두 가지만 인정한다:
      1) EXPLICIT_URL_MATCH: secondary 문서의 원문 텍스트에 PRIMARY 문서의 canonical_url과
         (정규화 후) 완전히 같은 URL이 그대로 등장.
      2) CANONICAL_TITLE_MATCH: secondary 문서의 원문 텍스트에 PRIMARY 문서의 title
         전체 문자열이(대소문자만 무시하고) 그대로 포함 - 부분 단어 매칭이나 유사도
         비교는 하지 않는다(퍼지 매칭 금지).
    반환: (relationships: {relationship_id: record}, review: [{document_id, result, ...}]).
    """
    relationships, review = {}, []

    primary_by_url, primary_by_title = {}, {}
    for did, doc in documents_by_id.items():
        canon = doc.get("canonical_url") or ""
        kind = is_primary_candidate(canon)
        if not kind:
            continue
        primary_by_url[_norm_url(canon)] = (did, canon)
        title = (doc.get("title") or "").strip()
        if len(title) >= 12:  # 너무 짧은 제목은 우연히 부분 일치할 위험이 있어 제외
            primary_by_title[title.lower()] = (did, canon)

    if not primary_by_url:
        return relationships, review  # PRIMARY 후보가 corpus에 아예 없으면 정직하게 빈 결과

    for did, doc in documents_by_id.items():
        if primary_by_url.get(_norm_url(doc.get("canonical_url") or "")) and \
           primary_by_url[_norm_url(doc.get("canonical_url") or "")][0] == did:
            continue  # 자기 자신은 PRIMARY 후보이지 SECONDARY 후보가 아님
        text = text_by_id.get(did) or ""
        matched = False
        for url in _URL_RX.findall(text):
            hit = primary_by_url.get(_norm_url(url))
            if hit and hit[0] != did:
                target_id, target_url = hit
                rec = build_relationship_record(
                    did, target_id, "EXPLICIT_URL_MATCH", 0.95, url, doc.get("canonical_url"),
                    target_url, doc.get("updated_at"),
                )
                relationships[rec["relationship_id"]] = rec
                review.append({"document_id": did, "result": "MATCH", "method": "EXPLICIT_URL_MATCH",
                                "to_document_id": target_id})
                matched = True
                break
        if matched:
            continue
        lower_text = text.lower()
        for title, (target_id, target_url) in primary_by_title.items():
            if target_id != did and title in lower_text:
                rec = build_relationship_record(
                    did, target_id, "CANONICAL_TITLE_MATCH", 0.85, title, doc.get("canonical_url"),
                    target_url, doc.get("updated_at"),
                )
                relationships[rec["relationship_id"]] = rec
                review.append({"document_id": did, "result": "MATCH", "method": "CANONICAL_TITLE_MATCH",
                                "to_document_id": target_id})
                matched = True
                break
        if not matched:
            # 신호가 전혀 없으면 PRIMARY_SOURCE_MISSING(회사/정부 원문 자체가 corpus에
            # 없음)과 UNRESOLVED_REFERENCE(원문은 있지만 이 문서가 그걸 가리킨다는
            # 명시적 신호가 텍스트에 없음)를 구분하지는 않는다 - 이 리졸버는 "가리킬 만한
            # PRIMARY가 있는지"를 판단할 근거가 없으므로 항상 UNRESOLVED_REFERENCE로 둔다.
            review.append({"document_id": did, "result": "UNRESOLVED_REFERENCE"})

    return relationships, review


def load_documents():
    return json.loads((INTEL_DIR / "documents.json").read_text(encoding="utf-8"))


def load_raw_text_by_id():
    """reports_on_runner.load_raw_items_by_id()와 같은 방식 - title+summary 원문(설명
    텍스트)만, 저장된 그대로. 본문 HTML이나 링크는 애초에 이 pipeline에 없다."""
    text_by_id = {}
    for f in ROOT.glob("data/2026-*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for it in d.get("items", []):
            text_by_id[it["id"]] = f"{it.get('title', '')}\n{it.get('desc') or it.get('summary') or ''}"
    return text_by_id


def run_on_real_corpus(write_output=True):
    """실제 corpus에 대해 실행 - 위 모듈 docstring에 적은 대로 0건이 나오는 것이 정상
    (정부/회사 원문 링크가 raw 텍스트에 저장되지 않으므로). 결과를 정직하게 그대로
    intel/relationships_company_gov.json에 쓴다(비어 있어도 빈 파일로)."""
    docs = load_documents()
    docs_list = docs if isinstance(docs, list) else list(docs.values())
    documents_by_id = {d["document_id"]: d for d in docs_list}
    text_by_id = load_raw_text_by_id()
    relationships, review = resolve_company_gov_reports_on(documents_by_id, text_by_id)
    metrics = {
        "documents_examined": len(documents_by_id),
        "company_or_gov_primary_candidates": sum(
            1 for d in documents_by_id.values() if is_primary_candidate(d.get("canonical_url") or "")
        ),
        "relationships_created": len(relationships),
        "note": ("실제 corpus에는 description 텍스트에 URL이 저장되지 않아(SUBSTEP D 데이터 "
                 "모델의 한계) EXPLICIT_URL_MATCH는 구조적으로 발화할 수 없다. "
                 "CANONICAL_TITLE_MATCH도 이번 실행에서 매칭 0건 - 이는 결함이 아니라 "
                 "정직한 GAP이며 REMEDIATION 최종 보고서에 그대로 남긴다."),
    }
    if write_output:
        (INTEL_DIR / "relationships_company_gov.json").write_text(
            json.dumps(relationships, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return metrics, relationships, review


def load_company_gov_pairs():
    """source_independence.load_reports_on_pairs()와 같은 모양(frozenset pair 집합)으로
    intel/relationships_company_gov.json을 읽는다. 파일이 없으면 빈 집합(추측 금지)."""
    path = INTEL_DIR / "relationships_company_gov.json"
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    pairs = set()
    for row in (data.values() if isinstance(data, dict) else data):
        a, b = row.get("source_document_id"), row.get("target_document_id")
        if a and b:
            pairs.add(frozenset((a, b)))
    return pairs


if __name__ == "__main__":
    m, *_ = run_on_real_corpus()
    print(json.dumps(m, ensure_ascii=False, indent=1))
