# SOURCE INTELLIGENCE remediation — Phase C: PRIMARY-SOURCE PROVENANCE GAP 근본 원인 수정
# (spec 섹션 6-3). 지난 라운드에서 확인된 구조적 사실: RSS 수집은 copyright 이유로
# title+description만 저장하고 원문 하이퍼링크를 전혀 저장하지 않는다
# (relationships_created=0 on 1346/1346 real RSS items). 이 모듈은 그 자체를 소급해서
# 메우지 않는다(백필 금지, 가짜 결과 생성 금지) - 대신 앞으로 content_acquisition이
# 실제로 FULL_TEXT/PARTIAL_TEXT를 확보했을 때(RSS 경로가 아니라 type-specific 원문
# fetch 경로), 그 HTML 안에서 "1차 출처로 보이는 링크"만 최소한으로 뽑아 별도
# provenance 레코드로 남기는 새 forward-looking 능력이다.
#
# briefing.py의 collection loop는 건드리지 않는다(제약 사항 그대로) - 이 모듈은
# content_acquisition.acquire_content()가 FULL_TEXT/PARTIAL_TEXT를 반환한 뒤에만
# 호출되는 별도 함수로 존재한다. 오늘 시점 RSS는 이 경로를 타지 않으므로, 실제
# 프로덕션 corpus에서는 0건이 정상이고 정직한 결과다 - 이 모듈은 합성 HTML fixture로만
# 검증됐다(테스트 파일 docstring 참고).
#
# 링크 추출은 LLM/fuzzy 매칭을 쓰지 않는다(제약: REPORTS_ON과 동일하게 결정론적).
# trafilatura가 이미 의존성으로 들어와 있으므로(content_acquisition.py) 그 HTML
# 파싱 능력을 재사용하되(REUSE BEFORE BUILD), 링크 자체는 표준 라이브러리
# html.parser로 최소한만 뽑는다 - 새 무거운 HTML 파서 의존성을 추가하지 않는다.
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlparse

# 1차 출처로 볼 수 있는 도메인 패턴만 허용한다(임의 외부 링크 전부를 provenance
# 후보로 만들지 않는다) - entity_resolution.py의 curated-seed 정신과 동일:
# 확인되지 않은 것은 넓히지 않는다.
_PRIMARY_DOMAIN_PATTERNS = (
    (re.compile(r"(^|\.)go\.kr$"), "GOVERNMENT_KR"),
    (re.compile(r"(^|\.)gov$"), "GOVERNMENT_OFFICIAL"),
    (re.compile(r"(^|\.)europa\.eu$"), "GOVERNMENT_EU_OFFICIAL"),
    (re.compile(r"(^|\.)ac\.kr$"), "ACADEMIC_KR"),
    (re.compile(r"(^|\.)edu$"), "ACADEMIC"),
    (re.compile(r"^doi\.org$"), "ACADEMIC_DOI"),
    (re.compile(r"^arxiv\.org$"), "ACADEMIC_ARXIV"),
    (re.compile(r"(^|\.)scourt\.go\.kr$"), "LEGAL_KR"),
    (re.compile(r"(^|\.)law\.go\.kr$"), "LEGAL_KR"),
    (re.compile(r"(^|\.)assembly\.go\.kr$"), "GOVERNMENT_KR_LEGISLATURE"),
    # entity_resolution 시드에 있는 공식 기업 뉴스룸 도메인(이미 사람이 확인한 것만).
    (re.compile(r"(^|\.)openai\.com$"), "COMPANY_NEWSROOM"),
    (re.compile(r"(^|\.)anthropic\.com$"), "COMPANY_NEWSROOM"),
    (re.compile(r"(^|\.)deepmind\.google$"), "COMPANY_NEWSROOM"),
    (re.compile(r"(^|\.)ai\.meta\.com$"), "COMPANY_NEWSROOM"),
)

_MAX_ANCHOR_TEXT_CHARS = 80  # 저작권 보호: 앵커 텍스트는 짧은 라벨 수준만 보관(문장 통째 금지)
_MAX_CONTEXT_CHARS = 40  # link_context도 최소한만(앞뒤 몇 단어 수준)
_MAX_LINKS_PER_DOCUMENT = 20  # 폭주 방지


