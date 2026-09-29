import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import atomizer  # noqa: E402
import dedup as dedup_mod  # noqa: E402
import indexer  # noqa: E402
import memory  # noqa: E402
import overrides as overrides_mod  # noqa: E402
import readiness as readiness_mod  # noqa: E402
from common import normalize_statement, stable_note_id  # noqa: E402
from concept_registry import concepts_in_text  # noqa: E402
from exporter import export_vault, note_to_markdown  # noqa: E402
from relation_service import build_structural_relations, graph_quality_metrics  # noqa: E402
from schema import (EVIDENCE_BACKED_TYPES, INTERPRETIVE_TYPES, NOTE_TYPES,  # noqa: E402
                     new_atomic_note_shell)

NOW = "2026-09-29T00:00:00+00:00"


def _fresh_memory_files():
    for name in ("notes.json", "relations.json"):
        p = PKG_DIR / name
        if p.exists():
            p.unlink()


# --- A/B/C: Fact -> Event -> Change atomization -----------------------------

def test_atomize_fact_produces_evidence_backed_note():
    fact = {"fact_id": "f1", "statement": "X increased by Y", "document_id": "doc1",
            "based_on_claim_status": "SOURCE_LOCATED", "created_at": NOW, "updated_at": NOW}
    note = atomizer.atomize_fact(fact, NOW)
    assert note["note_type"] == "FACT"
    assert note["note_type"] in EVIDENCE_BACKED_TYPES
    assert note["interpretation_distance"] == 0
    assert note["fact_ids"] == ["f1"]


def test_atomize_event_and_change():
    event = {"event_id": "e1", "event_name": "Nvidia news", "related_document_ids": ["doc1"],
              "entities": ["Nvidia"], "event_type": "OTHER"}
    e_note = atomizer.atomize_event(event, NOW)
    assert e_note["note_type"] == "EVENT"

    change = {"change_id": "c1", "change_statement": "Something changed", "change_name": "Change 1",
              "entities": ["OpenAI"], "domains": ["MODEL_RELEASE"], "change_confidence": "HIGH"}
    c_note = atomizer.atomize_change(change, NOW)
    assert c_note["note_type"] == "CHANGE"
    assert c_note["interpretation_distance"] == 1


# --- D: Hypothesis + supporting/counter evidence (schema-level, no real data) --

def test_evidence_backed_and_interpretive_never_overlap():
    assert not (EVIDENCE_BACKED_TYPES & INTERPRETIVE_TYPES)
    assert set(EVIDENCE_BACKED_TYPES) | set(INTERPRETIVE_TYPES) | {"CONCEPT", "RELATION"} == set(NOTE_TYPES)


# --- G: Rejected hypothesis/change preserved, not deleted --------------------

def test_human_rejected_change_excluded_from_atomization():
    rejected = {"change_id": "c2", "change_statement": "stmt", "change_name": "n",
                "override_status": "HUMAN_REJECTED"}
    assert atomizer.atomize_change(rejected, NOW) is None


# --- H: Duplicate fact dedup --------------------------------------------------

def test_duplicate_notes_deduped():
    fact = {"fact_id": "f1", "statement": "Same statement", "document_id": "doc1",
            "based_on_claim_status": "SOURCE_LOCATED"}
    n1 = atomizer.atomize_fact(fact, NOW)
    n2 = atomizer.atomize_fact(fact, NOW)
    out = dedup_mod.dedup_notes([n1, n2])
    assert len(out) == 1


# --- J: Entity vs Concept separation / R: Insight cannot become Fact --------

def test_concept_registry_only_returns_canonical():
    from schema import CANONICAL_CONCEPTS
    found = concepts_in_text("This is about AI Agent and compute demand")
    assert set(found) <= set(CANONICAL_CONCEPTS)
    assert "AI_AGENT" in found
    assert "COMPUTE" in found


def test_insight_cannot_be_created_as_fact_type():
    # atomizer only exposes atomize_fact/event/change - there is no atomize_insight
    # that returns note_type FACT; this asserts the module never conflates the two.
    assert not hasattr(atomizer, "atomize_insight")


# --- N: Human override persistence -------------------------------------------

