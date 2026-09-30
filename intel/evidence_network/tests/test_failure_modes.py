# PHASE M.5E-2 -- regression-protection tests for spec failure modes 1, 2, 9, 10, 12, 13, 14, 15.
#
# Loaded modules are isolated via importlib (same pattern every other intel/*/tests file in this
# repo uses), one file per subprocess -- no pytest/unittest, bare assert only.
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parents[1]


def _load_isolated(path, unique_name):
    key = f"_failure_modes_isolated__{unique_name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


def _audit():
    return _load_isolated(INTEL_DIR / "source_diversity" / "audit.py", "audit")


def _deep_pilot():
    return _load_isolated(INTEL_DIR / "evidence_network" / "deep_pilot.py", "deep_pilot")


def _source_independence():
    return _load_isolated(INTEL_DIR / "operator_brain" / "source_independence.py", "source_independence")


def _admission_gate():
    return _load_isolated(INTEL_DIR / "evidence_admission" / "admission_gate.py", "admission_gate")


# --- Failure mode 1: 10 documents citing the same underlying origin don't produce 10
# independent evidence families. ---------------------------------------------------------------

def test_failure_mode_1_ten_same_origin_documents_are_one_family():
    audit = _audit()
    docs = {
        f"d{i}": {"document_id": f"d{i}", "canonical_url": "https://news.google.com/rss/articles/SAME_TARGET"}
        for i in range(10)
    }
    result = audit.source_family_document_counts(docs)
    assert result["evidence_family_count"] == 1
    assert result["largest_family_size"] == 10


def test_failure_mode_1_via_real_source_independence_algorithm_directly():
    """Same failure mode, proven directly against source_independence.assess_independence()
    itself (not just this repo's audit wrapper), using identical canonical_url as the real
    SHARED_ORIGIN signal."""
    si = _source_independence()
    trails = [
        (f"n{i}", [{"document_id": f"n{i}", "canonical_url": "https://x.example.com/same", "found": True}])
        for i in range(10)
    ]
    result = si.assess_independence(trails)
    assert result["evidence_family_count"] == 1


# --- Failure mode 2: a document with UNKNOWN source/origin is never counted as an independent
# source. -----------------------------------------------------------------------------------

def test_failure_mode_2_unknown_origin_document_not_counted_independent():
    audit = _audit()
    docs = {
        "known_a": {"document_id": "known_a", "canonical_url": "https://a.example.com/1"},
        "known_b": {"document_id": "known_b", "canonical_url": "https://b.example.com/1"},
        "unknown_origin": {"document_id": "unknown_origin", "canonical_url": None},
    }
    result = audit.source_family_document_counts(docs)
    assert result["unresolved_origin_count"] == 1
    # 3 distinct documents -> 3 families; the unresolved one is never silently merged into
    # (and so never falsely "corroborates") either known family.
    assert result["evidence_family_count"] == 3


def test_failure_mode_2_unresolved_trail_never_produces_shared_origin_with_a_resolved_one():
    si = _source_independence()
    resolved = {"document_id": "known", "canonical_url": "https://a.example.com/1", "found": True}
    unresolved = {"document_id": "unknown", "canonical_url": None, "found": False}
    status = si.pairwise_status(resolved, unresolved)
    assert status == "UNKNOWN"
    assert status not in ("SHARED_ORIGIN", "DERIVED_FROM_SAME_SOURCE")


# --- Failure mode 9: counterevidence, once recorded, is never silently dropped by a rerun. ----

def test_failure_mode_9_counterevidence_node_survives_a_rerun():
    dp = _deep_pilot()
    r1 = dp.deep_pilot_report()
    r2 = dp.deep_pilot_report()
    assert r1["evidence_chain"]["COUNTEREVIDENCE"] == r2["evidence_chain"]["COUNTEREVIDENCE"]
    # Whatever the status is (a real finding or an honest gap), it must be identical and present
    # both times -- never dropped from the chain on a rerun.
    assert "COUNTEREVIDENCE" in r1["evidence_chain"]
    assert "COUNTEREVIDENCE" in r2["evidence_chain"]


# --- Failure mode 10: missing/gap data is never coerced to a numeric zero that reads as "no
# effect" -- a GAP status must stay distinct from a genuine 0 count. ---------------------------

