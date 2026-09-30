#!/usr/bin/env python3
# PHASE M.1 — GAP B remediation: pattern_layer source-independence gate.
# SYNTHETIC VERIFIED ONLY (not REAL CORPUS VERIFIED): real pattern count is currently 0
# (0 changes -> 0 pattern candidates), so there is nothing in the real corpus to demonstrate
# this gate against. These tests build synthetic documents/events/changes in an isolated
# temp directory (never touching intel/pattern_layer/*.json or any other real Stage output)
# to prove the wiring/mechanics: run_pilot.run() -> candidate_generation -> the new
# source_independence_gate -> operator_brain/source_independence.py (adapted, not
# reimplemented). No threshold is lowered anywhere in this file.
import sys
import tempfile
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAYER_DIR = HERE.parent
sys.path.insert(0, str(LAYER_DIR))

from run_pilot import run  # noqa: E402
import source_independence_gate as sig  # noqa: E402


def _change(change_id, entities, domains, event_ids, direction="EXPANDING", status="STABLE"):
    return {
        "change_id": change_id, "change_name": f"{change_id} 변화", "direction": direction,
        "status": status, "override_status": "AUTO_CANDIDATE",
        "event_count": len(event_ids), "entity_diversity": len(entities),
        "domain_diversity": len(domains), "evidence_strength": 5, "change_confidence": "MEDIUM",
        "supporting_event_ids": event_ids, "contradicting_event_ids": [],
        "entities": entities, "domains": domains, "topics": domains,
        "first_seen": "2026-09-27", "last_seen": "2026-09-29",
        "updated_at": "2026-09-29T00:00:00+00:00",
    }


def _event(event_id, doc_ids):
    return {"event_id": event_id, "related_document_ids": doc_ids}


def _doc(document_id, canonical_url):
    return {"document_id": document_id, "canonical_url": canonical_url}


def _isolated_dir():
    d = Path(tempfile.mkdtemp(prefix="pattern_layer_sig_test_"))
    return d


# ---------------------------------------------------------------------------
# A. 10 fixture records all derived from the same canonical source -> must NOT behave like
#    10 independent confirmations.
# ---------------------------------------------------------------------------
def test_a_ten_changes_same_canonical_url_collapse_to_one_family():
    documents_by_id = {}
    events_by_id = {}
    changes = {}
    for i in range(10):
        cid, eid, did = f"chg_{i}", f"evt_{i}", f"doc_{i}"
        documents_by_id[did] = _doc(did, "https://same-source.example.com/the-article")
        events_by_id[eid] = _event(eid, [did])
        changes[cid] = _change(cid, ["EntityA"], ["PRODUCT_RELEASE"], [eid])

    change_ids = list(changes.keys())
    count = sig.independent_evidence_count(change_ids, changes, documents_by_id, events_by_id)
    assert count == 1, f"expected all 10 to collapse into 1 evidence family, got {count}"

    # And the gate must reject this as pattern evidence at the real MIN_INDEPENDENT_CHANGES
    # threshold (2), even though the raw change_id count (10) would clear it.
    assert sig.passes_independence_gate(change_ids, changes, documents_by_id, events_by_id,
                                         min_independent=2) is False


# ---------------------------------------------------------------------------
# B. Multiple genuinely independent fixture sources -> may contribute (subject to all other
#    unchanged gates).
# ---------------------------------------------------------------------------
def test_b_genuinely_independent_sources_are_not_collapsed():
    documents_by_id = {
        "doc_1": _doc("doc_1", "https://outlet-one.example.com/a"),
        "doc_2": _doc("doc_2", "https://outlet-two.example.com/b"),
        "doc_3": _doc("doc_3", "https://outlet-three.example.com/c"),
    }
    events_by_id = {
        "evt_1": _event("evt_1", ["doc_1"]),
        "evt_2": _event("evt_2", ["doc_2"]),
        "evt_3": _event("evt_3", ["doc_3"]),
    }
    changes = {
        "chg_1": _change("chg_1", ["EntityA"], ["PRODUCT_RELEASE"], ["evt_1"]),
        "chg_2": _change("chg_2", ["EntityB"], ["PRODUCT_RELEASE"], ["evt_2"]),
        "chg_3": _change("chg_3", ["EntityC"], ["PRODUCT_RELEASE"], ["evt_3"]),
    }
    change_ids = list(changes.keys())
    count = sig.independent_evidence_count(change_ids, changes, documents_by_id, events_by_id)
    assert count == 3
    assert sig.passes_independence_gate(change_ids, changes, documents_by_id, events_by_id,
                                         min_independent=2) is True


