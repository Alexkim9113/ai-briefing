# STAGE 6 PRODUCTIONIZATION v1.0 — synthetic test matrix (섹션 61, 39: synthetic fixtures
# stay in tests/, never leak into notes.json/relations.json/memory_index.json).
import sys
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
from relation_service import (build_lineage_relations,  # noqa: E402
                               build_semantic_relations_from_upstream, dedup_relations,
                               graph_quality_metrics)
from schema import LINEAGE_RELATION_TYPES, SEMANTIC_RELATION_TYPES, new_atomic_note_shell

NOW = "2026-09-29T00:00:00+00:00"
LATER = "2026-10-01T00:00:00+00:00"


def _fresh():
    # 실제 production notes.json/relations.json을 절대 지우지 않는다 - memory 모듈 경로를
    # 테스트 전용 임시 디렉터리로 바꿔친다(이전 버전은 실제 파일을 unlink()해서, 이 테스트가
    # real pipeline.py 실행과 같은 세션에서 돌면 production notes.json이 통째로 사라지는
    # 실제 버그가 있었다 - test_foundation.py에서도 동일하게 수정함).
    import tempfile
    tmp_dir = Path(tempfile.mkdtemp(prefix="km_test_memory_prod_"))
    memory.NOTES_PATH = tmp_dir / "notes.json"
    memory.RELATIONS_PATH = tmp_dir / "relations.json"


# 3/4. Existing relation import: lineage (FACT -> EVENT) ------------------------

def test_lineage_relation_only_from_real_document_membership():
    fact = atomizer.atomize_fact({"fact_id": "f1", "statement": "s1", "document_id": "docA"}, NOW)
    event = atomizer.atomize_event({"event_id": "e1", "event_name": "Event A",
                                     "related_document_ids": ["docA", "docB"]}, NOW)
    rels = build_lineage_relations([fact], [event], NOW)
    assert len(rels) == 1
    assert rels[0]["relation_type"] == "PART_OF_EVENT"
    assert rels[0]["relation_class"] == "LINEAGE"
    assert rels[0]["evidence_ids"] == ["docA"]


def test_no_lineage_relation_without_shared_document():
    fact = atomizer.atomize_fact({"fact_id": "f1", "statement": "s1", "document_id": "docZ"}, NOW)
    event = atomizer.atomize_event({"event_id": "e1", "event_name": "Event A",
                                     "related_document_ids": ["docA"]}, NOW)
    rels = build_lineage_relations([fact], [event], NOW)
    assert rels == []


# 5/6. Semantic relation preservation from upstream, no new causal inference ----

def test_semantic_relation_imported_from_upstream_supporting_events():
    event = atomizer.atomize_event({"event_id": "evtprod_1", "event_name": "Event 1",
                                     "related_document_ids": ["d1"]}, NOW)
    change = atomizer.atomize_change({
        "change_id": "chg1", "change_statement": "stmt", "change_name": "Change 1",
        "supporting_event_ids": ["evtprod_1"], "contradicting_event_ids": [],
    }, NOW)
    event_index = {"evtprod_1": event["note_id"]}
    rels = build_semantic_relations_from_upstream([change], event_index, NOW)
    assert len(rels) == 1
    assert rels[0]["relation_type"] == "SUPPORTS"
    assert rels[0]["relation_class"] == "SEMANTIC"
    assert rels[0]["object_id"] == change["note_id"]


def test_semantic_relation_never_generates_causes():
    # relation_service has no code path that emits CAUSES - assert the module's public
    # builders can only ever produce types explicitly passed from upstream fields
    # (SUPPORTS/CONTRADICTS/PART_OF_EVENT), never infer CAUSES from correlation.
    import relation_service
    src = Path(relation_service.__file__).read_text(encoding="utf-8")
    assert '"CAUSES"' not in src


# 7. Stable relation ID ----------------------------------------------------------

def test_relation_id_stable_across_reruns():
    fact = atomizer.atomize_fact({"fact_id": "f1", "statement": "s1", "document_id": "docA"}, NOW)
    event = atomizer.atomize_event({"event_id": "e1", "event_name": "Event A",
                                     "related_document_ids": ["docA"]}, NOW)
    r1 = build_lineage_relations([fact], [event], NOW)
    r2 = build_lineage_relations([fact], [event], LATER)
    assert r1[0]["relation_id"] == r2[0]["relation_id"]


# 8. Relation dedup ---------------------------------------------------------------

