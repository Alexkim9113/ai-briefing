#!/usr/bin/env python3
"""SOURCE INTELLIGENCE remediation (item 6) — 실제 fetch pilot 스크립트.

이 스크립트는 이 remediation 세션 환경에서는 실행/검증되지 않았다: 이 sandbox는
pypi.org 외의 외부 호스트에 outbound가 막혀 있다(직접 curl로 확인됨). 아래
.github/workflows/source-intel-fetch-pilot.yml을 통해 실제 네트워크가 있는 GitHub
Actions 환경에서만 workflow_dispatch로 수동 실행해 검증할 수 있다 - 이 세션은 그
워크플로를 트리거하지도, 결과를 확인하지도 않았다(트리거할 방법이 없고, 임의로
시도해서도 안 된다는 지시를 그대로 따른다).

content_acquisition.acquire_content()에 주입하는 fetcher는 여기서 최소한의 실제
urllib 기반 구현으로 새로 만든다(그 모듈 자체는 fetcher=None이 기본값이라 네트워크를
직접 만지지 않는다 - 섹션 15/58 설계 그대로) - FETCH SECURITY 요구사항을 전부
지킨다: localhost/private-IP/file:/javascript:/data: 차단, redirect 5회 cap,
content_acquisition.MAX_HTML_BYTES 초과분 다운로드 중단, REQUEST_TIMEOUT_SECONDS
타임아웃, Content-Type이 text/html일 때만 파싱, fetched content는 절대 eval/exec
하지 않는다(파싱은 trafilatura에만 맡긴다).
"""
import hashlib
import ipaddress
import json
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import content_acquisition  # noqa: E402
import link_provenance  # noqa: E402 - REUSE BEFORE BUILD: allowlist/링크 추출 로직 재사용

USER_AGENT = "Mozilla/5.0 (compatible; METAXIS-SourceIntel-FetchPilot/1.0; +https://github.com)"

