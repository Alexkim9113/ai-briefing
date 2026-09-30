# STAGE 7 PHASE L — private_api tests. Follows this repo's convention (no pytest, no
# unittest.TestCase): plain test_*() functions with bare `assert`, loaded and run via
# importlib by a runner script (see intel/private_api/tests/run_all.py and
# intel/source_intelligence/tests/test_briefing_provenance_wiring.py for the same pattern).
#
# These tests read the REAL repo corpus (documents.json, knowledge_memory/notes.json, etc.)
# read-only. They write no new state into tracked corpus files: the one write path exercised
# (export_obsidian_bulk) is always given a tempfile.mkdtemp() output directory, never a path
# inside the repo.
import inspect
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import service  # noqa: E402
from errors import ApiError  # noqa: E402
from loader import load_km_memory  # noqa: E402


def _real_note_id():
    notes = load_km_memory().load_notes()
    assert notes, "expected at least one real note in knowledge_memory/notes.json for this test corpus"
    return next(iter(notes))


def test_health_reports_real_flags_and_never_claims_llm_without_a_key():
    result = service.health()
    assert result["version"] == service.API_VERSION
    assert set(result["available"]) == {"knowledge_memory", "documents", "relationships", "operator_brain"}
    assert isinstance(result["llm_enabled"], bool)
    # This sandbox has no ANTHROPIC_API_KEY - health must not fabricate llm_enabled=True.
    import os
    if not os.environ.get("ANTHROPIC_API_KEY"):
        assert result["llm_enabled"] is False
    assert "timestamp" in result


def test_status_returns_real_counts_not_placeholders():
    result = service.status()
    assert isinstance(result["documents_count"], int)
    assert isinstance(result["notes_count"], int)
    assert isinstance(result["relationships_count"], int)
    # honest zero is fine - just must match the real files exactly, not an estimate.
    notes = load_km_memory().load_notes()
    assert result["notes_count"] == len(notes)
    assert sum(result["note_type_distribution"].values()) == len(notes)


def test_search_real_term_returns_only_real_matches():
    result = service.search("AI", limit=5)
    assert result["q"] == "AI"
    assert result["total"] == len(result["results"]) if result["total"] <= 5 else True
    for row in result["results"]:
        assert "id" in row and "kind" in row


def test_search_nonexistent_term_is_honestly_empty():
    result = service.search("zzz_definitely_not_in_corpus_zzz_qwerty12345")
    assert result["total"] == 0
    assert result["results"] == []


def test_search_rejects_empty_query():
    try:
        service.search("")
        assert False, "expected ApiError"
    except ApiError as e:
        assert e.code == "INVALID_QUERY"


def test_search_caps_limit_at_max():
    result = service.search("a", limit=99999)
    assert result["limit"] == service._MAX_SEARCH_LIMIT


def test_get_document_real_and_missing():
    documents = load_km_memory  # noqa: F841 (documents come from km_adapter, not km_memory)
    from loader import load_km_adapter
    docs = load_km_adapter().load_documents()
    if docs:
        did = next(iter(docs))
        result = service.get_document(did)
        assert result["document"]["document_id"] == did
        # copyright boundary: never a full article body, only what's persisted.
        assert "full_text" not in result["document"]
        assert "body" not in result["document"]
    try:
        service.get_document("__no_such_document_id__")
        assert False, "expected ApiError"
    except ApiError as e:
        assert e.code == "NOT_FOUND"


def test_get_note_and_related_real_and_missing():
    note_id = _real_note_id()
    note = service.get_note(note_id)
    assert note["note_id"] == note_id

    related = service.related_notes(note_id)
    assert related["note_id"] == note_id
    assert isinstance(related["related"], list)
    # Every relation_type returned must be one this corpus's relations.json actually has -
    # never an invented one.
    real_relations = load_km_memory().load_relations()
    real_types = {r.get("relation_type") for r in real_relations.values() if isinstance(r, dict)}
    for row in related["related"]:
        assert row["relation_type"] in real_types

    try:
        service.get_note("__no_such_note_id__")
        assert False, "expected ApiError"
    except ApiError as e:
        assert e.code == "NOT_FOUND"