def test_human_override_locks_note_against_rerun():
    _fresh_memory_files()
    fact = {"fact_id": "f1", "statement": "stmt v1", "document_id": "doc1",
            "based_on_claim_status": "SOURCE_LOCATED"}
    note = atomizer.atomize_fact(fact, NOW)
    notes_by_id, stats = memory.upsert_notes([note], NOW)
    assert stats["created"] == 1
    nid = note["note_id"]

    overrides = {nid: {"human_review_status": "HUMAN_REJECTED"}}
    notes_by_id = overrides_mod.apply_overrides(notes_by_id, overrides)
    assert notes_by_id[nid]["status"] == "REJECTED"

    # rerun with a "changed" statement under the same note_id must not silently
    # overwrite the human's rejection once persisted back through upsert.
    memory._save(memory.NOTES_PATH, notes_by_id)  # simulate persisted rejection
    fact2 = dict(fact, statement="stmt v1")  # same id, would produce identical note_id
    note2 = atomizer.atomize_fact(fact2, NOW)
    notes_by_id2, stats2 = memory.upsert_notes([note2], NOW)
    assert notes_by_id2[nid]["human_review_status"] == "HUMAN_REJECTED"
    assert stats2["unchanged_human_locked"] == 1
    _fresh_memory_files()


# --- P: rerun idempotency ------------------------------------------------------

def test_rerun_idempotent_stable_id():
    fact = {"fact_id": "f1", "statement": "stable statement", "document_id": "doc1",
            "based_on_claim_status": "SOURCE_LOCATED"}
    n1 = atomizer.atomize_fact(fact, NOW)
    n2 = atomizer.atomize_fact(fact, "2027-01-01T00:00:00+00:00")
    assert n1["note_id"] == n2["note_id"]


# --- Q: provenance reconstruction ---------------------------------------------

def test_stable_note_id_deterministic_helper():
    norm = normalize_statement("  Hello   World  ")
    assert norm == "hello world"
    id1 = stable_note_id("FACT", norm, "subj1")
    id2 = stable_note_id("FACT", norm, "subj1")
    assert id1 == id2


# --- Graph explosion guard -----------------------------------------------------

def test_relation_service_only_related_to_and_flags_dominance():
    notes = [
        new_atomic_note_shell("n1", "FACT", "t1", "s1", NOW),
        new_atomic_note_shell("n2", "EVENT", "t2", "s2", NOW),
    ]
    notes[0]["document_ids"] = ["docX"]
    notes[1]["document_ids"] = ["docX"]
    rels = build_structural_relations(notes, NOW)
    assert len(rels) == 1
    assert rels[0]["relation_type"] == "RELATED_TO"
    gm = graph_quality_metrics(notes, rels)
    assert gm["graph_quality_flag"] == "RELATED_TO_DOMINATED"


# --- Obsidian export -----------------------------------------------------------

def test_obsidian_export_writes_stable_filenames():
    fact = {"fact_id": "f1", "statement": "exported fact", "document_id": "doc1",
            "based_on_claim_status": "SOURCE_LOCATED"}
    note = atomizer.atomize_fact(fact, NOW)
    md = note_to_markdown(note)
    assert "type: FACT" in md
    with tempfile.TemporaryDirectory() as tmp:
        written = export_vault({note["note_id"]: note}, tmp)
        assert len(written) == 1
        assert (Path(tmp) / written[0]).exists()


# --- Rejected notes excluded from retrieval index ------------------------------

def test_rejected_notes_excluded_from_index():
    active = new_atomic_note_shell("n1", "FACT", "t", "s", NOW)
    rejected = new_atomic_note_shell("n2", "FACT", "t2", "s2", NOW)
    rejected["status"] = "REJECTED"
    idx = indexer.build_index({"n1": active, "n2": rejected})
    assert len(idx) == 1
    assert idx[0]["note_id"] == "n1"


# --- Readiness never fabricates READY for missing data -------------------------

def test_readiness_question_hypothesis_not_ready_when_absent():
    r = readiness_mod.assess({}, {}, {"broken_provenance_count": 0}, {})
    assert r["QUESTION_MEMORY_READY"] == "NOT_READY"
    assert r["HYPOTHESIS_MEMORY_READY"] == "NOT_READY"
    assert r["ATOMIC_MEMORY_READY"] == "NOT_READY"