def test_failure_mode_10_gap_status_is_never_coerced_to_a_bare_zero():
    audit = _audit()
    stats = audit.statistical_source_ratio({"a": {"document_type": "NEWS"}})
    # This IS a genuine, real 0 (no statistical source exists) -- it must carry an explanatory
    # `note`, distinguishing it from a GAP status string. It must never be represented as just
    # the bare integer 0 with no context.
    assert isinstance(stats, dict)
    assert stats["count"] == 0
    assert "note" in stats

    dp = _deep_pilot()
    chain = dp.build_evidence_chain()
    stat_node = chain["STATISTICAL_CONTEXT"]
    # A GAP node must be a structured dict with an explicit GAP status string, never collapsed
    # to a plain 0/None that a caller could misread as "checked, found zero effect".
    assert stat_node["status"] == "STATISTICAL_GAP"
    assert stat_node["status"] != 0
    assert stat_node["document_id"] is None
    assert "reason" in stat_node and stat_node["reason"]


# --- Failure mode 12: documents from the same source family don't inflate a diversity count. --

def test_failure_mode_12_same_family_documents_do_not_inflate_diversity_count():
    audit = _audit()
    same_family_docs = {
        f"g{i}": {"document_id": f"g{i}", "document_type": "NEWS",
                   "canonical_url": "https://news.google.com/rss/articles/DUPLICATE_CLUSTER"}
        for i in range(5)
    }
    result = audit.source_family_document_counts(same_family_docs)
    # 5 documents, but they must never be reported as 5 independent families.
    assert result["documents_considered"] == 5
    assert result["evidence_family_count"] == 1
    assert result["evidence_family_count"] < result["documents_considered"]


# --- Failure mode 13: a candidate with weak title/topic relevance is not admitted as academic
# evidence -- reuses admission_gate.py's EXISTING checks, does not reimplement admission logic. -

def test_failure_mode_13_weak_relevance_candidate_still_fails_real_admission_checks():
    ag = _admission_gate()
    # A candidate missing the real evidentiary fields admission_gate.py's OWN checks require
    # (no provenance, no valid trusted source, no resolvable identity) must still be rejected by
    # the real, unmodified validate_candidate() -- this proves the existing M.5D gate logic
    # still holds, it does not add a new relevance-scoring layer.
    weak_candidate = {
        "source_id": "src_unknown_blog",
        "source_name": "Some Blog",
        "source_type": "OTHER",
        "canonical_url": "https://some-random-blog.example/post-1",
        "published": "2026-01-01",
        "document_type": "RESEARCH",
        "provenance_id": None,
        "retrieved_at": None,
        "rights_mode": "FULL_TEXT",
        "full_text": "some content",
    }
    result = ag.validate_candidate(weak_candidate)
    assert result["failures"], "a candidate with no trusted source and no provenance must fail admission"
    assert "SOURCE_IDENTIFIED" in result["failures"]
    decision_status, _ = ag._first_matching_rejection(result["failures"])
    assert decision_status.startswith("REJECTED_")


# --- Failure mode 14: running new audit code never mutates documents.json (byte-identical
# before/after). -------------------------------------------------------------------------------

def test_failure_mode_14_audit_and_deep_pilot_never_mutate_documents_json():
    real_docs_path = INTEL_DIR / "documents.json"
    before = real_docs_path.read_text(encoding="utf-8")

    audit = _audit()
    dp = _deep_pilot()
    audit.source_diversity_report()
    dp.deep_pilot_report()

    after = real_docs_path.read_text(encoding="utf-8")
    assert before == after


# --- Failure mode 15: rerunning audit/pilot code twice on the same corpus produces identical
# results (pure function idempotency). ----------------------------------------------------------

def test_failure_mode_15_audit_report_is_idempotent():
    audit = _audit()
    docs = audit.load_documents()
    r1 = audit.source_diversity_report(docs)
    r2 = audit.source_diversity_report(docs)
    assert r1 == r2


def test_failure_mode_15_deep_pilot_report_is_idempotent():
    dp = _deep_pilot()
    docs = dp.load_documents()
    r1 = dp.deep_pilot_report(docs)
    r2 = dp.deep_pilot_report(docs)
    assert r1 == r2


def main():
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