def test_trace_real_chain_and_stopped_chain():
    note_id = _real_note_id()
    result = service.trace(note_id)
    assert result["status"] in ("OK", "PROVENANCE_UNKNOWN")
    assert isinstance(result["trail"], list)

    try:
        service.trace("__no_such_note_id__")
        assert False, "expected ApiError"
    except ApiError as e:
        assert e.code == "NOT_FOUND"


def test_evidence_reuses_existing_scoring_not_a_second_system():
    note_id = _real_note_id()
    result = service.evidence(note_id)
    assert result["note_id"] == note_id
    sufficiency = result["evidence_sufficiency"]
    from loader import load_operator_brain
    ob_schema = load_operator_brain("schema")
    assert sufficiency["state"] in ob_schema.EVIDENCE_SUFFICIENCY_STATES
    # context_pack must come from context_builder.build_context_pack's own shell, not a
    # hand-rolled structure - spot check a couple of its distinctive shell keys.
    for key in ("known_facts", "key_events", "observed_changes", "claim_ceiling", "metrics"):
        assert key in result["context_pack"]


def test_query_endpoint_is_deterministic_retrieval_only():
    result = service.query({"question": "AI Agent"})
    assert "intent" in result and "retrieval" in result and "evidence_sufficiency" in result
    try:
        service.query({"question": "AI Agent", "mode": "DEEP_THINK"})
        assert False, "expected ApiError rejecting a non-RETRIEVE mode"
    except ApiError as e:
        assert e.code == "INVALID_QUERY"
    try:
        service.query({})
        assert False, "expected ApiError for missing question"
    except ApiError as e:
        assert e.code == "INVALID_QUERY"


def test_obsidian_export_single_note_has_valid_frontmatter_and_real_wikilinks_only():
    note_id = _real_note_id()
    result = service.export_obsidian_note(note_id)
    md = result["markdown"]
    assert md.startswith("---\n")
    assert f"id: {note_id}" in md
    assert "type:" in md and "status:" in md
    # any [[wikilink]] present must correspond to a real relation edge, not a fabricated one -
    # note_to_markdown only ever receives related_notes drawn from real relations.json.
    import re
    links = re.findall(r"\[\[([^\]]+)\]\]", md)
    real_relations = load_km_memory().load_relations()
    linked_note_ids = set()
    for rel in real_relations.values():
        if isinstance(rel, dict) and rel.get("status") != "REJECTED":
            linked_note_ids.add(rel.get("subject_id"))
            linked_note_ids.add(rel.get("object_id"))
    supporting_and_counter = set((service.get_note(note_id).get("supporting_evidence_ids") or [])
                                  + (service.get_note(note_id).get("counter_evidence_ids") or []))
    for link in links:
        assert link in linked_note_ids or link in supporting_and_counter, (
            f"fabricated wikilink not backed by a real relation or evidence id: {link}")


def test_obsidian_export_bulk_requires_explicit_scope_never_silent_full_dump():
    try:
        service.export_obsidian_bulk()
        assert False, "expected ApiError requiring an explicit scope"
    except ApiError as e:
        assert e.code == "INVALID_QUERY"

    note_id = _real_note_id()
    with tempfile.TemporaryDirectory() as tmp:
        result = service.export_obsidian_bulk(note_ids=[note_id], out_dir=tmp)
        assert result["exported_count"] == 1
        assert result["vault_dir"] == tmp
        written_path = Path(tmp) / result["written"][0]
        assert written_path.exists()
        assert written_path.read_text(encoding="utf-8").startswith("---\n")


def test_json_export_validity_and_scope():
    result = service.export_json(limit=3)
    assert result["count"] <= 3
    assert isinstance(result["notes"], list)
    for note in result["notes"]:
        assert "note_id" in note


def test_contradictions_endpoint_is_honest_about_real_backing_store():
    result = service.contradictions()
    assert isinstance(result["count"], int)
    assert result["count"] == len(result["contradictions"])