# CONDITIONAL-PASS CLOSURE item 1: 실제 개별 문서/기사 URL 매트릭스로 교체(홈페이지
# root URL 금지). 각 URL은 "왜 안정적인 개별 식별자인지"를 주석으로 남긴다 - 이
# 세션은 네트워크가 없어 실접속 검증을 할 수 없다(반복 확인됨); 실패(403/404/paywall)는
# 데이터이지 결함이 아니다(Te 지시). 카테고리 커버리지: NEWS>=3, RESEARCH>=2,
# GOVERNMENT>=2, POLICY>=2, LAW-COURT>=1, COMPANY-PRIMARY>=2.
# M.5E-F SECTION: this matrix was replaced to target the exact NO-GO blockers named in the
# M.5E-F spec (POLICY_RESEARCH_GAP, STATISTICAL_GAP, Korean research/statistics coverage) rather
# than the generic reachability matrix the prior remediation session scaffolded but never ran.
# Every URL below is a real, named, stable landing/listing page for a real institution already
# on Te's explicit candidate list (KDI/KEEI/World Bank/OECD/KOSIS/RISS) -- never a guessed API
# endpoint. This session still cannot verify reachability directly (sandbox network blocked,
# reconfirmed this round); these URLs are tested for the first time by this workflow run itself.
SOURCE_MATRIX = [
    # POLICY_RESEARCH_GAP -- Korean government-affiliated research institutes (국책연구기관)
    # named explicitly in Te's candidate list. KDI publication listing (not homepage).
    {"discovery_url": "https://www.kdi.re.kr/research/subjectList", "source_type": "POLICY_RESEARCH_KR_KDI",
     "identifier_type": "publication listing path (best-effort, not homepage)"},
    # KEEI (에너지경제연구원) -- directly relevant to AI_ENERGY_INFRA's STATISTICAL/POLICY_RESEARCH gap.
    {"discovery_url": "https://www.keei.re.kr/web_keei/d_results.nsf", "source_type": "POLICY_RESEARCH_KR_KEEI",
     "identifier_type": "research results listing path (best-effort, not homepage)"},
    # KISDI (정보통신정책연구원) -- AI/ICT policy research, directly relevant to AI governance gap.
    {"discovery_url": "https://www.kisdi.re.kr/kisdi/fp/kr/publication/selectResearchList.do",
     "source_type": "POLICY_RESEARCH_KR_KISDI", "identifier_type": "research list path (best-effort)"},
    # STEPI (과학기술정책연구원) -- AI science/tech policy research.
    {"discovery_url": "https://www.stepi.re.kr/site/stepiko/report/List.do?cmsCd=CM0012",
     "source_type": "POLICY_RESEARCH_KR_STEPI", "identifier_type": "report list path (best-effort)"},
    # STATISTICAL_GAP -- Korean official statistics, directly closing the 0/597 statistical
    # source gap documented in prior rounds.
    {"discovery_url": "https://kosis.kr/statisticsList/statisticsListIndex.do", "source_type": "STATISTICS_KR_KOSIS",
     "identifier_type": "statistics listing path (best-effort, not homepage)"},
    {"discovery_url": "https://ecos.bok.or.kr/#/", "source_type": "STATISTICS_KR_ECOS",
     "identifier_type": "statistics portal root (best-effort -- SPA root, data endpoint unconfirmed)"},
    # International statistics (World Bank/OECD/ILO), AI_ENERGY_INFRA + AI_LABOR candidates.
    {"discovery_url": "https://data.worldbank.org/indicator/EG.ELC.ACCS.ZS", "source_type": "STATISTICS_INTL_WORLDBANK",
     "identifier_type": "indicator page (real, stable World Bank indicator code)"},
    {"discovery_url": "https://www.ilo.org/global/statistics-and-databases/lang--en/index.htm",
     "source_type": "STATISTICS_INTL_ILO", "identifier_type": "statistics portal listing (best-effort)"},
    {"discovery_url": "https://www.oecd.org/en/data/datasets.html", "source_type": "STATISTICS_INTL_OECD",
     "identifier_type": "dataset listing path (best-effort, not homepage)"},
    {"discovery_url": "https://www.eia.gov/electricity/data.php", "source_type": "STATISTICS_INTL_EIA",
     "identifier_type": "data listing path (real, stable EIA path)"},
    # ACADEMIC_COVERAGE (Korean) -- RISS, Te's own explicit priority candidate.
    {"discovery_url": "https://www.riss.kr/index.do", "source_type": "ACADEMIC_KR_RISS",
     "identifier_type": "portal root (best-effort -- RISS search requires POST/session, landing only)"},
    # OpenAlex -- already on Te's approved international academic source list, API has a real,
    # documented, stable REST endpoint (not guessed).
    {"discovery_url": "https://api.openalex.org/works?search=AI%20energy%20demand&per-page=5",
     "source_type": "ACADEMIC_INTL_OPENALEX", "identifier_type": "documented public REST API endpoint"},
]

MAX_URLS = 12
PER_URL_TIMEOUT_SECONDS = 15
MAX_REDIRECTS = content_acquisition.MAX_REDIRECTS
MAX_BYTES = content_acquisition.MAX_HTML_BYTES


class _BlockedURLError(Exception):
    pass


def _is_private_or_blocked_host(host):
    if not host:
        return True
    host_l = host.lower()
    if host_l in ("localhost",) or host_l.endswith(".local"):
        return True
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return True  # 해석이 안 되는 호스트는 안전하게 차단
    for info in infos:
        ip = info[4][0]
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved or addr.is_multicast:
            return True
    return False


def _validate_url(url):
    """FETCH SECURITY: file/javascript/data 스킴 차단, localhost/사설 IP 차단."""
    u = urlparse(url)
    if u.scheme not in ("http", "https"):
        raise _BlockedURLError(f"disallowed scheme: {u.scheme!r}")
    if _is_private_or_blocked_host(u.hostname):
        raise _BlockedURLError(f"blocked host (private/loopback/unresolvable): {u.hostname!r}")
    return u