class _AnchorExtractor(HTMLParser):
    """표준 라이브러리 html.parser만 사용 - 새 무거운 파서 의존성 추가 안 함.
    <a href=...>anchor text</a> 쌍만 최소한으로 뽑는다. 스크립트/스타일 내용은
    절대 실행하지 않는다(파싱만, eval/exec 없음 - 섹션 47 FETCH SECURITY 원칙과 동일)."""

    def __init__(self):
        super().__init__()
        self.links = []  # [{"href": str, "text": str}]
        self._current_href = None
        self._current_text = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self._current_href = href
            self._current_text = []

    def handle_data(self, data):
        if self._current_href is not None:
            self._current_text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._current_href is not None:
            text = "".join(self._current_text).strip()
            self.links.append({"href": self._current_href, "text": text})
            self._current_href = None
            self._current_text = []


def _classify_domain(url):
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return None, None
    if not host:
        return None, None
    for pattern, source_type in _PRIMARY_DOMAIN_PATTERNS:
        if pattern.search(host):
            return host, source_type
    return host, None


def _truncate(text, max_chars):
    text = (text or "").strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "…"


def extract_link_provenance_candidates(source_document_id, html, acquisition_content_status):
    """FULL_TEXT/PARTIAL_TEXT로 실제로 확보된 HTML에서만 호출되어야 한다(호출자 책임 -
    이 함수 자체는 content_status를 강제하지 않고 기록만 한다, 섹션 6-3 필드 그대로).
    HTML이 없거나(RSS 경로 등) 파싱 불가면 빈 리스트를 반환한다 - 추측/생성 금지.

    반환: Te 스펙 섹션 6-3의 "link provenance object" 리스트, 정확히 아래 필드만:
    source_document_id, link_url, resolved_link_url, link_domain, anchor_text,
    link_context, candidate_source_type, is_primary_candidate, resolution_method,
    resolution_status, timestamp."""
    if not html or acquisition_content_status not in ("FULL_TEXT", "PARTIAL_TEXT"):
        return []

    parser = _AnchorExtractor()
    try:
        parser.feed(html)
    except Exception:
        # 섹션 47: 신뢰하지 않는 데이터 파싱 실패는 조용히 빈 결과로 - 새 "사실"을 만들지 않는다.
        return []

    now = datetime.now(timezone.utc).isoformat()
    candidates = []
    seen_urls = set()
    for link in parser.links:
        href = (link.get("href") or "").strip()
        if not href or not href.startswith(("http://", "https://")):
            continue  # 상대경로/#anchor/mailto 등은 1차 출처 후보가 아님 - 제외
        if href in seen_urls:
            continue
        seen_urls.add(href)

        domain, source_type = _classify_domain(href)
        if domain is None:
            continue  # 도메인 파싱 자체가 안 되면 후보에서 제외
        is_primary = source_type is not None

        anchor_text = _truncate(link.get("text"), _MAX_ANCHOR_TEXT_CHARS)
        candidates.append({
            "source_document_id": source_document_id,
            "link_url": href,
            "resolved_link_url": None,  # 이 단계에서는 리다이렉트 해석을 시도하지 않는다(결정론적 최소 구현)
            "link_domain": domain,
            "anchor_text": anchor_text,
            "link_context": _truncate(anchor_text, _MAX_CONTEXT_CHARS),
            "candidate_source_type": source_type,
            "is_primary_candidate": is_primary,
            "resolution_method": "DETERMINISTIC_DOMAIN_ALLOWLIST",
            "resolution_status": "CANDIDATE_UNRESOLVED",
            "timestamp": now,
        })
        if len(candidates) >= _MAX_LINKS_PER_DOCUMENT:
            break

    # 1차 출처 후보만 보고한다 - 임의 외부 링크 전체를 다 저장하지 않는다(범위 제한).
    return [c for c in candidates if c["is_primary_candidate"]]
