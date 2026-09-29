# STAGE 7 PHASE B — synthetic tests (섹션 62): retrieval planning, provenance
# reconstruction, dedup, source independence(중복 note_id 제거 확인).
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import dedup as dedup_mod  # noqa: E402
import provenance as provenance_mod  # noqa: E402
import reranker  # noqa: E402
import retriever  # noqa: E402
from retrieval_planner import plan_retrieval  # noqa: E402


def test_retrieval_planner_fact_lookup_maps_to_spec_targets():
    plan = plan_retrieval("FACT_LOOKUP")
    assert plan["targets"] == ["FACT", "EVIDENCE", "SOURCE"]


def test_retrieval_planner_unknown_intent_has_no_targets():
    plan = plan_retrieval("UNKNOWN")
    assert plan["targets"] == []


def test_dedup_by_note_id_removes_duplicates():
    rows = [{"note_id": "a"}, {"note_id": "b"}, {"note_id": "a"}]
    out = dedup_mod.dedup_by_note_id(rows)
    assert [r["note_id"] for r in out] == ["a", "b"]


def test_provenance_reconstruction_marks_missing_document_not_hidden():
    note = {"document_ids": ["exists", "missing"]}
    documents = {"exists": {"title": "T", "source_url": "http://x"}}
    trail = provenance_mod.reconstruct(note, documents)
    assert trail[0]["found"] is True
    assert trail[1]["found"] is False
    assert trail[1]["document_id"] == "missing"


def test_reranker_prefers_scope_matching_entity():
    rows = [{"note_id": "n1", "entities": [], "concepts": []},
            {"note_id": "n2", "entities": ["Nvidia"], "concepts": []}]
    scope = {"ENTITY": ["Nvidia"], "CONCEPT": None, "TIME": None}
    ranked = reranker.rerank(rows, scope)
    assert ranked[0]["note_id"] == "n2"


# --- 실제 production corpus 대상 통합 테스트 -----------------------------------

def test_retrieve_real_entity_scope_returns_nvidia_notes():
    result = retriever.retrieve("EVENT_LOOKUP", {"ENTITY": ["Nvidia"], "CONCEPT": None, "TIME": None})
    assert result["results"], "실제 corpus에 Nvidia 관련 Note가 있어야 함"
    assert all("Nvidia" in r["entities"] for r in result["results"])


def test_retrieve_real_concept_scope_returns_ai_agent_notes():
    result = retriever.retrieve("FACT_LOOKUP", {"ENTITY": None, "CONCEPT": ["AI_AGENT"], "TIME": None})
    assert result["results"]
    assert all("AI_AGENT" in r["concepts"] for r in result["results"])


def test_retrieve_provenance_traces_to_real_document():
    result = retriever.retrieve("EVENT_LOOKUP", {"ENTITY": ["Nvidia"], "CONCEPT": None, "TIME": None})
    found_any = any(p["found"] for r in result["results"] for p in r["provenance"])
    assert found_any, "적어도 하나는 실제 document까지 추적 가능해야 함"


def test_retrieve_no_scope_falls_back_to_broad_recall():
    result = retriever.retrieve("GENERAL_SYNTHESIS", {"ENTITY": None, "CONCEPT": None, "TIME": None})
    assert result["total_candidates_before_limit"] > 0
