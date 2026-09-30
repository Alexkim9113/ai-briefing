# CONDITIONAL-PASS CLOSURE item 2 — article_provenance_pipeline.py end-to-end 검증.
# 실제 corpus를 백필하지 않는다(모듈 docstring 그대로) - synthetic HTML fixture로만
# 체인 전체(본문->링크->1차후보->REPORTS_ON)가 실제로 동작함을 확인한다.
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import article_provenance_pipeline as app  # noqa: E402


def _acquired_full_text(text):
    return {"status": "FULL_TEXT", "text": text, "extractor": "trafilatura",
            "extractor_version": "2.2.0"}


def test_explicit_arxiv_link_produces_reports_on_record():
    html = (
        "<html><body><article><p>New research was announced, see the paper at "
        '<a href="https://arxiv.org/abs/2401.99999">arxiv.org/abs/2401.99999</a> '
        "for full details.</p></article></body></html>"
    )
    known_documents = {
        "doc_primary_1": {"canonical_url": "https://arxiv.org/abs/2401.99999",
                           "title": "Some Paper"},
    }
    result = app.process_acquired_article(
        source_document_id="doc_news_1",
        acquired=_acquired_full_text("New research was announced, see the paper for full details."),
        html=html,
        source_url="https://news.example.com/article",
        known_documents_by_id=known_documents,
    )
    assert result["content_hash"]  # sha256 present, non-empty
    assert len(result["link_candidates"]) == 1
    assert result["link_candidates"][0]["candidate_source_type"] == "ACADEMIC_ARXIV"
    assert len(result["reports_on_records"]) == 1
    rec = result["reports_on_records"][0]
    assert rec["relation_type"] == "REPORTS_ON"
    assert rec["source_document_id"] == "doc_news_1"
    assert rec["target_document_id"] == "doc_primary_1"
    assert rec["resolution_method"] == "EXACT_URL_MATCH"
    # MINIMAL STORAGE: 반환 dict 어디에도 원문 전체 텍스트가 그대로 저장되지 않는다.
    assert "text" not in result
    for cand in result["link_candidates"]:
        assert len(cand["anchor_text"]) <= 80
        assert len(cand["link_context"]) <= 40


def test_no_primary_candidate_link_yields_zero_relationships():
    # 링크가 전혀 1차 출처로 보이지 않으면(allowlist 도메인 아님) 0건이어야 한다 -
    # "reference가 없는 경우 relation을 발명하지 않는다"(Te 원칙).
    html = (
        "<html><body><article><p>Some opinion piece with a link to "
        '<a href="https://randomblog.example.com/post">a random blog</a>.</p></article></body></html>'
    )
    result = app.process_acquired_article(
        source_document_id="doc_news_2",
        acquired=_acquired_full_text("Some opinion piece with a link to a random blog."),
        html=html,
        source_url="https://news.example.com/opinion",
        known_documents_by_id={"doc_primary_1": {"canonical_url": "https://arxiv.org/abs/2401.99999"}},
    )
    assert result["link_candidates"] == []
    assert result["reports_on_records"] == []


def test_primary_candidate_link_with_no_matching_corpus_document_yields_zero_relationships():
    # 링크는 allowlist 도메인이라 link_candidate는 생기지만(예: arxiv.org), corpus 안에
    # 그 정확한 URL을 canonical_url로 가진 document가 없으면 REPORTS_ON을 만들지 않는다
    # (있을 법하다고 추측해서 발명하지 않는다).
    html = (
        "<html><body><article><p>See "
        '<a href="https://arxiv.org/abs/9999.00000">this paper</a> for context.</p></article></body></html>'
    )
    result = app.process_acquired_article(
        source_document_id="doc_news_3",
        acquired=_acquired_full_text("See this paper for context."),
        html=html,
        source_url="https://news.example.com/x",
        known_documents_by_id={"doc_other": {"canonical_url": "https://arxiv.org/abs/1111.11111"}},
    )
    assert len(result["link_candidates"]) == 1
    assert result["reports_on_records"] == []


def test_no_known_documents_means_no_reports_on_attempted():
    html = '<html><body><p><a href="https://arxiv.org/abs/1234.56789">x</a></p></body></html>'
    result = app.process_acquired_article(
        source_document_id="doc_news_4",
        acquired=_acquired_full_text("x"),
        html=html,
        source_url="https://news.example.com/y",
        known_documents_by_id=None,
    )
    assert result["reports_on_records"] == []


def test_non_full_text_html_yields_no_candidates():
    # content_status가 FULL_TEXT/PARTIAL_TEXT가 아니면 link_provenance 자체가 빈 결과를
    # 내야 한다(기존 link_provenance.py 계약 그대로 상속) - RSS 경로(title+desc만)를
    # 흉내낸 경우 여기서 0건이 정직한 결과다.
    result = app.process_acquired_article(
        source_document_id="doc_rss_1",
        acquired={"status": "SNIPPET_ONLY", "text": None},
        html=None,
        source_url="https://news.example.com/z",
        known_documents_by_id={"doc_other": {"canonical_url": "https://arxiv.org/abs/1111.11111"}},
    )
    assert result["link_candidates"] == []
    assert result["reports_on_records"] == []
    assert result["content_hash"] is None
