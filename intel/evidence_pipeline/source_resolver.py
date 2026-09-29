# PRIMARY EVIDENCE RESOLUTION 확장(운영자 지시 섹션 6). 기존 intel/evidence_service.py의
# DOI/arXiv EXACT IDENTIFIER 파일럿을 절대 수정하지 않고 그대로 재사용(import)하며, 이
# 모듈은 그 위에 "EVIDENCE SOURCE HIERARCHY"(섹션 5) 분류만 얹는다. 외부 API·검색·퍼지매칭
# 없음 — document_service.py가 이미 만든 domain 힌트(공식 도메인 목록)를 그대로 재사용한다.
from urllib.parse import urlparse

import evidence_service as _es
import document_service as _ds
from normalize import _primary_identifier_of  # noqa: E402 — 기존 Pilot과 완전히 동일한 "자기 자신이 원문인가" 판정 재사용

from schema import EVIDENCE_SOURCE_HIERARCHY

_COURT_HINTS = ("scourt.go.kr", "supremecourt.gov", "courtlistener.com", "eur-lex.europa.eu")
_LEGISLATIVE_HINTS = ("assembly.go.kr", "congress.gov", "parliament.uk", "eur-lex.europa.eu")
_REGULATORY_HINTS = ("ftc.gov", "sec.gov", "fcc.gov", "kcc.go.kr", "ftc.go.kr", "edps.europa.eu")
_DATASET_HINTS = ("huggingface.co/datasets", "kaggle.com/datasets", "data.gov", "zenodo.org")
_WIRE_HINTS = ("reuters.com", "apnews.com", "yna.co.kr", "newsis.com")


def domain_of(url):
    if not url:
        return None
    try:
        return urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return None


def extract_identifiers(document):
    """기존 evidence_service.extract_identifiers를 그대로 재사용(제목만 — 원문 미보유이므로)."""
    return _es.extract_identifiers(document.get("title") or "")


def classify_source_hierarchy(document, domain, is_primary_self):
    """섹션 5 EVIDENCE SOURCE HIERARCHY. 우선순위: canonical_url 자신이 arXiv/Nature 원문인
    PRIMARY_RESEARCH > 법원/입법/규제/데이터셋 공식 도메인 > 정부 공식 도메인 > 기업 자사 발표 >
    통신사 재배포 > 일반 언론 > 기타. 애매하면 SECONDARY_OTHER(과대 승격 금지). is_primary_self는
    제목 안 식별자 '언급'(REPORTS_ON용)과는 다른 질문 — "이 URL 자체가 원문인가"만 본다."""
    dtype = document.get("document_type")
    if is_primary_self:
        return "PRIMARY_RESEARCH"
    if domain and any(h in domain for h in _COURT_HINTS):
        return "PRIMARY_COURT"
    if domain and any(h in domain for h in _LEGISLATIVE_HINTS):
        return "PRIMARY_LEGISLATIVE"
    if domain and any(h in domain for h in _REGULATORY_HINTS):
        return "PRIMARY_REGULATORY"
    if domain and any(h in domain for h in _DATASET_HINTS):
        return "PRIMARY_DATASET"
    if domain and any(h in domain for h in _ds._GOV_DOMAIN_HINTS):
        return "PRIMARY_OFFICIAL"
    if dtype == "COMPANY_ANNOUNCEMENT" or dtype == "PRESS_RELEASE":
        return "PRIMARY_COMPANY"
    if domain and any(h in domain for h in _WIRE_HINTS):
        return "SECONDARY_WIRE"
    if dtype == "NEWS":
        return "SECONDARY_MAJOR_MEDIA"
    return "SECONDARY_OTHER"


def resolve_document(document):
    """DOCUMENT 하나에 대한 (identifiers, source_hierarchy, domain, evidence_id) 튜플.
    "이 문서 자신이 원문인가"는 기존 normalize.py Pilot과 완전히 동일하게 canonical_url이
    arXiv/Nature 원문 URL 패턴인지로 판정한다(제목 텍스트 안의 식별자 언급과는 다른 질문 —
    후자는 REPORTS_ON 판정용 extract_identifiers가 따로 담당)."""
    domain = domain_of(document.get("canonical_url"))
    identifiers = extract_identifiers(document)
    self_kind, self_id = _primary_identifier_of({"link": document.get("canonical_url")})
    is_primary = self_kind is not None
    hierarchy = classify_source_hierarchy(document, domain, is_primary)
    assert hierarchy in EVIDENCE_SOURCE_HIERARCHY
    return {
        "domain": domain, "identifiers": identifiers, "is_primary_by_identifier": is_primary,
        "self_identifier": (self_kind, self_id) if self_kind else None,
        "source_hierarchy": hierarchy,
        "evidence_id": f"ev_{document['document_id']}",
    }
