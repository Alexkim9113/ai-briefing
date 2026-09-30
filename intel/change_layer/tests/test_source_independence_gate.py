#!/usr/bin/env python3
# PHASE M.5 — Priority 1: change_layer source-independence gate.
# SYNTHETIC-SCHEMA-VERIFIED ONLY (not REAL CORPUS VERIFIED for the rejection path): the real
# corpus currently has 0 raw change candidate groups this run (its single prior candidate,
# "아모데"/OpenAI+Trump, no longer regroups because one of its two backing raw documents has
# rotated out of data/2026-*.json — a real corpus-drift finding, not a code bug), so there is
# no live candidate to exercise the gate's REJECT path against in the real corpus this round.
# These tests build synthetic events/documents in memory (never touching any real intel/*.json
# file) to prove the gate's mechanics: independence_families / independent_evidence_count /
# passes_independence_gate, reusing operator_brain/source_independence.py's union-find exactly
# as intel/pattern_layer/tests/test_source_independence_gate.py already does for the
# pattern-layer instance of this same adapter pattern. No threshold is lowered anywhere here.
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAYER_DIR = HERE.parent
sys.path.insert(0, str(LAYER_DIR))

import source_independence_gate as sig  # noqa: E402


def _event(event_id, doc_ids):
    return {"event_id": event_id, "related_document_ids": doc_ids}


def _doc(document_id, canonical_url):
    return {"document_id": document_id, "canonical_url": canonical_url}


# ---------------------------------------------------------------------------
# A. Shared-origin collapse: N events whose documents share one canonical_url must not count
#    as N independent supporting events.
# ---------------------------------------------------------------------------
def test_a_shared_origin_events_collapse_to_one_family():
    documents_by_id = {}
    events_by_id = {}
    for i in range(5):
        eid, did = f"evt_{i}", f"doc_{i}"
        documents_by_id[did] = _doc(did, "https://same-source.example.com/the-article")
        events_by_id[eid] = _event(eid, [did])

    event_ids = list(events_by_id.keys())
    count = sig.independent_evidence_count(event_ids, events_by_id, documents_by_id)
    assert count == 1, f"expected all 5 same-origin events to collapse into 1 family, got {count}"

    # Raw count (5) clears MIN_SUPPORTING_EVENTS(=2), but the gate must still reject at that
    # same threshold once collapsed to 1 independent family.
    assert sig.passes_independence_gate(event_ids, events_by_id, documents_by_id,
                                         min_independent=2) is False


def test_a_shared_origin_via_identical_document_id():
    # Two events that (incorrectly upstream) both cite the exact same document_id — must
    # collapse via SHARED_ORIGIN (document identity), not just canonical_url matching.
    documents_by_id = {"doc_x": _doc("doc_x", None)}
    events_by_id = {
        "evt_1": _event("evt_1", ["doc_x"]),
        "evt_2": _event("evt_2", ["doc_x"]),
    }
    event_ids = list(events_by_id.keys())
    count = sig.independent_evidence_count(event_ids, events_by_id, documents_by_id)
    assert count == 1


# ---------------------------------------------------------------------------
# B. Genuinely independent sources are never collapsed.
# ---------------------------------------------------------------------------
def test_b_genuinely_independent_events_are_not_collapsed():
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
    event_ids = list(events_by_id.keys())
    count = sig.independent_evidence_count(event_ids, events_by_id, documents_by_id)
    assert count == 3
    assert sig.passes_independence_gate(event_ids, events_by_id, documents_by_id,
                                         min_independent=2) is True


# ---------------------------------------------------------------------------
# C. UNKNOWN provenance must never be silently treated as INDEPENDENT (nor silently collapsed).
# ---------------------------------------------------------------------------
def test_c_unknown_provenance_is_not_treated_as_independent_or_collapsed():
    documents_by_id = {
        "doc_1": {"document_id": "doc_1", "canonical_url": None},
        "doc_2": {"document_id": "doc_2", "canonical_url": None},
    }
    events_by_id = {
        "evt_1": _event("evt_1", ["doc_1"]),
        "evt_2": _event("evt_2", ["doc_2"]),
    }
    event_ids = list(events_by_id.keys())
    result = sig.independence_families(event_ids, events_by_id, documents_by_id)
    # No fabricated grouping AND no fabricated certainty of independence: raw count preserved.
    assert result["evidence_family_count"] == 2
    assert result["overall_status"] != "INDEPENDENT"


def test_c_missing_document_entirely_stays_unknown_not_fabricated():
    documents_by_id = {}  # nothing resolvable at all
    events_by_id = {
        "evt_1": _event("evt_1", ["doc_missing_1"]),
        "evt_2": _event("evt_2", ["doc_missing_2"]),
    }
    event_ids = list(events_by_id.keys())
    result = sig.independence_families(event_ids, events_by_id, documents_by_id)
    assert result["overall_status"] == "UNKNOWN"
    assert result["evidence_family_count"] == 2  # not collapsed, not promoted to confirmed


# ---------------------------------------------------------------------------
# D. REPORTS_ON pairs: respected when present, never fabricated when absent.
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
    event_ids = list(events_by_id.keys())
    reports_on_pairs = {frozenset(("doc_1", "doc_2"))}
    count = sig.independent_evidence_count(event_ids, events_by_id, documents_by_id,
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
    event_ids = list(events_by_id.keys())
    count = sig.independent_evidence_count(event_ids, events_by_id, documents_by_id,
                                            reports_on_pairs=set())
    assert count == 2


# ---------------------------------------------------------------------------
# E. Additive-only contract: gate result is always <= raw event count, never greater.
# ---------------------------------------------------------------------------
def test_e_gate_never_increases_effective_count():
    documents_by_id = {
        "doc_1": _doc("doc_1", "https://a.example.com/1"),
        "doc_2": _doc("doc_2", "https://a.example.com/1"),  # same url as doc_1
        "doc_3": _doc("doc_3", "https://b.example.com/2"),
    }
    events_by_id = {
        "evt_1": _event("evt_1", ["doc_1"]),
        "evt_2": _event("evt_2", ["doc_2"]),
        "evt_3": _event("evt_3", ["doc_3"]),
    }
    event_ids = list(events_by_id.keys())
    count = sig.independent_evidence_count(event_ids, events_by_id, documents_by_id)
    assert count <= len(event_ids)
    assert count == 2  # evt_1/evt_2 collapse (same canonical_url), evt_3 stays separate


# ---------------------------------------------------------------------------
# F. Real-shape smoke test: run the gate against the actual real-corpus documents.json loader,
#    using the real repo's one known prior change candidate's event ids as a shape check (not
#    asserting a specific outcome number, since the real candidate group no longer forms this
#    run due to unrelated raw-data-file rotation — see module docstring).
# ---------------------------------------------------------------------------
def test_f_real_documents_loader_does_not_crash_on_real_corpus():
    documents_by_id = sig.load_documents()
    assert isinstance(documents_by_id, dict)
    assert len(documents_by_id) > 0, "real intel/documents.json should be non-empty (569 docs baseline)"
    # Real event shape smoke test using the real production_events.json.
    import json
    events_path = LAYER_DIR.parent / "event_production" / "production_events.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    event_ids = list(events.keys())
    if len(event_ids) >= 2:
        count = sig.independent_evidence_count(event_ids[:2], events, documents_by_id)
        assert count <= 2


def run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {t.__name__}: {e!r}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return failed == 0


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)
