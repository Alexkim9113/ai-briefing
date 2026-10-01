import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import relevance_gate as m  # noqa: E402


def test_weather_article_excluded():
    r = m.classify_public_relevance("도쿄 35일 연속 비, 1886년 이후 최장 기록",
                                     "도쿄에 35일 연속 비가 내려 1886년 이후 최장 기록을 세웠다.")
    assert r["category"] not in m.PUBLIC_CATEGORIES
    assert r["category"] in m.EXCLUDED_CATEGORIES


def test_forex_article_excluded():
    r = m.classify_public_relevance("원/달러 환율 1400원 돌파", "달러 강세에 원화 가치가 하락했다.")
    assert r["category"] not in m.PUBLIC_CATEGORIES


def test_sports_article_excluded():
    r = m.classify_public_relevance("손흥민, 해트트릭으로 팀 승리 이끌어", "오늘 경기에서 세 골을 넣었다.")
    assert r["category"] not in m.PUBLIC_CATEGORIES


def test_ai_weather_research_included():
    r = m.classify_public_relevance(
        "AI 기상예측 모델, 전통 수치예보보다 정확도 높아",
        "딥러닝 기반 AI 기상예측 모델이 기존 수치예보 모델보다 태풍 경로 예측 정확도가 높다는 연구 결과가 나왔다.")
    assert r["category"] in m.PUBLIC_CATEGORIES


def test_keyword_data_alone_is_not_ai_relevance():
    r = m.classify_public_relevance("기업, 새로운 데이터 플랫폼 출시", "이 회사는 데이터 분석 플랫폼을 출시했다고 밝혔다.")
    assert r["category"] in ("KEYWORD_COLLISION", "GENERAL_NEWS")
    assert r["category"] not in m.PUBLIC_CATEGORIES


def test_ai_datacenter_power_article_with_explicit_link_included():
    r = m.classify_public_relevance(
        "AI 데이터센터 전력 수요 급증, 전력망 부담 가중",
        "AI 모델 학습과 추론을 위한 데이터센터 전력 수요가 급증하면서 지역 전력망에 부담을 주고 있다는 분석이 나왔다.")
    assert r["category"] in m.PUBLIC_CATEGORIES


def test_bare_ai_substring_in_ordinary_word_is_not_a_false_positive():
    r = m.classify_public_relevance("Company will maintain its supply chain amid trade tensions",
                                     "Executives said they aim to retain staff and remain compliant.")
    assert r["category"] not in m.PUBLIC_CATEGORIES


def test_standalone_ai_token_in_title_is_detected():
    r = m.classify_public_relevance("Startup raises funding for AI chips", "")
    assert r["category"] in m.PUBLIC_CATEGORIES


def test_public_categories_and_excluded_are_disjoint():
    assert set(m.PUBLIC_CATEGORIES).isdisjoint(set(m.EXCLUDED_CATEGORIES))


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
