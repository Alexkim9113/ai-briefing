# N-2 Section 33 -- Public API/View boundary tests. Verifies, against real modules (not mocks),
# that the four hard boundaries hold: 0 private full-text exposure, 0 rights-restricted full-text
# exposure, 0 feed exposure for PUBLIC_RELEVANCE-irrelevant documents, 0 exposure for unsupported
# causal METAXIS Points -- and that non-AI structural/contextual evidence never auto-shows in the
# public feed.
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import content_aware_relevance as car  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "intel" / "private_research_vault"))
sys.path.insert(0, str(ROOT / "intel" / "research_rights"))
import vault  # noqa: E402
import research_rights_model as rights  # noqa: E402
import briefing  # noqa: E402


def test_irrelevant_document_not_publication_eligible():
    doc = {"title": "손흥민 해트트릭으로 승리", "category": "news_ko"}
    r = car.classify_content_aware_relevance(doc)
    assert r["publication_eligible"] is False


def test_structural_evidence_document_never_auto_shown_in_public_feed():
    doc = {"title": "전력망 부하 증가 통계", "category": "news_ko"}
    r = car.classify_content_aware_relevance(doc)
    assert r["relevance_scope"] == "STRUCTURAL"
    assert r["publication_eligible"] is False  # structural evidence relevance != public feed exposure


def test_unsupported_causal_point_zero_exposure_in_production():
    it = {"title": "AI 데이터센터 전력 수요 기사", "summary": "전력 수요가 늘고 있다", "detail": "", "id": "boundary1"}
    r = {"brief": "어떤 기사 요약 내용입니다 괜찮은 길이로 작성됨.",
         "point": "AI 수요 증가가 전력망 위기를 만들고 있다는 분석이다.", "tags": ["AI"]}
    out = briefing._mx_ok(it, r)
    it["mx"] = out
    attrs = briefing._mx_attrs(it)
    assert 'data-mv=""' in attrs  # the unsupported Point is never rendered into the public attr


def test_private_vault_module_has_no_public_fulltext_export_function():
    # The vault module must expose no function whose name implies a public/bulk full-text export.
    public_names = [n for n in dir(vault) if not n.startswith("_")]
    assert not any("public" in n.lower() and "full" in n.lower() for n in public_names)


def test_rights_restricted_document_never_auto_upgraded_to_fulltext_allowed():
    doc = {"document_id": "d1", "title": "t", "rights_mode": "LINK_ONLY"}
    record = rights.classify_rights_for_document(doc)
    assert record["FULLTEXT_STORAGE_ALLOWED"] is False
    assert record["FULLTEXT_PUBLICATION_ALLOWED"] is False


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
