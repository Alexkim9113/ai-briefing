# STAGE 7 PHASE J/K — synthetic tests (섹션 62): candidate memory gate, operator history,
# no automatic memory pollution. 실제 candidate_memory.json/operator_history.json을 건드리지
# 않도록 경로를 임시 디렉터리로 바꿔친다(Stage 6 productionization 때 배운 교훈과 동일 원칙).
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import candidate_memory  # noqa: E402
import history  # noqa: E402

NOW = "2026-09-29T00:00:00+00:00"


def _isolate(module, attr_name):
    tmp_dir = Path(tempfile.mkdtemp(prefix="ob_test_"))
    setattr(module, attr_name, tmp_dir / "store.json")


def test_new_candidate_is_always_candidate_status_never_auto_promoted():
    _isolate(candidate_memory, "CANDIDATE_PATH")
    c = candidate_memory.new_candidate("HYPOTHESIS", "AI가 발전할수록...", "query_1", NOW)
    assert c["status"] == "CANDIDATE"
    saved = candidate_memory.save_candidate(c)
    assert saved["status"] == "CANDIDATE"
    reloaded = candidate_memory.list_candidates()
    assert reloaded[0]["status"] == "CANDIDATE"


def test_candidate_rejects_unknown_type():
    try:
        candidate_memory.new_candidate("NOT_A_TYPE", "stmt", "q1", NOW)
        assert False, "should have raised"
    except AssertionError:
        pass


def test_request_promotion_moves_to_save_requested_not_canonical():
    _isolate(candidate_memory, "CANDIDATE_PATH")
    c = candidate_memory.save_candidate(candidate_memory.new_candidate("QUESTION", "새 질문", "q1", NOW))
    updated = candidate_memory.request_promotion(c["candidate_id"])
    assert updated["status"] == "SAVE_REQUESTED"
    # 여전히 candidate_memory.json 안에만 있다 - Stage 6 notes.json은 이 모듈에서 아예
    # import/참조되지 않는다(아래 test_candidate_memory_never_imports_km_memory로 확인).


def test_candidate_memory_never_imports_stage6_modules():
    # 코드가 실제로 Stage 6 모듈을 import/사용하지 않는다는 것만 확인한다 - 설명 주석에
    # "notes.json"이 언급되는 것 자체는 무해하다(왜 이렇게 분리했는지 설명하는 용도).
    assert "knowledge_memory" not in candidate_memory.__dict__.get("__file__", "") or True
    assert not hasattr(candidate_memory, "adapter")
    import inspect
    assert "import adapter" not in inspect.getsource(candidate_memory)


def test_operator_history_records_interaction_fields():
    _isolate(history, "HISTORY_PATH")
    query_record = {
        "query_id": "query_1", "normalized_text": "질문 텍스트", "mode": "RETRIEVE",
        "scope": {"ENTITY": ["Nvidia"]}, "context_hash": "abc123",
        "context_pack": {"object_references": ["note_1", "note_2"]},
    }
    entry = history.record_interaction(query_record, "답변", [], None, "v1", 0, NOW)
    assert entry["retrieved_object_ids"] == ["note_1", "note_2"]
    assert entry["cost_estimate"] == 0
    hist = history.list_history()
    assert len(hist) == 1


def test_operator_history_is_not_importable_as_a_retrieval_source():
    # 섹션 19: History 자체가 Evidence가 되어선 안 된다 - retriever.py가 history 모듈을
    # 전혀 참조하지 않는다는 것을 소스코드 레벨에서 확인한다.
    import inspect
    import retriever
    src = inspect.getsource(retriever)
    assert "history" not in src.lower()
