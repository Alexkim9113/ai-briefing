# SOURCE INTELLIGENCE CORRECTION v1.0 — synthetic tests (spec 섹션 55: SHADOW
# IMPLEMENTATION → SYNTHETIC TEST 단계). 실제 네트워크 pilot(섹션 67)은 이 세션 환경의
# outbound 제한으로 실행 불가 - 그 사실을 최종 보고서에 명시한다.
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import content_acquisition  # noqa: E402
import content_status  # noqa: E402
import entity_resolution  # noqa: E402
import schema  # noqa: E402
import summary_firewall  # noqa: E402
from ai_relevance import assess_ai_relevance  # noqa: E402

AI_KEYWORDS = ["AI", "인공지능", "ChatGPT", "LLM", "챗봇", "머신러닝", "딥러닝"]


# ---------------------------------------------------------------- content_status (Phase D, 섹션 74)

def test_snippet_only_when_only_summary_present():
    assert content_status.assign_content_status({"title": "t", "summary": "짧은 소개글"}) == "SNIPPET_ONLY"


def test_title_only_when_no_summary():
    assert content_status.assign_content_status({"title": "t", "summary": ""}) == "TITLE_ONLY"


def test_unknown_when_nothing_present():
    assert content_status.assign_content_status({"title": "", "summary": ""}) == "UNKNOWN"


def test_full_text_only_when_acquisition_actually_succeeded():
    # 섹션 74: TITLE_ONLY/SNIPPET_ONLY가 절대 FULL_TEXT처럼 취급되면 안 된다 -
    # acquired가 없으면 아무리 title/summary가 길어도 FULL_TEXT를 자칭하지 않는다.
    long_summary = "매우 긴 소개글 " * 50
    status = content_status.assign_content_status({"title": "t", "summary": long_summary})
    assert status == "SNIPPET_ONLY"
    assert status != "FULL_TEXT"


def test_full_text_comes_only_from_real_acquisition_result():
    acquired = {"status": "FULL_TEXT", "text": "실제 본문 " * 100}
    assert content_status.assign_content_status({"title": "t", "summary": "s"}, acquired=acquired) == "FULL_TEXT"


def test_content_ceiling_blocks_source_verified_from_snippet_only():
    claim, capped = schema.enforce_content_ceiling("SOURCE_VERIFIED", "SNIPPET_ONLY")
    assert capped is True
    assert claim == "SECONDARY_ONLY"


def test_content_ceiling_allows_source_verified_from_full_text():
    claim, capped = schema.enforce_content_ceiling("SOURCE_VERIFIED", "FULL_TEXT")
    assert capped is False
    assert claim == "SOURCE_VERIFIED"


def test_title_only_never_allows_source_located_or_above():
    claim, capped = schema.enforce_content_ceiling("SOURCE_LOCATED", "TITLE_ONLY")
    assert capped is True
    assert claim == "INSUFFICIENT_SOURCE"


# ---------------------------------------------------------------- content_acquisition (Phase C, 섹션 46/47)

def test_no_fetcher_never_attempts_network_and_returns_unknown():
    result = content_acquisition.acquire_content("https://example.com/a")
    assert result["status"] == "UNKNOWN"
    assert result["text"] is None


def test_fetch_failed_on_http_error_status():
    result = content_acquisition.acquire_content("https://example.com/a", fetcher=lambda u: {"status_code": 500})
    assert result["status"] == "FETCH_FAILED"


def test_paywalled_detected_honestly():
    result = content_acquisition.acquire_content("https://example.com/a", fetcher=lambda u: {"paywalled": True})
    assert result["status"] == "PAYWALLED"


def test_blocked_detected_honestly():
    result = content_acquisition.acquire_content("https://example.com/a", fetcher=lambda u: {"status_code": 403})
    assert result["status"] == "BLOCKED"


def test_full_text_extraction_via_trafilatura_when_html_available():
    if not content_acquisition.is_extractor_available():
        return  # trafilatura가 없는 환경이면 스킵(설치 실패를 조용히 성공으로 위장하지 않음)
    html = ("<html><body><article><p>" + ("실제 기사 본문 문장입니다. " * 40) +
            "</p></article><nav>메뉴 링크1 링크2</nav></body></html>")
    result = content_acquisition.acquire_content("https://example.com/a", fetcher=lambda u: {"html": html})
    assert result["status"] == "FULL_TEXT"
    assert result["text"] and "실제 기사 본문" in result["text"]
    assert result["extractor"] == "trafilatura"


