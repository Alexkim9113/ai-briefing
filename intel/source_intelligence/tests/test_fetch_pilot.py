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


def test_run_never_exceeds_max_urls():
    # CONDITIONAL-PASS CLOSURE item 1: MAX_URLS는 6->12로 늘었다(개별 문서 URL 매트릭스
    # 확장, 12개 카테고리 커버리지 요구사항). 이 테스트는 여전히 "cap이 실제로 걸리는지"만
    # 검증한다 - 하드코드된 6 대신 fp.MAX_URLS를 그대로 참조해 cap 값이 바뀌어도
    # 테스트 자체의 의도(무한정 crawl 금지)는 그대로 유지한다.
    calls = []

    def fake_fetcher(url):
        calls.append(url)
        return {"html": "<html><body>" + ("word " * 300) + "</body></html>",
                "content_type": "text/html", "status_code": 200, "byte_size": 1000,
                "resolved_url": url}

    matrix = [{"discovery_url": f"https://example.com/{i}", "source_type": "TEST"} for i in range(30)]
    results = fp.run(source_matrix=matrix, fetcher=fake_fetcher)
    assert len(results) <= fp.MAX_URLS
    assert len(calls) <= fp.MAX_URLS


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


def test_nav_heavy_fake_page_flagged_low_quality():
    # 합성 fixture: nav/footer/cookie-banner 스타일의 짧은 줄이 대부분인 가짜 페이지.
    # trafilatura가 뭔가를 뽑아내더라도(길이만으로는 FULL_TEXT 임계값을 넘을 수 있음)
    # title이 없거나 짧은 줄 비율이 높으면 LOW_QUALITY_EXTRACTION으로 플래그돼야 한다.
    nav_text = "\n".join(["Home"] * 60 + ["About"] * 60 + ["Cookie Policy"] * 60 + ["Contact"] * 60)
    assert fp.assess_full_text_quality(nav_text, None) == "LOW_QUALITY_EXTRACTION"
    assert fp.assess_full_text_quality(nav_text, "Some Title") == "LOW_QUALITY_EXTRACTION"


def test_clean_article_like_page_is_ok_quality():
    # 합성 fixture: 문장 단위의 긴 줄로 구성된 "진짜 기사 같은" 본문 + title 존재.
    sentence = "This is a full sentence that reads like real article body content about a topic."
    clean_text = "\n".join([sentence] * 20)
    assert fp.assess_full_text_quality(clean_text, "A Real Article Title") == "OK"


def test_quality_flag_and_new_fields_present_on_full_text_row():
    body = "".join(
        f"<p>This is paragraph number {i} of real article body content, discussing point {i} at some length.</p>"
        for i in range(15)
    )
    fake_html = (
        "<html><head><title>Real Article Title</title></head><body>"
        f"<article><h1>Real Article Title</h1>{body}"
        '<p>See also <a href="https://arxiv.org/abs/1234.56789">a paper</a> for details.</p>'
        "</article></body></html>"
    )

    def fake_fetcher(url):
        return {"html": fake_html, "content_type": "text/html", "status_code": 200,
                "byte_size": len(fake_html), "resolved_url": url}

    results = fp.run(source_matrix=[{"discovery_url": "https://example.com/article", "source_type": "TEST"}],
                      fetcher=fake_fetcher)
    row = results[0]
    assert row["fetch_result"] == "OK"
    assert row["quality_flag"] == "OK"
    assert row["outbound_link_count"] >= 1
    assert row["primary_candidate_link_count"] >= 1  # arxiv.org is on the allowlist
    for field in ("author", "publication_date", "language", "redirect_chain"):
        assert field in row


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