def test_relation_dedup_merges_evidence_ids():
    fact = atomizer.atomize_fact({"fact_id": "f1", "statement": "s1", "document_id": "docA"}, NOW)
    event = atomizer.atomize_event({"event_id": "e1", "event_name": "Event A",
                                     "related_document_ids": ["docA", "docB"]}, NOW)
    fact["document_ids"] = ["docA", "docB"]  # pretend fact also touches docB
    rels = build_lineage_relations([fact], [event], NOW)
    deduped = dedup_relations(rels + rels)  # simulate two upstream paths finding the same edge
    assert len(deduped) == 1
    assert deduped[0]["evidence_ids"] == ["docA", "docB"]


# 9/10. Temporal propagation / unknown -------------------------------------------

def test_temporal_fields_propagate_only_when_upstream_has_them():
    event = atomizer.atomize_event({"event_id": "e1", "event_name": "Event A",
                                     "event_date": "2026-09-28"}, NOW)
    assert event["event_date"] == "2026-09-28"

    event_no_date = atomizer.atomize_event({"event_id": "e2", "event_name": "Event B"}, NOW)
    assert event_no_date["event_date"] is None  # never guessed from published_at or anything else


def test_change_first_last_seen_propagate():
    change = atomizer.atomize_change({
        "change_id": "chg1", "change_statement": "stmt", "change_name": "n",
        "first_seen": "2026-09-28", "last_seen": "2026-09-29", "time_span_days": 1,
    }, NOW)
    assert change["first_seen"] == "2026-09-28"
    assert change["last_seen"] == "2026-09-29"
    assert change["temporal_scope"] == "1_DAYS"


# 11/12. Scope propagation / unknown / 13-14 scope non-expansion ----------------

def test_scope_fields_default_unknown_not_global():
    fact = atomizer.atomize_fact({"fact_id": "f1", "statement": "s1", "document_id": "docA"}, NOW)
    assert fact["geographic_scope"] is None
    assert fact["jurisdiction"] is None
    assert fact["geographic_scope"] != "GLOBAL"


# 15/16. Revision v1 -> v2, supersedes -------------------------------------------

def test_revision_bumps_version_and_keeps_history():
    _fresh()
    fact_v1 = atomizer.atomize_fact({"fact_id": "f1", "statement": "stmt v1", "document_id": "d1"}, NOW)
    notes, stats = memory.upsert_notes([fact_v1], NOW)
    assert stats["created"] == 1
    nid = fact_v1["note_id"]

    fact_v2 = dict(fact_v1)
    fact_v2["statement"] = "stmt v1 REVISED"
    fact_v2["status"] = "REVISED"
    notes2, stats2 = memory.upsert_notes([fact_v2], LATER)
    assert stats2["updated"] == 1
    assert notes2[nid]["version"] == 2
    assert len(notes2[nid]["history"]) == 2
    assert notes2[nid]["statement"] == "stmt v1 REVISED"
    _fresh()


# 17. Human override persistence (already covered in test_foundation; re-verify with
#     an upstream update happening AFTER the human rejection - section 22) ---------

def test_human_override_survives_upstream_update():
    _fresh()
    fact = atomizer.atomize_fact({"fact_id": "f1", "statement": "stmt", "document_id": "d1"}, NOW)
    notes, _ = memory.upsert_notes([fact], NOW)
    nid = fact["note_id"]
    notes = overrides_mod.apply_overrides(notes, {nid: {"human_review_status": "HUMAN_CONFIRMED"}})
    memory._save(memory.NOTES_PATH, notes)

    # upstream "changes" (same fact_id, but content technically identical since note_id is
    # deterministic from the statement - a real upstream edit would produce a new note_id,
    # which is correct: it should not silently overwrite the confirmed note under a new id
    # colliding with the old one).
    notes2, stats2 = memory.upsert_notes([fact], LATER)
    assert notes2[nid]["human_review_status"] == "HUMAN_CONFIRMED"
    assert stats2["unchanged_human_locked"] == 1
    _fresh()


# 18/19. Question / Hypothesis synthetic memory ----------------------------------

def test_synthetic_question_full_lifecycle():
    _fresh()
    q = new_atomic_note_shell("q_synthetic_1", "QUESTION", "Test question",
                               "Is X happening?", NOW)
    q["source_object_type"] = "SYNTHETIC_FIXTURE"
    notes, stats = memory.upsert_notes([q], NOW)
    assert stats["created"] == 1
    idx = indexer.build_index(notes)
    assert any(r["note_id"] == "q_synthetic_1" and r["note_type"] == "QUESTION" for r in idx)
    filtered = indexer.filter_index(idx, note_type="QUESTION")
    assert len(filtered) == 1
    _fresh()


