# PHASE G-K CHECKPOINT REMEDIATION — item 3/3: View Revision Candidate. 자동 revision
# 금지, materiality 기반 REVISION != CONTRADICTION, BOUNDARY_CONDITION 1급 타입,
# Operator History/Novelty Gate 연결, canonical Stage 6 memory 절대 미접근.
import inspect
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import view_revision as vr  # noqa: E402

NOW = "2026-09-29T00:00:00+00:00"


def _isolate():
    tmp_dir = Path(tempfile.mkdtemp(prefix="ob_test_vr_"))
    vr.VIEW_REVISION_PATH = tmp_dir / "store.json"


_WEAK = {"source_quality": "LOW", "directness": "LOW", "temporal_relevance": "UNKNOWN",
         "scope_match": "UNKNOWN", "independence": "UNKNOWN", "measurement_quality": "UNKNOWN"}
_STRONG = {"source_quality": "HIGH", "directness": "HIGH", "temporal_relevance": "HIGH",
           "scope_match": "HIGH", "independence": "HIGH", "measurement_quality": "MEDIUM"}


def test_candidate_has_exactly_17_fields_and_requires_human_approval():
    c = vr.new_view_revision_candidate(
        "q1", "note_1", "기존 진술", "OBSERVED_CHANGE", ["note_2"], 2,
        "CONTRADICTS", _STRONG, "제안된 새 진술", NOW)
    assert len(c) == 17
    assert c["requires_human_approval"] is True
    assert c["status"] == "PENDING_HUMAN_REVIEW"
    assert c["human_review_status"] == "UNREVIEWED"


def test_single_weak_contradicting_source_never_produces_reverse():
    # REVISION != CONTRADICTION(Te 지시): 약한 반박 하나로는 REVERSE가 아니라 기껏해야
    # QUALIFY 정도만 제안한다.
    c = vr.new_view_revision_candidate(
        "q1", "note_1", "기존 진술", "SUPPORTED_TREND", ["note_2"], 1,
        "CONTRADICTS", _WEAK, "제안된 새 진술", NOW)
    assert c["revision_type"] != "REVERSE"
    assert c["revision_type"] in ("QUALIFY", "NO_REVISION_NEEDED")


def test_strong_independent_contradiction_can_reach_reverse():
    c = vr.new_view_revision_candidate(
        "q1", "note_1", "기존 진술", "SUPPORTED_TREND", ["note_2", "note_3"], 2,
        "CONTRADICTS", _STRONG, "제안된 새 진술", NOW)
    assert c["revision_type"] == "REVERSE"


def test_boundary_condition_is_first_class_revision_type():
    c = vr.new_view_revision_candidate(
        "q1", "note_1", "기존 진술", "SUPPORTED_TREND", ["note_2"], 2,
        "REVEALS_BOUNDARY", _STRONG, "제안된 새 진술", NOW, is_boundary_condition=True)
    assert c["revision_type"] == "BOUNDARY_CONDITION"
    assert "BOUNDARY_CONDITION" in vr.REVISION_TYPES


def test_novelty_gate_mapping_matches_te_spec():
    assert vr.novelty_kind_for_relationship("EXTENDS") == "EXTENSION_CANDIDATE"
    assert vr.novelty_kind_for_relationship("QUALIFIES") == "VIEW_REVISION_CANDIDATE"
    assert vr.novelty_kind_for_relationship("WEAKENS") == "VIEW_REVISION_CANDIDATE"
    assert vr.novelty_kind_for_relationship("CONTRADICTS") == "HIGH_VALUE_VIEW_REVISION_CANDIDATE"
    assert vr.novelty_kind_for_relationship("REVEALS_BOUNDARY") == "HIGH_VALUE_VIEW_REVISION_CANDIDATE"


def test_creating_a_candidate_never_modifies_canonical_stage6_memory():
    _isolate()
    c = vr.new_view_revision_candidate(
        "q1", "note_1", "기존 진술", "OBSERVED_CHANGE", ["note_2"], 2,
        "QUALIFIES", _STRONG, "제안", NOW)
    vr.save_candidate(c)
    reloaded = vr.list_candidates()
    assert reloaded[0]["status"] == "PENDING_HUMAN_REVIEW"
    # knowledge_memory 모듈은 이 파일에서 아예 import되지 않는다.
    src = inspect.getsource(vr)
    assert "import adapter" not in src
    assert not hasattr(vr, "adapter")


def test_approve_does_not_touch_canonical_memory_either():
    _isolate()
    c = vr.save_candidate(vr.new_view_revision_candidate(
        "q1", "note_1", "기존 진술", "OBSERVED_CHANGE", ["note_2"], 2,
        "WEAKENS", _STRONG, "제안", NOW))
    approved = vr.approve_candidate(c["revision_candidate_id"])
    assert approved["status"] == "APPROVED"
    # 여전히 view_revision_candidates.json 안에만 있다 - canonical memory로 자동 승격 없음.
    assert vr.list_candidates("APPROVED")[0]["revision_candidate_id"] == c["revision_candidate_id"]


def test_operator_history_used_only_as_context_never_as_evidence():
    history_entries = [
        {"query_id": "q0", "retrieved_object_ids": ["note_1", "note_9"]},
        {"query_id": "q_other", "retrieved_object_ids": ["note_9"]},
    ]
    ctx = vr.previous_view_context_from_history(history_entries, "note_1")
    assert len(ctx) == 1
    # retriever.py는 여전히 history를 참조하지 않는다(Phase J/K 회귀 체크와 동일 원칙).
    import retriever
    assert "history" not in inspect.getsource(retriever).lower()