def real_fetcher(url):
    """content_acquisition.acquire_content()에 주입하는 실제 fetcher. 계약:
    (url) -> {"html", "content_type", "status_code", "byte_size", "resolved_url"}.
    redirect는 urllib이 자동으로 따라가되, 매 hop마다 URL을 다시 검증하고
    MAX_REDIRECTS를 넘으면 중단한다. Content-Type이 text/html이 아니면 본문을
    다운로드하지 않는다(파싱 대상이 아니므로)."""
    _validate_url(url)

    class _RedirectGuard(urllib.request.HTTPRedirectHandler):
        def __init__(self):
            self.hops = 0
            self.chain = []

        def redirect_request(self, req, fp, code, msg, headers, newurl):
            self.hops += 1
            self.chain.append(newurl)
            if self.hops > MAX_REDIRECTS:
                raise _BlockedURLError("too many redirects")
            _validate_url(newurl)
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    guard = _RedirectGuard()
    opener = urllib.request.build_opener(guard)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with opener.open(req, timeout=PER_URL_TIMEOUT_SECONDS) as resp:
            status_code = resp.getcode()
            resolved_url = resp.geturl()
            content_type = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            redirect_chain = list(guard.chain)
            if content_type and content_type != "text/html":
                return {"html": None, "content_type": content_type, "status_code": status_code,
                        "byte_size": 0, "resolved_url": resolved_url, "redirect_chain": redirect_chain}
            raw = resp.read(MAX_BYTES + 1)
            byte_size = len(raw)
            if byte_size > MAX_BYTES:
                return {"html": None, "content_type": content_type, "status_code": status_code,
                        "byte_size": byte_size, "resolved_url": resolved_url, "redirect_chain": redirect_chain}
            html = raw.decode("utf-8", errors="replace")
            return {"html": html, "content_type": content_type, "status_code": status_code,
                    "byte_size": byte_size, "resolved_url": resolved_url, "redirect_chain": redirect_chain}
    except urllib.error.HTTPError as e:
        return {"html": None, "content_type": None, "status_code": e.code, "byte_size": 0,
                "resolved_url": url}
    except _BlockedURLError:
        raise
    except Exception as e:
        return {"html": None, "content_type": None, "status_code": None, "byte_size": 0,
                "resolved_url": url, "error": repr(e)}