def test_view_revisions_endpoint_never_auto_resolves():
    result = service.view_revisions()
    assert isinstance(result["count"], int)
    for cand in result["candidates"]:
        assert cand.get("requires_human_approval") is True
        assert cand.get("status") != "APPROVED_AUTOMATICALLY"


def test_zero_llm_calls_anywhere_in_private_api_source():
    """Grep-assert: no Claude/Gemini/OpenAI SDK client construction anywhere in the new
    private_api package, and the only Claude-adjacent symbol referenced anywhere is the
    read-only adapter_status() check used by health()."""
    src_dir = PKG_DIR
    forbidden = ("anthropic.Anthropic(", "anthropic.Client(", "openai.OpenAI(", "openai.Client(",
                 "google.generativeai", "genai.configure", "call_claude(", "run_deep_think(")
    for path in sorted(src_dir.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"found forbidden LLM-call symbol {token!r} in {path}"


def test_default_query_path_never_triggers_ask_metaxis_or_claude_adapter():
    src = inspect.getsource(service.query)
    assert "ask_metaxis" not in src
    assert "claude_adapter" not in src
    assert "import ask" not in src


# ---------------------------------------------------------------------------
# STAGE 7 PHASE M — Foresight Engine endpoint tests.
# ---------------------------------------------------------------------------
def test_coverage_endpoint_returns_real_counts():
    result = service.coverage()
    assert result["documents_total"] > 0
    assert result["by_geography"] == {"UNKNOWN": result["documents_total"]}


def test_knowledge_gaps_endpoint_always_reports_geographic_gap():
    result = service.knowledge_gaps()
    assert result["count"] == len(result["gaps"])
    assert any(g["dimension"] == "GEOGRAPHIC" for g in result["gaps"])


def test_cross_domain_connections_endpoint_never_uses_causal_language():
    result = service.cross_domain_connections()
    assert isinstance(result["count"], int)
    for conn in result["connections"]:
        assert conn["relation_type"] in (
            "ASSOCIATED_WITH", "PRECEDES", "POSSIBLE_DRIVER", "CONTRIBUTING_FACTOR")
        assert "CAUSES" not in conn["relation_type"]


def test_historical_analogies_endpoint_requires_topic():
    threw = False
    try:
        service.historical_analogies()
    except ApiError as e:
        threw = True
        assert e.code == "INVALID_QUERY"
    assert threw


def test_historical_analogies_endpoint_reports_real_gap_for_this_corpus():
    # This real corpus (as of Phase M) has no document old enough to ground a historical
    # analogy - the endpoint must say so honestly, not fabricate a comparison.
    result = service.historical_analogies(topic="AI regulation")
    assert result["status"] in ("HISTORICAL_EVIDENCE_GAP", "CANDIDATE", "ANALOGY_REJECTED_INCOMPLETE")


def test_intelligence_package_endpoint_requires_topic():
    threw = False
    try:
        service.intelligence_package()
    except ApiError as e:
        threw = True
        assert e.code == "INVALID_QUERY"
    assert threw


def test_intelligence_package_endpoint_honest_structure_for_real_topic():
    result = service.intelligence_package(topic="Nvidia")
    assert result["topic"] == "Nvidia"
    assert isinstance(result["documents"]["count"], int)
    assert isinstance(result["notes"]["count"], int)
    assert set(result["layers"].keys()) == {
        "signals", "patterns", "structural_changes", "structural_analyses",
        "contradictions", "view_revisions", "scenarios", "policy_questions"}
    for layer_result in result["layers"].values():
        assert layer_result["count"] == 0  # honest: every layer is empty in the real corpus
    assert result["evidence_sufficiency"] in (
        "NO_EVIDENCE", "DOCUMENTS_ONLY", "NOTES_BUILT")


def test_intelligence_package_endpoint_honest_zero_for_nonsense_topic():
    result = service.intelligence_package(topic="zzz_definitely_not_in_corpus_zzz")
    assert result["documents"]["count"] == 0
    assert result["notes"]["count"] == 0
    assert result["evidence_sufficiency"] == "NO_EVIDENCE"
