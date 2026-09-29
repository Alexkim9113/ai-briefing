# STAGE 7 PHASE D — synthetic tests (섹션 62): context budget, cache/context hash.
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import context_builder  # noqa: E402
import pipeline  # noqa: E402
from common import context_hash  # noqa: E402
from context_budget import apply_budget, estimate_tokens  # noqa: E402
from schema import new_context_pack_shell  # noqa: E402


def test_empty_context_pack_leaves_lists_empty_not_fabricated():
    pack = new_context_pack_shell()
    assert pack["counter_evidence"] == []
    assert pack["structural_changes"] == []
    assert pack["claim_ceiling"] is None


def test_apply_budget_noop_when_under_target():
    pack = new_context_pack_shell()
    pack["known_facts"] = [{"note_id": "n1", "statement": "short"}]
    trimmed, info = apply_budget(pack, target_tokens=20000)
    assert info["over_budget"] is False
    assert info["truncated_fields"] == []
    assert trimmed["known_facts"] == pack["known_facts"]


def test_apply_budget_trims_when_over_target():
    pack = new_context_pack_shell()
    pack["known_facts"] = [{"note_id": f"n{i}", "statement": "x" * 500} for i in range(200)]
    trimmed, info = apply_budget(pack, target_tokens=1000)
    assert info["over_budget"] is False or len(trimmed["known_facts"]) < len(pack["known_facts"])
    assert estimate_tokens(trimmed) <= estimate_tokens(pack)


def test_context_hash_deterministic_for_same_pack():
    pack = new_context_pack_shell()
    pack["question"] = "same question"
    h1 = context_hash(pack)
    h2 = context_hash(pack)
    assert h1 == h2


def test_context_hash_changes_when_pack_changes():
    pack1 = new_context_pack_shell()
    pack1["question"] = "q1"
    pack2 = new_context_pack_shell()
    pack2["question"] = "q2"
    assert context_hash(pack1) != context_hash(pack2)


def test_pipeline_builds_context_pack_from_real_retrieval():
    record = pipeline.ask("Nvidia 규제 관련 최근 사건은?", "RETRIEVE")
    assert "context_pack" in record
    assert record["context_pack"]["object_references"], "object_references가 비어있으면 안 됨"
    assert record["context_pack"]["source_references"], "실제 document까지 추적된 source가 있어야 함"
    assert record["context_hash"]


def test_pipeline_never_puts_raw_document_text_in_context_pack():
    # 섹션 22: raw DB dump 금지 - context_pack에는 구조화된 note reference만 있어야 하고
    # document 원문(article body)이 통째로 들어가면 안 된다.
    record = pipeline.ask("Nvidia 규제 관련 최근 사건은?", "RETRIEVE")
    pack = record["context_pack"]
    for fact in pack["known_facts"]:
        assert set(fact.keys()) == {"note_id", "statement"}