# ---------------------------------------------------------------------------
# C. Provenance UNKNOWN -> must not silently become INDEPENDENT.
# ---------------------------------------------------------------------------
def test_c_unknown_provenance_does_not_silently_collapse_or_inflate():
    # No canonical_url at all on either document -> pairwise_status has no url to compare and
    # no reports_on match -> falls through to LIKELY_INDEPENDENT/UNKNOWN, never INDEPENDENT
    # being manufactured from nothing, and never unioned into a shared family.
    documents_by_id = {
        "doc_1": {"document_id": "doc_1", "canonical_url": None},
        "doc_2": {"document_id": "doc_2", "canonical_url": None},
    }
    events_by_id = {
        "evt_1": _event("evt_1", ["doc_1"]),
        "evt_2": _event("evt_2", ["doc_2"]),
    }
    changes = {
        "chg_1": _change("chg_1", ["EntityA"], ["PRODUCT_RELEASE"], ["evt_1"]),
        "chg_2": _change("chg_2", ["EntityB"], ["PRODUCT_RELEASE"], ["evt_2"]),
    }
    change_ids = list(changes.keys())
    result = sig.independence_families(change_ids, changes, documents_by_id, events_by_id)
    assert result["overall_status"] != "INDEPENDENT" or result["evidence_family_count"] == 2
    # Critically: unresolved provenance must not be silently treated as a single confirmed
    # independent family collapse in either direction - families count must equal the raw
    # change count here (no fabricated grouping AND no fabricated certainty of independence).
    assert result["evidence_family_count"] == 2


def test_c_missing_document_entirely_is_not_found_and_stays_unknown():
    # A change whose supporting event references a document_id that is not in documents.json
    # at all (broken provenance) must never be treated as INDEPENDENT by fabrication.
    documents_by_id = {}  # nothing resolvable
    events_by_id = {"evt_1": _event("evt_1", ["doc_missing"]), "evt_2": _event("evt_2", ["doc_missing_2"])}
    changes = {
        "chg_1": _change("chg_1", ["EntityA"], ["PRODUCT_RELEASE"], ["evt_1"]),
        "chg_2": _change("chg_2", ["EntityB"], ["PRODUCT_RELEASE"], ["evt_2"]),
    }
    change_ids = list(changes.keys())
    result = sig.independence_families(change_ids, changes, documents_by_id, events_by_id)
    assert result["overall_status"] == "UNKNOWN"
    assert result["evidence_family_count"] == 2  # not collapsed, not fabricated as confirmed


# ---------------------------------------------------------------------------
# D. REPORTS_ON relationships: if present, respect them; if absent, do not fabricate shared
#    origin.
# ---------------------------------------------------------------------------
def test_d_reports_on_pair_causes_collapse_when_present():
    documents_by_id = {
        "doc_1": _doc("doc_1", "https://outlet-a.example.com/x"),
        "doc_2": _doc("doc_2", "https://outlet-b.example.com/y"),
    }
    events_by_id = {
        "evt_1": _event("evt_1", ["doc_1"]),
        "evt_2": _event("evt_2", ["doc_2"]),
    }
    changes = {
        "chg_1": _change("chg_1", ["EntityA"], ["PRODUCT_RELEASE"], ["evt_1"]),
        "chg_2": _change("chg_2", ["EntityB"], ["PRODUCT_RELEASE"], ["evt_2"]),
    }
    change_ids = list(changes.keys())
    reports_on_pairs = {frozenset(("doc_1", "doc_2"))}
    count = sig.independent_evidence_count(change_ids, changes, documents_by_id, events_by_id,
                                            reports_on_pairs=reports_on_pairs)
    assert count == 1