def test_synthetic_hypothesis_with_support_and_counter():
    h = new_atomic_note_shell("h_synthetic_1", "HYPOTHESIS", "Test hypothesis",
                               "X may cause Y", NOW)
    h["supporting_evidence_ids"] = ["ev_1"]
    h["counter_evidence_ids"] = ["ev_2"]
    h["uncertainties"] = ["small sample"]
    assert h["supporting_evidence_ids"] and h["counter_evidence_ids"]
    # Hypothesis is never allowed to start as FACT-confidence (distance None until set)
    assert h["interpretation_distance"] is None


# 20/21/22/23. Supporting/counter evidence, falsifier, uncertainty, epistemic separation

def test_insight_cannot_be_promoted_to_fact_type():
    insight = new_atomic_note_shell("i_synthetic_1", "INSIGHT", "Test insight", "stmt", NOW)
    assert insight["note_type"] != "FACT"
    assert not hasattr(atomizer, "promote_insight_to_fact")


# 25/26. Claim ceiling / interpretation distance ---------------------------------

def test_claim_ceiling_fact_statement_stays_reported_not_asserted():
    fact = atomizer.atomize_fact({
        "fact_id": "f1", "statement": "식별자로 논문의 존재가 확인됨(내용은 미검증)",
        "document_id": "d1", "based_on_claim_status": "SOURCE_LOCATED"}, NOW)
    # atomizer copies the upstream statement verbatim - it never rewrites a hedged
    # "existence confirmed, content unverified" statement into an unconditional claim.
    assert fact["statement"].startswith("식별자로")
    assert fact["interpretation_distance"] == 0


def test_change_interpretation_distance_is_one_not_zero():
    change = atomizer.atomize_change({"change_id": "c1", "change_statement": "s",
                                       "change_name": "n"}, NOW)
    assert change["interpretation_distance"] == 1  # never silently treated as raw Fact (0)


# 27-31. Retrieval by type/concept/entity/time, rejected exclusion ---------------

def test_retrieval_filters():
    notes = {
        "n1": {**new_atomic_note_shell("n1", "FACT", "t", "s", NOW), "concepts": ["ENERGY"],
               "entities": ["OpenAI"], "updated_at": "2026-09-28T00:00:00+00:00"},
        "n2": {**new_atomic_note_shell("n2", "EVENT", "t2", "s2", NOW), "concepts": ["COMPUTE"],
               "entities": ["Nvidia"], "updated_at": "2026-09-29T00:00:00+00:00"},
        "n3": {**new_atomic_note_shell("n3", "FACT", "t3", "s3", NOW), "status": "REJECTED"},
    }
    idx = indexer.build_index(notes)
    assert len(idx) == 2  # n3 excluded by default
    idx_audit = indexer.build_index(notes, include_rejected=True)
    assert len(idx_audit) == 3

    by_concept = indexer.filter_index(idx, concept="ENERGY")
    assert [r["note_id"] for r in by_concept] == ["n1"]
    by_entity = indexer.filter_index(idx, entity="Nvidia")
    assert [r["note_id"] for r in by_entity] == ["n2"]
    by_type = indexer.filter_index(idx, note_type="EVENT")
    assert [r["note_id"] for r in by_type] == ["n2"]
    by_time = indexer.filter_index(idx, updated_after="2026-09-29T00:00:00+00:00")
    assert [r["note_id"] for r in by_time] == ["n2"]


# 32/33. Provenance retrieval / Counter evidence retrieval readiness -------------

def test_provenance_reconstruction_from_note_to_document():
    import adapter
    documents = adapter.load_documents()
    facts = adapter.load_facts_verified()
    real_fact = next(f for f in facts if f.get("document_id"))
    note = atomizer.atomize_fact(real_fact, NOW)
    did = note["document_ids"][0]
    assert did in documents  # NOTE -> document_id -> real DOCUMENT, reconstructable


def test_counter_evidence_synthetic_roundtrip():
    hyp = new_atomic_note_shell("h1", "HYPOTHESIS", "t", "Some hypothesis", NOW)
    counter = new_atomic_note_shell("f_counter", "FACT", "t2", "Counter fact", NOW)
    hyp["counter_evidence_ids"] = [counter["note_id"]]
    rel = {"subject_id": counter["note_id"], "relation_type": "CONTRADICTS",
           "object_id": hyp["note_id"], "relation_class": "SEMANTIC"}
    assert rel["relation_type"] in SEMANTIC_RELATION_TYPES
    assert counter["note_id"] in hyp["counter_evidence_ids"]


# 34. Orphan allowed ---------------------------------------------------------------