def test_too_short_extraction_is_not_promoted_to_full_text():
    if not content_acquisition.is_extractor_available():
        return
    html = "<html><body><p>짧음</p></body></html>"
    result = content_acquisition.acquire_content("https://example.com/a", fetcher=lambda u: {"html": html})
    assert result["status"] == "FETCH_FAILED"


def test_structured_primary_bypasses_html_fetch():
    result = content_acquisition.acquire_content("https://arxiv.org/abs/1", structured_primary={"arxiv_id": "1"})
    assert result["status"] == "STRUCTURED_PRIMARY_DATA"


# ---------------------------------------------------------------- summary_firewall (Phase H, 섹션 32/33, 72)

def test_gemini_eligible_text_never_returns_mx_b():
    raw_item = {"summary": "", "mx": {"b": "생성된 요약"}}
    assert summary_firewall.gemini_eligible_text(raw_item) is None


def test_gemini_eligible_text_returns_real_summary_when_present():
    raw_item = {"summary": "발행사 RSS 소개글", "mx": {"b": "생성된 요약"}}
    assert summary_firewall.gemini_eligible_text(raw_item) == "발행사 RSS 소개글"


def test_summary_derived_cannot_be_promoted_to_source_located():
    try:
        summary_firewall.assert_not_summary_derived("SOURCE_LOCATED", "mx.b", "test canonical fact")
        assert False, "should have raised"
    except ValueError:
        pass


def test_summary_derived_secondary_only_is_allowed_through():
    summary_firewall.assert_not_summary_derived("SECONDARY_ONLY", "mx.b", "test")  # 예외 없이 통과해야 함


def test_summary_contamination_regression_source_body_vs_mx_b():
    # 섹션 72 정확한 시나리오: source body는 A라고 말하는데 mx.b는 B라고 잘못 말했다.
    # canonical fact는 A(summary/실제 원문)에서 와야지 B(mx.b)에서 오면 안 된다.
    raw_item = {"summary": "A: 실제 발행사가 밝힌 내용", "mx": {"b": "B: 잘못된 생성 요약"}}
    text = summary_firewall.gemini_eligible_text(raw_item)
    assert text == "A: 실제 발행사가 밝힌 내용"
    assert "B:" not in (text or "")


def test_summary_contamination_regression_no_body_means_insufficient_source():
    # source body(summary)가 없고 mx.b만 있으면: SOURCE_VERIFIED 승격 없음 - Gemini 입력
    # 자체가 None이 되어 애초에 Level3 후보가 되지 않는다.
    raw_item = {"summary": "", "mx": {"b": "생성된 요약만 있음"}}
    assert summary_firewall.gemini_eligible_text(raw_item) is None


# ---------------------------------------------------------------- entity_resolution (Phase J, 섹션 38)

def test_openai_aliases_resolve_to_same_entity():
    ids = {entity_resolution.resolve_entity(s) for s in ("OpenAI", "Open AI", "오픈AI")}
    assert ids == {"org_openai"}


def test_eu_ai_act_aliases_resolve_to_same_entity():
    ids = {entity_resolution.resolve_entity(s) for s in ("EU AI Act", "AI Act", "유럽연합 인공지능법")}
    assert ids == {"policy_eu_ai_act"}


def test_unregistered_surface_form_is_unknown_not_guessed():
    assert entity_resolution.resolve_entity("어떤 낯선 이름 주식회사") is None


def test_resolution_status_reports_partial_honestly():
    status = entity_resolution.resolution_status()
    assert status["status"] == "PARTIAL"
    assert "PERSON" in status["entity_types_missing"]  # 사람 alias는 아직 시드 없음


# ---------------------------------------------------------------- ai_relevance / REMOVE_AI_TEST (Phase K, 섹션 29/30/71)

def test_ai_in_title_is_central():
    r = assess_ai_relevance("OpenAI, 새 모델 공개", "회사가 발표했다", AI_KEYWORDS)
    assert r["status"] == "CENTRAL"


def test_no_ai_keyword_anywhere_is_none():
    r = assess_ai_relevance("청년변호사단체 새변, 미래헌법포럼 숙의토론 '참정권과 미래헌법'",
                            "참정권과 미래헌법을 주제로 토론회가 열렸다.", AI_KEYWORDS)
    assert r["status"] == "NONE"


