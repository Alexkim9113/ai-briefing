# STAGE 7 PHASE A — synthetic tests (섹션 62): intent classification, scope extraction,
# query record shape. Production data를 수정하지 않는다(이 phase는 애초에 아무 JSON도 쓰지 않음).
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import intent_classifier  # noqa: E402
import pipeline  # noqa: E402
import query_parser  # noqa: E402
import scope_parser  # noqa: E402
from common import normalize_query, stable_query_id  # noqa: E402
from schema import ASK_MODES, QUERY_INTENTS, SCOPE_DIMENSIONS  # noqa: E402

NOW = "2026-09-29T00:00:00+00:00"


def test_normalize_query_collapses_whitespace_and_case():
    assert normalize_query("  Hello   World  ") == "hello world"


def test_stable_query_id_deterministic():
    id1 = stable_query_id("최근 AI Agent 관련 Event는?", "RETRIEVE", NOW)
    id2 = stable_query_id("최근 AI Agent 관련 Event는?", "RETRIEVE", NOW)
    assert id1 == id2


def test_query_record_has_all_modes_and_unknown_default_intent():
    for mode in ASK_MODES:
        record = query_parser.parse_query("test question", mode, NOW)
        assert record["mode"] == mode
        assert record["intent"] == "UNKNOWN"


def test_intent_classifier_fact_lookup():
    intent = intent_classifier.classify_intent(normalize_query("최근 AI 저작권 관련 중요한 사건 찾아줘"))
    assert intent in QUERY_INTENTS


def test_intent_classifier_hypothesis_test():
    text = normalize_query("AI가 발전할수록 희소성이 권한으로 이동하고 있다는 가설을 검토해줘")
    assert intent_classifier.classify_intent(text) == "HYPOTHESIS_TEST"


def test_intent_classifier_counter_evidence():
    text = normalize_query("이 주장에 대한 반박 증거가 있는가")
    assert intent_classifier.classify_intent(text) == "COUNTER_EVIDENCE_SEARCH"


def test_intent_classifier_ambiguous_returns_unknown_not_fabricated():
    # 완전히 무관한 문장은 억지로 어떤 intent로도 승격하지 않는다.
    assert intent_classifier.classify_intent(normalize_query("점심 뭐 먹지")) == "UNKNOWN"


def test_scope_extraction_never_guesses_unspecified_dims():
    scope = scope_parser.extract_scope("Nvidia 관련 최근 소식")
    assert scope["ENTITY"] == ["Nvidia"]
    assert scope["TIME"] == "RECENT"
    # 텍스트에 없는 차원은 절대 추측하지 않는다.
    assert scope["GEOGRAPHY"] is None
    assert scope["JURISDICTION"] is None
    assert scope["INDUSTRY"] is None


def test_scope_extraction_concept_uses_canonical_registry_only():
    scope = scope_parser.extract_scope("AI Agent와 compute demand에 대한 질문")
    assert scope["CONCEPT"] is not None
    assert "AI_AGENT" in scope["CONCEPT"]
    assert "COMPUTE" in scope["CONCEPT"]


def test_scope_extraction_all_dimensions_present_even_when_none():
    scope = scope_parser.extract_scope("아무 신호도 없는 문장")
    assert set(scope.keys()) == set(SCOPE_DIMENSIONS)


def test_pipeline_ask_phase_a_end_to_end():
    record = pipeline.ask("Nvidia 규제 관련 최근 사건은?", "RETRIEVE")
    assert record["mode"] == "RETRIEVE"
    assert record["scope"]["ENTITY"] == ["Nvidia"]
    assert record["intent"] in QUERY_INTENTS


def test_pipeline_rejects_unknown_mode():
    try:
        pipeline.ask("test", "NOT_A_REAL_MODE")
        assert False, "should have raised"
    except AssertionError:
        pass
