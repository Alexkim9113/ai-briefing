# PRODUCTION EVIDENCE SUPPLY v1.0 — SUBSTEP B (섹션 11-14). Google News redirect URL
# (news.google.com/rss/articles/CBMi...)을 실제 목적지/발행사 URL로 해석한다.
#
# 원칙(섹션 11-14, 절대 규칙):
#   - LLM/추측 금지. 실패하면 resolution_status="UNRESOLVED"로 남기고 절대 목적지를 지어내지 않는다.
#   - 같은 URL을 두 번 다시 해석하지 않는다 — redirect_url_hash 키로 캐시.
#   - discovery_source(예: GOOGLE_NEWS) / actual_source(예: REUTERS) / primary_source(예: EU_COMMISSION)
#     세 가지는 서로 다른 개념이며 이 모듈은 그중 discovery_source→actual_source만 다룬다
#     (primary_source 판정은 evidence_supply.source_registry의 몫).
#   - 네트워크 접근 함수는 주입 가능해야 한다(fetcher) — 이 세션 환경은 news.google.com에 대한
#     outbound HTTPS를 조직 프록시 정책으로 차단하므로(curl 실측: CONNECT tunnel failed, 403),
#     이 모듈은 실제 네트워크 없이도 단위 테스트가 가능해야 하고, 운영 배포(GitHub Actions
#     daily.yml 등, 이미 RSS/DeepL/Gemini를 정상 호출하는 환경) 에서 실제 fetcher로 검증되어야
#     한다 — 이 세션 안에서 실제 라이브 해석 결과를 보장할 수 없다는 사실을 감추지 않는다.
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
REDIRECT_CACHE_PATH = HERE / "redirect_cache.json"

RESOLUTION_METHODS = (
    "REDIRECT_METADATA",   # 기존 아이템에 이미 실제 링크가 붙어있던 경우
    "HTTP_REDIRECT",       # 실제 HTTP 302/301 체인을 따라간 최종 URL
    "CANONICAL_LINK",      # 응답 HTML의 <link rel=canonical>
    "PUBLISHER_METADATA",  # og:url 등 발행사 임베디드 메타데이터
    "STRUCTURED_METADATA", # JSON-LD 등 구조화 메타데이터
    "GOOGLE_NEWS_DECODE",  # 알려진 구글 뉴스 해석 메커니즘(리버스엔지니어링 아님, 공개된 방식만)
)
RESOLUTION_STATUSES = ("RESOLVED", "UNRESOLVED")

_GOOGLE_NEWS_HOSTS = {"news.google.com"}


def is_google_news_redirect(url):
    if not url:
        return False
    try:
        return urlparse(url).netloc.lower().lstrip("www.") in _GOOGLE_NEWS_HOSTS
    except Exception:
        return False


def redirect_url_hash(url):
    return hashlib.sha256((url or "").strip().encode("utf-8")).hexdigest()[:24]


def _domain_of(url):
    if not url:
        return None
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc[4:] if netloc.startswith("www.") else netloc
    except Exception:
        return None


def _load_cache():
    if not REDIRECT_CACHE_PATH.exists():
        return {}
    try:
        with open(REDIRECT_CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache):
    with open(REDIRECT_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")


def _from_redirect_metadata(item):
    """섹션 13 우선순위 1: RSS 아이템에 이미 실제 발행사 링크가 별도 필드로 들어있는 경우
    (예: 일부 Google News RSS entry는 <source url="..."> 를 제공한다). 이 세션에서는
    이런 부가 필드가 실제로 채워져 있는지 아직 확인되지 않았으므로, 존재할 때만 쓰고
    없으면 다음 단계로 넘어간다 — 추측하지 않는다."""
    return item.get("resolved_url") or item.get("source_url") or None


_CANONICAL_RE = re.compile(
    r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', re.I
)
_OG_URL_RE = re.compile(
    r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']', re.I
)


def _from_html(html):
    if not html:
        return None, None
    m = _CANONICAL_RE.search(html)
    if m:
        return m.group(1), "CANONICAL_LINK"
    m = _OG_URL_RE.search(html)
    if m:
        return m.group(1), "PUBLISHER_METADATA"
    return None, None


def resolve_google_news_url(google_news_url, item=None, fetcher=None, use_cache=True):
    """google_news_url을 실제 목적지 URL로 해석한다.

    fetcher: (url) -> {"final_url": str|None, "html": str|None} 형태를 반환하는 주입 가능한
    함수. 기본값(None)이면 실제 네트워크를 시도하지 않고 UNRESOLVED를 반환한다 — 이 모듈은
    스스로 네트워크 계층을 갖지 않는다(운영 환경에서 실제 HTTP 구현을 주입해서 쓴다).
    실패 시 절대 목적지를 추측하지 않고 resolution_status=UNRESOLVED로만 남긴다(섹션 11).
    """
    item = item or {}
    h = redirect_url_hash(google_news_url)
    cache = _load_cache() if use_cache else {}
    if use_cache and h in cache:
        return cache[h]

    result = {
        "redirect_url_hash": h,
        "discovery_url": google_news_url,
        "discovery_source": "GOOGLE_NEWS",
        "resolved_url": None,
        "canonical_url": None,
        "resolved_domain": None,
        "resolution_method": None,
        "resolution_status": "UNRESOLVED",
    }

    metadata_url = _from_redirect_metadata(item)
    if metadata_url:
        result.update(
            resolved_url=metadata_url,
            canonical_url=metadata_url,
            resolved_domain=_domain_of(metadata_url),
            resolution_method="REDIRECT_METADATA",
            resolution_status="RESOLVED",
        )
    elif fetcher is not None:
        try:
            fetched = fetcher(google_news_url) or {}
        except Exception:
            fetched = {}
        final_url = fetched.get("final_url")
        if final_url and _domain_of(final_url) not in (None,) and not is_google_news_redirect(final_url):
            result.update(
                resolved_url=final_url,
                canonical_url=final_url,
                resolved_domain=_domain_of(final_url),
                resolution_method="HTTP_REDIRECT",
                resolution_status="RESOLVED",
            )
        else:
            html_url, method = _from_html(fetched.get("html"))
            if html_url:
                result.update(
                    resolved_url=html_url,
                    canonical_url=html_url,
                    resolved_domain=_domain_of(html_url),
                    resolution_method=method,
                    resolution_status="RESOLVED",
                )
    # fetcher가 없거나 모든 경로가 실패하면 UNRESOLVED 그대로 둔다 — 추측 금지.

    assert result["resolution_status"] in RESOLUTION_STATUSES
    if result["resolution_method"] is not None:
        assert result["resolution_method"] in RESOLUTION_METHODS

    if use_cache:
        cache[h] = result
        _save_cache(cache)
    return result