def test_single_peripheral_ai_mention_is_downgraded_by_remove_ai_test():
    # AI가 한 번 스치듯 언급되지만 제거해도 central event(투자 행사)는 그대로 설명됨.
    summary = "이번 행사는 지역 투자 유치를 위한 설명회였다. 일부 발표자는 AI 활용 사례도 소개했다."
    r = assess_ai_relevance("지역 투자 유치 설명회 열려", summary, AI_KEYWORDS)
    assert r["status"] == "PERIPHERAL"


def test_single_ai_mention_that_is_the_whole_point_stays_central():
    summary = "AI가 이번 사건의 핵심이다."
    r = assess_ai_relevance("행사 개최", summary, AI_KEYWORDS)
    assert r["status"] == "CENTRAL"


def test_lawleader_regression_fixture_does_not_produce_ai_education_framing():
    # 섹션 30/71 LAWLEADER REGRESSION FIXTURE. 실제 RSS raw summary 원문은 archive에
    # 남아있지 않아(감사 보고서 F절 GAP) 대표성 있는 synthetic fixture로 재현한다:
    # 제목/소개글 어디에도 AI 키워드가 없는, 청년변호사단체 미래헌법포럼 유형의 기사.
    title = "청년변호사단체 새변, 미래헌법포럼 숙의토론 '참정권과 미래헌법'"
    summary = "새변이 주최한 미래헌법포럼에서 참정권 확대와 미래 헌법 개정 방향을 논의했다."
    r = assess_ai_relevance(title, summary, AI_KEYWORDS)
    assert r["status"] == "NONE"
    # 섹션 30/31: 이 케이스에서 "교육·역량 강화", "AI 역량이 기본 소양", "교육 격차" 같은
    # AI-education framing이 나와서는 안 된다 - 이 모듈은 그런 문장을 아예 생성하지
    # 않는다(생성 자체를 하는 함수가 아니라 relevance 판정만 한다는 것이 이 설계의 핵심
    # 안전장치: status=NONE이면 상위 파이프라인은 애초에 mx_note류의 토픽 템플릿을
    # 호출할 근거가 없어야 한다 - 배선은 아직 안 됐음을 최종 보고서에 명시).
    for banned in ("교육", "역량", "기본 소양"):
        assert banned not in title
        assert banned not in summary


def test_lawleader_regression_briefing_mx_note_also_does_not_fire_education_template():
    # 섹션 71 확장: assess_ai_relevance는 판정만 할 뿐 실제로 site 콘텐츠를 만드는 건
    # briefing.py의 mx_note()/_EVENTS 테이블이다. 이 테스트는 그 production 코드를 직접
    # 실행해서, Lawleader류 fixture(및 "역량"이라는 범용 단어가 여러 번 등장하지만 AI와는
    # 무관한 변형)가 "교육·역량 강화" 캔드 템플릿을 발화시키지 않는지 확인한다.
    import importlib.util

    repo_root = PKG_DIR.parent.parent  # intel/source_intelligence -> intel -> repo root
    spec = importlib.util.spec_from_file_location(
        "briefing_lawleader_check", repo_root / "briefing.py"
    )
    briefing = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(briefing)

    base_item = {
        "title": "청년변호사단체 새변, 미래헌법포럼 숙의토론 '참정권과 미래헌법'",
        "title_ko": "",
        "summary": "새변이 주최한 미래헌법포럼에서 참정권 확대와 미래 헌법 개정 방향을 논의했다.",
        "summary_ko": "",
        "category": "news",
        "source": "새변",
    }
    summ, view, tags = briefing.mx_note(dict(base_item))
    for banned in ("교육", "역량", "기본 소양", "교육 격차"):
        assert banned not in summ
        assert banned not in view

    # 변형: "역량"이 여러 번 나오지만 AI와는 전혀 무관한 경우(원래 버그의 근본 원인 재현) -
    # 버킷 단어 개수만으로 발화하던 예전 로직이면 여기서 걸렸을 것이다.
    variant = dict(base_item)
    variant["title"] = base_item["title"] + " - 청년 법조인 역량강화 세미나"
    variant["summary"] = base_item["summary"] + " 법조인 역량 강화 방안도 함께 논의됐다."
    summ2, view2, tags2 = briefing.mx_note(variant)
    for banned in ("AI 역량이 기본 소양", "교육 격차를 줄이는"):
        assert banned not in view2
