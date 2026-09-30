# SOURCE INTELLIGENCE remediation — Phase C: link_provenance.py는 실제 네트워크로
# 검증되지 않았다(이 sandbox는 outbound 차단). 여기 fixture는 실제 GitHub Actions
# fetch pilot이 받아온 4건(yna.co.kr/arxiv.org/data.go.kr/artificialintelligenceact.eu)의
# 실제 HTML을 이 세션이 갖고 있지 않으므로, 그 페이지들의 알려진 실제 구조(정부/학술
# 사이트가 흔히 갖는 헤더/푸터 링크 형태)를 본뜬 합성(synthetic) HTML로만 검증한다.
# 이 사실을 최종 보고서에도 명시한다 - "실제 HTML로 검증했다"고 하지 않는다.
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import link_provenance as lp  # noqa: E402

SYNTHETIC_GOV_HTML = """
<html><body>
<article>
  <h1>AI 정책 발표</h1>
  <p>정부는 오늘 <a href="https://www.data.go.kr/data/notice/1">관련 공고</a>를 냈다.</p>
  <p>원문은 <a href="https://www.law.go.kr/lsInfoP.do?lsId=1234">법령정보센터</a>에서 확인 가능하다.</p>
  <p>참고 논문은 <a href="https://arxiv.org/abs/2401.00001">arXiv 2401.00001</a>이다.</p>
  <p>이 기사도 참고: <a href="https://doi.org/10.1000/xyz123">DOI 링크</a></p>
</article>
<footer>
  <a href="/privacy">개인정보처리방침</a>
  <a href="https://ads.example-tracker.com/click?id=1">광고</a>
  <a href="mailto:tip@example.com">제보</a>
  <a href="#top">맨위로</a>
</footer>
</body></html>
"""


def test_returns_empty_when_html_missing():
    assert lp.extract_link_provenance_candidates("doc1", None, "FULL_TEXT") == []


def test_returns_empty_when_content_status_not_full_or_partial():
    # SNIPPET_ONLY(현재 RSS 기본값)에서는 절대 provenance를 만들지 않는다 - 이게
    # 이 모듈이 "forward-looking"이고 백필이 아니라는 것의 실제 강제 지점이다.
    assert lp.extract_link_provenance_candidates("doc1", SYNTHETIC_GOV_HTML, "SNIPPET_ONLY") == []
    assert lp.extract_link_provenance_candidates("doc1", SYNTHETIC_GOV_HTML, "UNKNOWN") == []


def test_only_primary_domain_allowlist_links_kept():
    candidates = lp.extract_link_provenance_candidates("doc1", SYNTHETIC_GOV_HTML, "FULL_TEXT")
    domains = {c["link_domain"] for c in candidates}
    # 정부/학술/DOI 도메인만 후보로 남아야 한다 - 광고 트래커, 상대경로, mailto, #anchor는 전부 제외.
    assert domains == {"www.data.go.kr", "www.law.go.kr", "arxiv.org", "doi.org"}
    assert all(c["is_primary_candidate"] for c in candidates)
    for c in candidates:
        assert "ads.example-tracker.com" not in c["link_url"]


def test_all_required_fields_present_and_deterministic():
    candidates = lp.extract_link_provenance_candidates("doc1", SYNTHETIC_GOV_HTML, "PARTIAL_TEXT")
    assert len(candidates) == 4
    required_fields = ("source_document_id", "link_url", "resolved_link_url", "link_domain",
                        "anchor_text", "link_context", "candidate_source_type",
                        "is_primary_candidate", "resolution_method", "resolution_status",
                        "timestamp")
    for c in candidates:
        for f in required_fields:
            assert f in c
        assert c["source_document_id"] == "doc1"
        assert c["resolution_method"] == "DETERMINISTIC_DOMAIN_ALLOWLIST"
        assert c["resolution_status"] == "CANDIDATE_UNRESOLVED"


def test_anchor_text_never_stores_full_sentence():
    # 저작권 경계: 앵커 텍스트는 짧은 라벨만 - 긴 문장이 들어와도 잘려야 한다.
    long_anchor_html = (
        '<html><body><article><p>'
        '<a href="https://arxiv.org/abs/9999.00001">' + ("이것은 매우 긴 앵커 텍스트 문장입니다 " * 10) +
        '</a></p></article></body></html>'
    )
    candidates = lp.extract_link_provenance_candidates("doc2", long_anchor_html, "FULL_TEXT")
    assert len(candidates) == 1
    assert len(candidates[0]["anchor_text"]) <= lp._MAX_ANCHOR_TEXT_CHARS + 1  # +1 for ellipsis char


def test_non_primary_domains_excluded_entirely():
    html = '<html><body><a href="https://random-blog.example.com/post">random</a></body></html>'
    candidates = lp.extract_link_provenance_candidates("doc3", html, "FULL_TEXT")
    assert candidates == []


def test_max_links_per_document_cap():
    many_links = "".join(
        f'<a href="https://arxiv.org/abs/{i}.00001">paper {i}</a>' for i in range(50)
    )
    html = f"<html><body>{many_links}</body></html>"
    candidates = lp.extract_link_provenance_candidates("doc4", html, "FULL_TEXT")
    assert len(candidates) <= lp._MAX_LINKS_PER_DOCUMENT


def test_malformed_html_does_not_raise():
    # 신뢰하지 않는 데이터(fetched HTML)가 깨져 있어도 예외를 던지지 않고 빈 결과.
    broken = "<html><body><a href='https://arxiv.org/abs/1'>unterminated"
    candidates = lp.extract_link_provenance_candidates("doc5", broken, "FULL_TEXT")
    assert isinstance(candidates, list)  # 예외 없이 리스트 반환(내용은 파서 관용성에 따라 다를 수 있음)