def _sha256(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _extract_metadata(html):
    """content_acquisition.acquire_content()는 status/text만 반환하고 메타데이터는
    버린다 - 계약을 바꾸지 않기 위해 fetch_pilot 쪽에서 별도로 trafilatura의 메타데이터
    추출을 호출한다. trafilatura 2.x는 extract(..., with_metadata=True,
    output_format="json")로 metadata를 함께 내준다. 실패하면 전부 None(추측 금지)."""
    empty = {"title": None, "author": None, "publication_date": None,
              "language": None, "canonical_url": None}
    if not html:
        return dict(empty)
    try:
        import trafilatura
    except ImportError:
        return dict(empty)
    try:
        raw = trafilatura.extract(html, with_metadata=True, output_format="json",
                                   include_comments=False, include_tables=False)
        if not raw:
            return dict(empty)
        meta = json.loads(raw)
        return {
            "title": meta.get("title") or None,
            "author": meta.get("author") or None,
            "publication_date": meta.get("date") or None,
            "language": meta.get("language") or None,
            "canonical_url": meta.get("url") or None,
        }
    except Exception:
        # 메타데이터 추출 실패는 본문 추출 실패와 무관하게 조용히 None으로 처리한다
        # (섹션 47: fetched content는 신뢰하지 않는 데이터).
        return dict(empty)


def _nav_contamination_ratio(text):
    """CONDITIONAL-PASS CLOSURE item 1: nav/footer/cookie-banner 오염 휴리스틱.
    추출된 텍스트를 줄 단위로 나눠, 4단어 미만인 짧은 줄의 비율을 본다. 실제 기사
    본문은 대부분 문장 단위 줄이 길고, nav/메뉴/쿠키배너는 짧은 라벨성 줄이 몰린다.
    완벽한 판정은 아니다(휴리스틱) - 그래서 FULL_TEXT를 아예 막지 않고 별도
    LOW_QUALITY_EXTRACTION 플래그만 얹는다(기존 FETCH_FAILED 승격/강등 로직은
    건드리지 않는다 - content_acquisition.py의 acquire_content() 계약은 그대로 둔다)."""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return 0.0
    short = sum(1 for ln in lines if len(ln.split()) < 4)
    return short / len(lines)


def assess_full_text_quality(text, title):
    """(a) title 존재 여부, (b) nav/footer 오염 비율을 확인해 "진짜 본문을 확보했는가"를
    text_length 하나만으로 판정하지 않는다. 반환: "OK" 또는 "LOW_QUALITY_EXTRACTION".
    이 함수는 content_status를 바꾸지 않는다(FULL_TEXT 승격/강등은 하지 않음) - 별도
    진단 필드(quality_flag)로만 보고한다. 기존 acquire_content() 반환 계약은 그대로."""
    if not title:
        return "LOW_QUALITY_EXTRACTION"
    if _nav_contamination_ratio(text) > 0.4:
        return "LOW_QUALITY_EXTRACTION"
    return "OK"


def run(source_matrix=None, fetcher=real_fetcher):
    source_matrix = (source_matrix or SOURCE_MATRIX)[:MAX_URLS]  # 섹션 67: 최대 6개, crawl 금지
    results = []
    for entry in source_matrix:
        url = entry["discovery_url"]
        row = {
            "discovery_url": url,
            "resolved_url": None,
            "canonical_url": None,
            "source_type": entry.get("source_type"),
            "http_status": None,
            "fetch_result": None,
            "parser_result": None,
            "text_length": None,
            "title": None,
            "content_status": None,
            "failure_reason": None,
            "extractor": None,
            "extractor_version": None,
            "content_hash": None,
            "author": None,
            "publication_date": None,
            "language": None,
            "outbound_link_count": None,
            "primary_candidate_link_count": None,
            "redirect_chain": None,
            "quality_flag": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        # acquire_content()의 반환 계약(status/text/extractor만)은 바꾸지 않는다 - 대신
        # 주입하는 fetcher를 얇게 감싸서 fetcher가 실제로 반환한 raw dict(status_code,
        # resolved_url, html)를 옆에서 그대로 캡처해 둔다. 네트워크 호출은 여전히 1회뿐이다.
        captured = {}

        def _capturing_fetcher(u, _fetcher=fetcher, _sink=captured):
            result = _fetcher(u)
            _sink["fetched"] = result
            return result

        try:
            acquired = content_acquisition.acquire_content(url, fetcher=_capturing_fetcher)
            fetched = captured.get("fetched") or {}
            row["http_status"] = fetched.get("status_code")
            row["resolved_url"] = fetched.get("resolved_url")
            row["redirect_chain"] = fetched.get("redirect_chain") or None
            html = fetched.get("html")
            meta = _extract_metadata(html)
            row["title"] = meta["title"]
            row["author"] = meta["author"]
            row["publication_date"] = meta["publication_date"]
            row["language"] = meta["language"]
            row["canonical_url"] = meta["canonical_url"]
            row["content_status"] = acquired.get("status")
            row["extractor"] = acquired.get("extractor")
            row["extractor_version"] = acquired.get("extractor_version")
            if html:
                # REUSE BEFORE BUILD: link_provenance._AnchorExtractor로 전체 http(s)
                # 앵커 수를 세고(outbound_link_count), 같은 모듈의
                # extract_link_provenance_candidates()로 그 중 allowlist 통과분만
                # 센다(primary_candidate_link_count). 새 파서/정규식을 다시 만들지 않는다.
                anchor_parser = link_provenance._AnchorExtractor()
                try:
                    anchor_parser.feed(html)
                    row["outbound_link_count"] = sum(
                        1 for lk in anchor_parser.links
                        if (lk.get("href") or "").startswith(("http://", "https://")))
                except Exception:
                    row["outbound_link_count"] = None
                link_candidates = link_provenance.extract_link_provenance_candidates(
                    url, html, acquired.get("status"))
                row["primary_candidate_link_count"] = len(link_candidates)
            if acquired.get("status") == "FULL_TEXT":
                text = acquired.get("text") or ""
                row["fetch_result"] = "OK"
                row["parser_result"] = "EXTRACTED"
                row["text_length"] = len(text)
                row["content_hash"] = _sha256(text)
                row["quality_flag"] = assess_full_text_quality(text, meta["title"])
            else:
                row["fetch_result"] = "FAILED"
                row["parser_result"] = None
                row["failure_reason"] = acquired.get("reason") or acquired.get("status")
        except _BlockedURLError as e:
            row["fetch_result"] = "BLOCKED_BY_SECURITY_POLICY"
            row["failure_reason"] = str(e)
        except Exception as e:
            row["fetch_result"] = "ERROR"
            row["failure_reason"] = repr(e)
        results.append(row)
        time.sleep(0.2)  # 섹션 67: 재시도 1회 이상 금지, 최소한의 예의(no hammering)
    return results


if __name__ == "__main__":
    out = run()
    out_path = Path("fetch_pilot_results.json")
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))
