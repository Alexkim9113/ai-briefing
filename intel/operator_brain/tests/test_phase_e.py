# STAGE 7 PHASE E — synthetic tests (섹션 62): retrieval-only end-to-end, structured
# response shape, Claude=0 확인.
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

from ask import ask_metaxis  # noqa: E402


def test_ask_metaxis_never_calls_claude_in_phase_e():
    result = ask_metaxis("최근 Nvidia 규제 관련 사건은?")
    assert result["structured_response"]["model"] is None


def test_ask_metaxis_returns_answer_text_and_structured_response():
    result = ask_metaxis("최근 Nvidia 규제 관련 사건은?")
    assert isinstance(result["answer_text"], str) and result["answer_text"]
    assert result["structured_response"]["response_id"].startswith("resp_")


def test_ask_metaxis_no_result_question_reports_insufficient_not_silent():
    result = ask_metaxis("완전히 무관한 점심 메뉴 추천")
    assert "NO RESULT" in result["answer_text"] or result["structured_response"]["evidence_sufficiency"]


def test_unknown_intent_with_no_scope_never_guesses_broad_recall():
    # Te CONTINUE 섹션 0 CORE RULE: NO EVIDENCE != FILL WITH SOMETHING. intent도 못 알아낸
    # 질문에 scope 신호까지 없으면 index 전체를 "관련 있다"고 우기지 않고 정직하게 0건.
    result = ask_metaxis("완전히 무관한 점심 메뉴 추천")
    assert result["query_record"]["intent"] == "UNKNOWN"
    assert len(result["query_record"]["retrieval"]["results"]) == 0
    assert result["structured_response"]["evidence_sufficiency"] == "INSUFFICIENT_EVIDENCE"


def test_ask_metaxis_citation_guard_fact_ids_match_answer_text():
    result = ask_metaxis("최근 AI Agent 관련 중요한 Event는?")
    for fid in result["structured_response"]["used_fact_ids"]:
        assert fid in result["answer_text"]
    for eid in result["structured_response"]["used_event_ids"]:
        assert eid in result["answer_text"]