def test_orphan_note_is_not_an_error():
    fact = new_atomic_note_shell("n1", "FACT", "t", "s", NOW)  # no document_ids, no relations
    gm = graph_quality_metrics([fact], [])
    assert gm["orphan_note_count"] == 1
    assert gm["graph_quality_flag"] == "OK"  # orphan alone never trips the quality flag


# 35/36. Graph explosion guard / no keyword-only relation ------------------------

def test_keyword_only_relation_count_is_always_zero():
    gm = graph_quality_metrics([], [])
    assert gm["keyword_only_relation_count"] == 0


# 39. Synthetic isolation ----------------------------------------------------------

def test_synthetic_fixtures_never_appear_in_real_pipeline_output():
    import pipeline
    notes_by_id, relations_by_id, index, metrics, readiness = pipeline.run(write_output=False)
    assert "q_synthetic_1" not in notes_by_id
    assert "h_synthetic_1" not in notes_by_id
    assert all(n["source_object_type"] != "SYNTHETIC_FIXTURE" for n in notes_by_id.values())


# 40/41. Upstream update / upstream missing --------------------------------------

def test_upstream_missing_document_recorded_as_broken_provenance_not_hidden():
    fact = {"fact_id": "f1", "statement": "s1", "document_id": "does_not_exist_doc"}
    note = atomizer.atomize_fact(fact, NOW)
    # atomize_fact alone doesn't check documents.json (that happens in atomizer.run());
    # verify the note still carries the document_id so run() can detect it's missing.
    assert note["document_ids"] == ["does_not_exist_doc"]


# Readiness / Stage 7 verdict vocabulary -----------------------------------------

def test_stage7_entry_verdict_not_blocked_by_absent_interpretive_types():
    readiness = readiness_mod.assess({}, {}, {"broken_provenance_count": 0}, {})
    verdict, blocking = readiness_mod.stage7_entry_verdict(readiness)
    # QUESTION/HYPOTHESIS/COUNTER_EVIDENCE are READY_FOR_NATURAL_DATA, which counts as
    # satisfying the criterion - only ATOMIC_MEMORY/PROVENANCE (genuinely NOT_READY with
    # zero notes) should block.
    assert "QUESTION_MEMORY_READY" not in blocking
    assert "HYPOTHESIS_MEMORY_READY" not in blocking
    assert "COUNTER_EVIDENCE_READY" not in blocking
    assert "ATOMIC_MEMORY_READY" in blocking


# Obsidian export productionization (섹션 46-48) ----------------------------------

def test_export_frontmatter_includes_temporal_scope_review_revision_fields():
    import exporter
    note = new_atomic_note_shell("n1", "FACT", "t", "s", NOW)
    note["first_seen"] = "2026-09-01"
    note["jurisdiction"] = "EU"
    note["human_review_status"] = "HUMAN_CONFIRMED"
    note["version"] = 2
    md = exporter.note_to_markdown(note)
    assert "first_seen: 2026-09-01" in md
    assert "jurisdiction: EU" in md
    assert "human_review_status: HUMAN_CONFIRMED" in md
    assert "version: 2" in md


def test_export_only_links_real_relations_not_shared_keywords():
    import exporter
    from common import stable_relation_id
    from schema import new_relation_shell
    note_a = new_atomic_note_shell("na", "FACT", "t", "s", NOW)
    note_b = new_atomic_note_shell("nb", "EVENT", "t2", "s2", NOW)
    rel = new_relation_shell(stable_relation_id("na", "PART_OF_EVENT", "nb"),
                              "na", "PART_OF_EVENT", "nb", NOW,
                              relation_class="LINEAGE", source_stage="test")
    relations_by_id = {rel["relation_id"]: rel}
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        exporter.export_vault({"na": note_a, "nb": note_b}, tmp, relations_by_id)
        broken = exporter.check_broken_internal_links({"na": note_a, "nb": note_b}, tmp)
        assert broken == []
        md_a = (Path(tmp) / "02_FACTS" / "na.md").read_text(encoding="utf-8")
        assert "[[nb]]" in md_a
        assert "PART_OF_EVENT" in md_a


def test_broken_internal_link_detection_catches_dangling_link():
    import exporter
    import tempfile
    note_a = new_atomic_note_shell("na2", "FACT", "t", "s", NOW)
    with tempfile.TemporaryDirectory() as tmp:
        exporter.export_vault({"na2": note_a}, tmp)
        # simulate a stray link to a note that was never exported
        p = Path(tmp) / "02_FACTS" / "na2.md"
        p.write_text(p.read_text(encoding="utf-8") + "\n- [[does_not_exist]]\n", encoding="utf-8")
        broken = exporter.check_broken_internal_links({"na2": note_a}, tmp)
        assert broken == [("na2", "does_not_exist")]
