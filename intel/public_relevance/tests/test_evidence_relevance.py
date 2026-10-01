import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import evidence_relevance as m  # noqa: E402
import content_aware_relevance as car  # noqa: E402


def test_public_and_evidence_relevance_are_independent_fields():
    # Te's explicit Section-10 example: general electricity statistics are not AI news, but ARE
    # real evidence for the AI_ENERGY_INFRA hypothesis.
    doc = {"title": "전국 전력 수요 통계 발표, 올해 전력망 부하 증가", "category": "news_ko"}
    r = car.classify_content_aware_relevance(doc)
    assert r["relevance_class"] not in car.PUBLIC_RELEVANCE_CLASSES
    assert r["publication_eligible"] is False
    assert r["evidence_relevance"] == "RELEVANT_TO_HYPOTHESIS"
    assert "AI_ENERGY_INFRA" in r["evidence_matched_hypotheses"]


def test_public_eligible_false_never_forces_evidence_eligible_false():
    # The explicit forbidden conversion from Section 10: PUBLIC_ELIGIBLE=false must never force
    # EVIDENCE_ELIGIBLE=false.
    doc = {"title": "노동시장 고용률 통계 발표", "category": "news_ko"}
    r = car.classify_content_aware_relevance(doc)
    assert r["publication_eligible"] is False
    assert r["evidence_relevance"] == "RELEVANT_TO_HYPOTHESIS"


def test_scope_direct_for_public_category():
    r = car.classify_content_aware_relevance({"title": "AI 데이터센터 전력 수요 급증", "category": "news_ko"})
    assert r["relevance_scope"] == "DIRECT"
    assert r["publication_eligible"] is True


def test_scope_structural_for_non_ai_hypothesis_evidence():
    doc = {"title": "전력망 부하 통계 보고서", "category": "news_ko"}
    r = car.classify_content_aware_relevance(doc)
    assert r["relevance_scope"] == "STRUCTURAL"
    assert r["publication_eligible"] is False


def test_scope_contextual_for_background_with_real_content_but_no_hypothesis_match():
    doc = {"title": "국내 경제 성장률 전망 발표", "category": "news_ko",
           "abstract_excerpt": "정부가 올해 경제 성장률 전망치를 발표했다."}
    r = car.classify_content_aware_relevance(doc)
    assert r["relevance_scope"] in ("CONTEXTUAL", "IRRELEVANT")  # deterministic, not DIRECT/STRUCTURAL
    assert r["publication_eligible"] is False


def test_scope_irrelevant_for_title_only_no_match():
    doc = {"title": "손흥민 해트트릭", "category": "news_ko"}
    r = car.classify_content_aware_relevance(doc)
    assert r["relevance_scope"] == "IRRELEVANT"


def test_structural_or_contextual_never_publication_eligible():
    for scope in ("STRUCTURAL", "CONTEXTUAL", "IRRELEVANT", "UNKNOWN"):
        eligible = (scope == "DIRECT")
        assert eligible is False


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