def test_d_no_reports_on_data_does_not_fabricate_shared_origin():
    documents_by_id = {
        "doc_1": _doc("doc_1", "https://outlet-a.example.com/x"),
        "doc_2": _doc("doc_2", "https://outlet-b.example.com/y"),
    }
    events_by_id = {
        "evt_1": _event("evt_1", ["doc_1"]),
        "evt_2": _event("evt_2", ["doc_2"]),
    }
    changes = {
        "chg_1": _change("chg_1", ["EntityA"], ["PRODUCT_RELEASE"], ["evt_1"]),
        "chg_2": _change("chg_2", ["EntityB"], ["PRODUCT_RELEASE"], ["evt_2"]),
    }
    change_ids = list(changes.keys())
    count = sig.independent_evidence_count(change_ids, changes, documents_by_id, events_by_id,
                                            reports_on_pairs=set())
    assert count == 2  # different domains, different urls -> genuinely INDEPENDENT, not collapsed


# ---------------------------------------------------------------------------
# End-to-end through run_pilot.run(): a pattern candidate that clears the raw
# MIN_INDEPENDENT_CHANGES=2 count but whose 2 changes are same-source-derived must be rejected
# (0 patterns produced), never force-promoted.
# ---------------------------------------------------------------------------
def test_e2e_same_source_candidate_is_rejected_end_to_end():
    out_dir = _isolated_dir()
    try:
        documents_by_id = {
            "doc_1": _doc("doc_1", "https://same-source.example.com/article"),
            "doc_2": _doc("doc_2", "https://same-source.example.com/article"),
        }
        events_by_id = {
            "evt_1": _event("evt_1", ["doc_1"]),
            "evt_2": _event("evt_2", ["doc_2"]),
        }
        changes = {
            "chg_1": _change("chg_1", ["EntityA"], ["PRODUCT_RELEASE"], ["evt_1"]),
            "chg_2": _change("chg_2", ["EntityB"], ["PRODUCT_RELEASE"], ["evt_2"]),
        }
        metrics, patterns = run(changes_override=changes, signals_override={}, out_dir=out_dir,
                                 documents_by_id_override=documents_by_id,
                                 events_by_id_override=events_by_id)
        assert metrics["pattern_candidates_rejected_by_source_independence_gate"] == 1
        assert metrics["patterns_created_or_updated"] == 0
        assert len(patterns) == 0
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_e2e_independent_candidate_still_creates_pattern_end_to_end():
    out_dir = _isolated_dir()
    try:
        documents_by_id = {
            "doc_1": _doc("doc_1", "https://outlet-a.example.com/x"),
            "doc_2": _doc("doc_2", "https://outlet-b.example.com/y"),
        }
        events_by_id = {
            "evt_1": _event("evt_1", ["doc_1"]),
            "evt_2": _event("evt_2", ["doc_2"]),
        }
        changes = {
            "chg_1": _change("chg_1", ["EntityA"], ["PRODUCT_RELEASE"], ["evt_1"]),
            "chg_2": _change("chg_2", ["EntityB"], ["PRODUCT_RELEASE"], ["evt_2"]),
        }
        metrics, patterns = run(changes_override=changes, signals_override={}, out_dir=out_dir,
                                 documents_by_id_override=documents_by_id,
                                 events_by_id_override=events_by_id)
        assert metrics["pattern_candidates_rejected_by_source_independence_gate"] == 0
        assert metrics["patterns_created_or_updated"] == 1
        assert len(patterns) == 1
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
