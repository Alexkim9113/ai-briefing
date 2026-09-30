# SOURCE INTELLIGENCE remediation (item 6) — fetch_pilot.py 보안 가드는 네트워크 없이도
# 검증 가능한 부분(URL 스킴/호스트 차단, MAX_URLS cap)만 테스트한다. 실제 네트워크
# 호출 자체는 이 sandbox에서 검증 불가(GAP으로 최종 보고서에 명시).
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))
sys.path.insert(0, str(PKG_DIR / "scripts"))

import fetch_pilot as fp  # noqa: E402


def test_file_scheme_is_blocked():
    try:
        fp._validate_url("file:///etc/passwd")
        assert False, "file: scheme must be blocked"
    except fp._BlockedURLError:
        pass


def test_javascript_scheme_is_blocked():
    try:
        fp._validate_url("javascript:alert(1)")
        assert False, "javascript: scheme must be blocked"
    except fp._BlockedURLError:
        pass


def test_data_scheme_is_blocked():
    try:
        fp._validate_url("data:text/html,<script>1</script>")
        assert False, "data: scheme must be blocked"
    except fp._BlockedURLError:
        pass


def test_localhost_is_blocked():
    try:
        fp._validate_url("http://localhost/")
        assert False, "localhost must be blocked"
    except fp._BlockedURLError:
        pass


def test_loopback_ip_is_blocked():
    try:
        fp._validate_url("http://127.0.0.1/")
        assert False, "loopback IP must be blocked"
    except fp._BlockedURLError:
        pass


def test_normal_https_url_passes_validation():
    u = fp._validate_url("https://example.com/page")
    assert u.hostname == "example.com"


def test_run_never_exceeds_six_urls():
    calls = []

    def fake_fetcher(url):
        calls.append(url)
        return {"html": "<html><body>" + ("word " * 300) + "</body></html>",
                "content_type": "text/html", "status_code": 200, "byte_size": 1000,
                "resolved_url": url}

    matrix = [{"discovery_url": f"https://example.com/{i}", "source_type": "TEST"} for i in range(20)]
    results = fp.run(source_matrix=matrix, fetcher=fake_fetcher)
    assert len(results) <= 6
    assert len(calls) <= 6


def test_full_field_set_present_on_success():
    def fake_fetcher(url):
        return {"html": "<html><body>" + ("word " * 300) + "</body></html>",
                "content_type": "text/html", "status_code": 200, "byte_size": 1000,
                "resolved_url": url}

    results = fp.run(source_matrix=[{"discovery_url": "https://example.com/x", "source_type": "TEST"}],
                      fetcher=fake_fetcher)
    row = results[0]
    for field in ("discovery_url", "resolved_url", "canonical_url", "source_type", "http_status",
                  "fetch_result", "parser_result", "text_length", "title", "content_status",
                  "failure_reason", "extractor", "extractor_version", "content_hash", "timestamp"):
        assert field in row
    assert row["fetch_result"] == "OK"
    assert row["content_hash"]  # sha256 present


def test_http_status_and_title_captured_on_success():
    # 버그 재현/수정 검증: real_fetcher가 반환하는 status_code/resolved_url과
    # trafilatura 메타데이터의 title이 최종 row에 전파되어야 한다(과거엔 항상 null).
    fake_html = (
        "<html><head><title>테스트 기사 제목입니다</title></head><body>"
        "<article><h1>테스트 기사 제목입니다</h1><p>" + ("실제 기사 본문 내용. " * 40) +
        "</p></article></body></html>"
    )

    def fake_fetcher(url):
        return {"html": fake_html, "content_type": "text/html", "status_code": 200,
                "byte_size": len(fake_html), "resolved_url": url + "?resolved"}

    results = fp.run(source_matrix=[{"discovery_url": "https://example.com/article", "source_type": "TEST"}],
                      fetcher=fake_fetcher)
    row = results[0]
    assert row["fetch_result"] == "OK"
    assert row["http_status"] == 200
    assert row["resolved_url"] == "https://example.com/article?resolved"
    assert row["title"] == "테스트 기사 제목입니다"


def test_http_status_captured_on_failure():
    # BLOCKED/FETCH_FAILED 경로에서도 http_status는 여전히 채워져야 한다(title은 없어도 된다).
    def fake_fetcher(url):
        return {"html": None, "content_type": None, "status_code": 403, "byte_size": 0,
                "resolved_url": url}

    results = fp.run(source_matrix=[{"discovery_url": "https://example.com/blocked", "source_type": "TEST"}],
                      fetcher=fake_fetcher)
    row = results[0]
    assert row["content_status"] == "BLOCKED"
    assert row["http_status"] == 403
    assert row["title"] is None
