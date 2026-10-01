import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import content_aware_relevance as m  # noqa: E402


def test_weather_negative_control_excluded():
    doc = {"title": "도쿄 35일 연속 비, 1886년 이후 최장 기록", "category": "news_global"}
    r = m.classify_content_aware_relevance(doc)
    assert r["relevance_class"] not in m.PUBLIC_RELEVANCE_CLASSES
    assert r["publication_eligible"] is False


def test_sports_negative_control_excluded():
    doc = {"title": "손흥민, 해트트릭으로 팀 승리 이끌어", "category": "news_global"}
    r = m.classify_content_aware_relevance(doc)
    assert r["publication_eligible"] is False


def test_ordinary_economy_negative_control_excluded():
    doc = {"title": "원/달러 환율 1400원 돌파", "category": "news_global"}
    r = m.classify_content_aware_relevance(doc)
    assert r["publication_eligible"] is False


def test_ai_paper_without_literal_ai_in_title_recognized():
    doc = {"title": "VkVIO: Cross-platform GPU Acceleration for Visual-Inertial Odometry",
           "category": "papers", "source_id": "src_arxiv_cs_ro_robot",
           "abstract_excerpt": "We propose a multi-agent large language model pipeline for odometry."}
    r = m.classify_content_aware_relevance(doc)
    assert r["relevance_class"] in m.PUBLIC_RELEVANCE_CLASSES


def test_multi_agent_research_recognition():
    doc = {"title": "Multi-Agent Code Judge: Two Label-Free Measurements",
           "category": "papers", "source_id": "src_arxiv_cs_ai_ai_general"}
    r = m.classify_content_aware_relevance(doc)
    assert r["relevance_class"] in m.PUBLIC_RELEVANCE_CLASSES


def test_bare_technique_term_without_research_context_not_promoted():
    doc = {"title": "Neural network signaling discovered in coral reef fish",
           "category": "news_global", "source_id": "src_some_biology_news"}
    r = m.classify_content_aware_relevance(doc)
    assert r["relevance_class"] not in m.PUBLIC_RELEVANCE_CLASSES


def test_contextual_document_not_shown_as_ai_news():
    # A real power-grid statistic doc -- useful as Intelligence evidence context, but not itself
    # AI news, so it must never show up as a PUBLIC AI_* category.
    doc = {"title": "Rural electrification: Grid extension, decentralization, and financing",
           "category": "research", "doi": "10.2172/7260748"}
    r = m.classify_content_aware_relevance(doc)
    assert r["relevance_class"] not in m.PUBLIC_RELEVANCE_CLASSES


def test_content_depth_reflects_available_fields():
    assert m.compute_content_depth({"title": "t"}) == "TITLE_ONLY"
    assert m.compute_content_depth({"title": "t", "field": "AI 일반"}) == "CONTENT_PARTIAL"
    assert m.compute_content_depth({"title": "t", "abstract_excerpt": "abs"}) == "CONTENT_COMPLETE"


def test_publication_eligibility_is_deterministic_not_llm():
    doc = {"title": "AI 데이터센터 전력 수요 급증", "category": "news_ko"}
    r1 = m.classify_content_aware_relevance(doc)
    r2 = m.classify_content_aware_relevance(doc)
    assert r1 == r2


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
