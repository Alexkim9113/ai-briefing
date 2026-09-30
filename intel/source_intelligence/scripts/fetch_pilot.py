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

USER_AGENT = "Mozilla/5.0 (compatible; METAXIS-SourceIntel-FetchPilot/1.0; +https://github.com)"

# 섹션 67 REAL FETCH PILOT: ~6개, 실제 존재하는 안정적인 공개 URL. 카테고리를 섞는다
# (뉴스/정부/학술/공식 규제 페이지/법률/기업 뉴스룸). 이 세션에서 실제로 접속해
# 확인한 것은 아니다(sandbox 네트워크 제한) - GitHub Actions 실행 시 결과가 실제로
# 이 목록과 맞는지(리디렉션·구조 변경 등) 확인이 필요할 수 있다.
SOURCE_MATRIX = [
    {"discovery_url": "https://www.yna.co.kr/", "source_type": "NEWS_KO"},
    {"discovery_url": "https://arxiv.org/abs/2401.00001", "source_type": "ACADEMIC_ARXIV"},
    {"discovery_url": "https://www.data.go.kr/", "source_type": "GOVERNMENT_KR"},
    {"discovery_url": "https://artificialintelligenceact.eu/", "source_type": "GOVERNMENT_EU_OFFICIAL"},
    {"discovery_url": "https://www.law.go.kr/", "source_type": "LEGAL_KR"},
    {"discovery_url": "https://openai.com/news/", "source_type": "COMPANY_NEWSROOM"},
]

MAX_URLS = 6
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

        def redirect_request(self, req, fp, code, msg, headers, newurl):
            self.hops += 1
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
            if content_type and content_type != "text/html":
                return {"html": None, "content_type": content_type, "status_code": status_code,
                        "byte_size": 0, "resolved_url": resolved_url}
            raw = resp.read(MAX_BYTES + 1)
            byte_size = len(raw)
            if byte_size > MAX_BYTES:
                return {"html": None, "content_type": content_type, "status_code": status_code,
                        "byte_size": byte_size, "resolved_url": resolved_url}
            html = raw.decode("utf-8", errors="replace")
            return {"html": html, "content_type": content_type, "status_code": status_code,
                    "byte_size": byte_size, "resolved_url": resolved_url}
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


def _extract_title(html):
    """content_acquisition.acquire_content()는 status/text만 반환하고 메타데이터
    (title 등)는 버린다 - 계약을 바꾸지 않기 위해 fetch_pilot 쪽에서 별도로
    trafilatura의 메타데이터 추출을 호출한다. trafilatura 2.x는
    extract(..., with_metadata=True, output_format="json")로 metadata를 함께 내준다."""
    if not html:
        return None
    try:
        import trafilatura
    except ImportError:
        return None
    try:
        raw = trafilatura.extract(html, with_metadata=True, output_format="json",
                                   include_comments=False, include_tables=False)
        if not raw:
            return None
        meta = json.loads(raw)
        title = meta.get("title")
        return title or None
    except Exception:
        # 메타데이터 추출 실패는 본문 추출 실패와 무관하게 조용히 None으로 처리한다
        # (섹션 47: fetched content는 신뢰하지 않는 데이터).
        return None


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
            row["title"] = _extract_title(fetched.get("html"))
            row["content_status"] = acquired.get("status")
            row["extractor"] = acquired.get("extractor")
            row["extractor_version"] = acquired.get("extractor_version")
            if acquired.get("status") == "FULL_TEXT":
                text = acquired.get("text") or ""
                row["fetch_result"] = "OK"
                row["parser_result"] = "EXTRACTED"
                row["text_length"] = len(text)
                row["content_hash"] = _sha256(text)
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
