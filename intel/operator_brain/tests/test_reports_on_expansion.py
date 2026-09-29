# SOURCE INTELLIGENCE remediation (item 5) — REPORTS_ON 확장: NEWS -> COMPANY/GOVERNMENT
# PRIMARY. EXACT URL / EXACT canonical title match만 쓰고 LLM/퍼지매칭은 전혀 안 쓴다.
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import reports_on_expansion as roe  # noqa: E402
import source_independence as si  # noqa: E402


def test_is_primary_candidate_only_for_allowlisted_or_gov_domain():
    assert roe.is_primary_candidate("https://openai.com/index/foo") == "COMPANY_PRIMARY"
    assert roe.is_primary_candidate("https://www.moef.go.kr/notice/1") == "GOVERNMENT_PRIMARY"
    assert roe.is_primary_candidate("https://random-blog.example.com/post") is None
    assert roe.is_primary_candidate("") is None


def test_relationship_record_has_full_schema():
    rec = roe.build_relationship_record(
        "doc_secondary", "doc_primary", "EXPLICIT_URL_MATCH", 0.95,
        "https://openai.com/index/foo", "https://news.example.com/a",
        "https://openai.com/index/foo", "2026-09-29T00:00:00+00:00",
    )
    for field in roe.RELATIONSHIP_RECORD_FIELDS:
        assert field in rec
    assert rec["relation_type"] == "REPORTS_ON"


def test_explicit_url_match_resolves_news_to_company_primary():
    documents_by_id = {
        "doc_primary": {"document_id": "doc_primary", "canonical_url": "https://openai.com/index/foo",
                         "title": "How we will do better for Australia", "updated_at": "2026-09-29"},
        "doc_secondary": {"document_id": "doc_secondary", "canonical_url": "https://news.example.com/a",
                           "title": "OpenAI announces changes", "updated_at": "2026-09-29"},
    }
    text_by_id = {
        "doc_primary": "How we will do better for Australia\nOfficial announcement.",
        "doc_secondary": "OpenAI announces changes\nSee https://openai.com/index/foo for details.",
    }
    relationships, review = roe.resolve_company_gov_reports_on(documents_by_id, text_by_id)
    assert len(relationships) == 1
    rec = next(iter(relationships.values()))
    assert rec["source_document_id"] == "doc_secondary"
    assert rec["target_document_id"] == "doc_primary"
    assert rec["resolution_method"] == "EXPLICIT_URL_MATCH"
    assert any(r["result"] == "MATCH" for r in review)


def test_canonical_title_match_resolves_when_no_url_present():
    documents_by_id = {
        "doc_primary": {"document_id": "doc_primary", "canonical_url": "https://blog.google/ai/foo",
                         "title": "Announcing our new research initiative", "updated_at": "2026-09-29"},
        "doc_secondary": {"document_id": "doc_secondary", "canonical_url": "https://news.example.com/b",
                           "title": "Google news roundup", "updated_at": "2026-09-29"},
    }
    text_by_id = {
        "doc_primary": "Announcing our new research initiative\nDetails here.",
        "doc_secondary": "Google news roundup\nGoogle published 'Announcing our new research initiative' today.",
    }
    relationships, review = roe.resolve_company_gov_reports_on(documents_by_id, text_by_id)
    assert len(relationships) == 1
    rec = next(iter(relationships.values()))
    assert rec["resolution_method"] == "CANONICAL_TITLE_MATCH"


def test_no_signal_means_unresolved_reference_not_fabricated_match():
    documents_by_id = {
        "doc_primary": {"document_id": "doc_primary", "canonical_url": "https://openai.com/index/foo",
                         "title": "How we will do better for Australia", "updated_at": "2026-09-29"},
        "doc_secondary": {"document_id": "doc_secondary", "canonical_url": "https://news.example.com/c",
                           "title": "Unrelated article about something else entirely", "updated_at": "2026-09-29"},
    }
    text_by_id = {
        "doc_primary": "How we will do better for Australia\nOfficial announcement.",
        "doc_secondary": "Unrelated article about something else entirely, no mention of OpenAI at all.",
    }
    relationships, review = roe.resolve_company_gov_reports_on(documents_by_id, text_by_id)
    assert len(relationships) == 0
    assert any(r["result"] == "UNRESOLVED_REFERENCE" for r in review)


def test_no_primary_candidates_yields_empty_result_honestly():
    documents_by_id = {
        "doc_a": {"document_id": "doc_a", "canonical_url": "https://news.example.com/a", "title": "A", "updated_at": None},
        "doc_b": {"document_id": "doc_b", "canonical_url": "https://news.example.com/b", "title": "B", "updated_at": None},
    }
    relationships, review = roe.resolve_company_gov_reports_on(documents_by_id, {"doc_a": "A", "doc_b": "B"})
    assert relationships == {}
    assert review == []


def test_source_independence_wiring_merges_company_gov_pairs():
    # source_independence.load_reports_on_pairs()가 relationships.json과
    # relationships_company_gov.json을 합쳐서 읽는지 확인 - 기존 DOI/arXiv 파일은
    # 건드리지 않고 새 파일만 함께 읽는다. pytest가 없는 환경이라 tempfile로 직접
    # INTEL_DIR을 갈아끼우고 원상복구한다.
    import tempfile

    original_intel_dir = si.INTEL_DIR
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        (tmp / "relationships.json").write_text(
            '{"r1": {"from_document_id": "a", "to_document_id": "b"}}', encoding="utf-8"
        )
        (tmp / "relationships_company_gov.json").write_text(
            '{"r2": {"source_document_id": "c", "target_document_id": "d"}}', encoding="utf-8"
        )
        try:
            si.INTEL_DIR = tmp
            pairs = si.load_reports_on_pairs()
        finally:
            si.INTEL_DIR = original_intel_dir
    assert frozenset(("a", "b")) in pairs
    assert frozenset(("c", "d")) in pairs


def test_real_corpus_run_is_honest_about_zero_matches():
    # 실제 corpus(569 documents, 1346 raw items)에는 description 텍스트에 URL이 전혀
    # 없어(직접 확인됨) EXPLICIT_URL_MATCH가 구조적으로 발화할 수 없다. 이 테스트는
    # "언젠가 데이터가 생기면 동작한다"는 스캐폴딩이 실제로는 아무것도 조작해서
    # 만들어내지 않는다는 것을 확인한다(회귀 방지: 나중에 누군가 실수로 추측 매칭을
    # 넣으면 이 테스트가 깨진다).
    metrics, relationships, review = roe.run_on_real_corpus(write_output=False)
    assert isinstance(metrics["documents_examined"], int) and metrics["documents_examined"] > 0
    assert metrics["relationships_created"] == len(relationships)
