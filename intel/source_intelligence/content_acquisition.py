# SOURCE INTELLIGENCE CORRECTION v1.0 — Phase C(spec 섹션 15/58). 원문 본문 확보 계층.
# url_resolver.py와 동일한 원칙: fetcher는 주입 가능해야 한다. 기본값(fetcher=None)이면
# 실제 네트워크를 시도하지 않고 FETCH_NOT_ATTEMPTED를 반환한다 - 이 세션 환경은 실측
# 결과 news.google.com/reuters.com/arxiv.org 등 거의 모든 외부 호스트에 대한 outbound가
# 조직 프록시 정책으로 막혀 있다(curl 실측: CONNECT tunnel failed, 403 - evidence_supply/
# url_resolver.py가 이미 문서화한 것과 동일한 제약). 실제 fetcher는 daily.yml처럼 실제
# 네트워크가 있는 GitHub Actions 환경에서만 주입해 검증할 수 있다.
#
# HTML 본문 추출은 자체 readability 엔진을 새로 만들지 않고 검증된 OSS(trafilatura,
# MIT 라이선스, PyPI 설치 확인됨 v2.2.0)를 쓴다 - spec 섹션 5/15 REUSE BEFORE BUILD.
import re

try:
    import trafilatura
    _TRAFILATURA_AVAILABLE = True
except ImportError:
    _TRAFILATURA_AVAILABLE = False

EXTRACTOR_NAME = "trafilatura"
EXTRACTOR_VERSION = getattr(trafilatura, "__version__", None) if _TRAFILATURA_AVAILABLE else None

# 섹션 47/48: 안전 한도. 실제 값은 운영 배포 시 조정 가능하나, 기본값 자체가
# 보수적이어야 한다(단일 운영자 안정성 > crawl throughput).
MAX_HTML_BYTES = 3_000_000
MAX_PDF_BYTES = 20_000_000
REQUEST_TIMEOUT_SECONDS = 15
MAX_REDIRECTS = 5


def is_extractor_available():
    return _TRAFILATURA_AVAILABLE


def _extract_main_text(html):
    if not _TRAFILATURA_AVAILABLE or not html:
        return None
    try:
        return trafilatura.extract(html, include_comments=False, include_tables=False)
    except Exception:
        # 섹션 47: fetched content는 신뢰하지 않는 데이터 - 파서가 예외를 던져도
        # 절대 그 예외를 새로운 "사실"로 바꾸지 않는다. 조용히 실패로 처리.
        return None


def acquire_content(url, fetcher=None, structured_primary=None):
    """url: 원문 후보 URL(이미 canonical_url까지 해석된 것을 권장).
    fetcher: (url) -> {"html": str|None, "content_type": str|None, "status_code": int|None,
                        "byte_size": int|None} 형태를 반환하는 주입 가능한 함수.
    structured_primary: 이미 구조화된 1차 데이터가 있으면(예: arXiv API 응답) 그것을
    우선 쓴다(섹션 15 우선순위 1) - 이 경우 HTML fetch 자체를 시도하지 않는다.

    반환: {"status": CONTENT_STATUS_VALUES 중 하나, "text": str|None,
           "extractor": str|None, "extractor_version": str|None}
    추측 금지 - 판정할 수 없으면 UNKNOWN, 시도하지 않았으면 FETCH_FAILED가 아니라
    아예 호출하지 않는 것이 맞다(이 함수는 "시도했다"는 것을 전제로 한다)."""
    if structured_primary is not None:
        return {"status": "STRUCTURED_PRIMARY_DATA", "text": None,
                "extractor": "structured_primary_api", "extractor_version": None,
                "structured_data": structured_primary}

    if fetcher is None:
        # 실제 네트워크를 시도하지 않았다 - "실패"가 아니라 "미시도"이지만, 이 함수의
        # 반환 계약상 상태값은 CONTENT_STATUS_VALUES 안에서만 골라야 하므로 가장 가까운
        # 정직한 상태는 UNKNOWN(판정 불가)이다. 호출자는 acquired=None으로 이 함수 자체를
        # 건너뛰는 것을 기본으로 한다(content_status.assign_content_status 참고).
        return {"status": "UNKNOWN", "text": None, "extractor": None, "extractor_version": None}

    try:
        fetched = fetcher(url) or {}
    except Exception:
        return {"status": "FETCH_FAILED", "text": None, "extractor": None, "extractor_version": None}

    status_code = fetched.get("status_code")
    if status_code == 402 or fetched.get("paywalled"):
        return {"status": "PAYWALLED", "text": None, "extractor": None, "extractor_version": None}
    if status_code in (403, 999) or fetched.get("blocked"):
        return {"status": "BLOCKED", "text": None, "extractor": None, "extractor_version": None}
    if status_code and status_code >= 400:
        return {"status": "FETCH_FAILED", "text": None, "extractor": None, "extractor_version": None}

    html = fetched.get("html")
    byte_size = fetched.get("byte_size") or (len(html.encode("utf-8")) if html else 0)
    if byte_size and byte_size > MAX_HTML_BYTES:
        return {"status": "FETCH_FAILED", "text": None, "extractor": None, "extractor_version": None,
                "reason": "OVERSIZED"}

    text = _extract_main_text(html)
    if not text or len(re.sub(r"\s+", "", text)) < 200:
        # 본문이 너무 짧으면(광고/로그인 페이지 등) FULL_TEXT라고 우기지 않는다.
        if html:
            return {"status": "FETCH_FAILED", "text": None, "extractor": EXTRACTOR_NAME,
                    "extractor_version": EXTRACTOR_VERSION, "reason": "EXTRACTION_TOO_SHORT"}
        return {"status": "FETCH_FAILED", "text": None, "extractor": None, "extractor_version": None}

    return {"status": "FULL_TEXT", "text": text, "extractor": EXTRACTOR_NAME,
            "extractor_version": EXTRACTOR_VERSION}
