#!/usr/bin/env python3
# PHASE 5E — 24개 Synthetic Fixture 테스트(운영자 지시 51번). 전부 tempfile.mkdtemp()로
# 격리된 out_dir/override 경로만 사용 — 실제 Production JSON은 절대 건드리지 않는다.
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAYER = HERE.parent
ROOT = LAYER.parent.parent
sys.path.insert(0, str(LAYER))
sys.path.insert(0, str(ROOT))

import pipeline  # noqa: E402
from schema import PARADOX_RULE_MATRIX  # noqa: E402
from scope import classify_pair  # noqa: E402
from assessment import build_epistemic_assessments, compute_epistemic_ceiling  # noqa: E402
from common import cap_confidence  # noqa: E402

VALID_TYPES = ("STRUCTURAL_CHANGE", "DRIVER", "DEPENDENCY", "CONTROL", "POWER_SHIFT",
               "VALUE_SHIFT", "SCARCITY_SHIFT", "BOTTLENECK", "STRUCTURAL_ANALYSIS")


def full_target_index(**overrides):
    idx = {t: set() for t in VALID_TYPES}
    for k, v in overrides.items():
        idx[k] = set(v)
    return idx


def claim(target_type="STRUCTURAL_CHANGE", target_id="sc1", **fields):
    base = {"type": "CLAIM", "target_object_type": target_type, "target_object_id": target_id,
            "subject": "s", "object": "o", "domain": "TECH", "population": "ALL",
            "time_period": "2026", "context": "c", "measurement": "m", "relation": "r",
            "dimension": "ACCESS", "direction": "UP", "evidence_ids": ["e1"]}
    base.update(fields)
    return base


def isolated_dir():
    d = Path(tempfile.mkdtemp(prefix="epistemic_test_"))
    overrides_path = d / "overrides.json"
    overrides_path.write_text(json.dumps(
        {c: {"human_confirmed": [], "human_rejected": []} for c in
         ("counter_evidence", "contradictions", "tensions", "paradox_candidates", "uncertainties",
          "assumptions", "falsifiers", "evidence_gaps", "alternative_explanations",
          "view_revisions", "epistemic_assessments")}), encoding="utf-8")
    return d, overrides_path


def run_isolated(records, target_index=None, out_dir=None, overrides_path=None, ceiling_records=None):
    if out_dir is None:
        out_dir, overrides_path = isolated_dir()
    ti = target_index if target_index is not None else full_target_index(STRUCTURAL_CHANGE=["sc1", "sc2"])
    metrics, collections, revisions, assessments = pipeline.run(
        target_index_override=ti, evidence_records_override=records, out_dir=out_dir,
        overrides_path=overrides_path, ceiling_records_override=ceiling_records or [])
    return out_dir, overrides_path, metrics, collections, revisions, assessments


def test_01_direct_contradiction():
    a = claim(target_id="sc1", direction="UP")
    b = claim(target_id="sc2", direction="DOWN")
    _, _, m, coll, _, _ = run_isolated([a, b])
    assert m["contradictions_total"] == 1
    ctd = next(iter(coll["contradictions"].values()))
    assert ctd["conflict_type"] == "DIRECT_CONTRADICTION"
    print("test_01 OK")


def test_02_temporal_guard():
    a = claim(target_id="sc1", direction="UP", time_period="2026")
    b = claim(target_id="sc2", direction="DOWN", time_period="2028")
    _, _, m, coll, _, _ = run_isolated([a, b])
    assert m["contradictions_total"] == 1
    ctd = next(iter(coll["contradictions"].values()))
    assert ctd["conflict_type"] == "TEMPORAL_REVERSAL_CANDIDATE"
    assert not any(c["conflict_type"] == "DIRECT_CONTRADICTION" for c in coll["contradictions"].values())
    print("test_02 OK")


def test_03_geographic_guard():
    a = claim(target_id="sc1", direction="UP", domain="US")
    b = claim(target_id="sc2", direction="DOWN", domain="EU")
    _, _, m, coll, _, _ = run_isolated([a, b])
    ctd = next(iter(coll["contradictions"].values()))
    assert ctd["conflict_type"] == "NO_DIRECT_CONTRADICTION"
    print("test_03 OK")


def test_04_population_guard():
    a = claim(target_id="sc1", direction="UP", population="ENTERPRISE")
    b = claim(target_id="sc2", direction="DOWN", population="SME")
    _, _, m, coll, _, _ = run_isolated([a, b])
    ctd = next(iter(coll["contradictions"].values()))
    assert ctd["conflict_type"] == "NO_DIRECT_CONTRADICTION"
    print("test_04 OK")


def test_05_tension_not_contradiction():
    a = claim(target_id="sc1", dimension="ACCESS", direction="UP")
    b = claim(target_id="sc2", dimension="DEPENDENCY", direction="UP")
    _, _, m, coll, _, _ = run_isolated([a, b])
    assert m["tensions_total"] == 1
    assert m["contradictions_total"] == 0
    print("test_05 OK")


def test_06_paradox_candidate():
    a = claim(target_id="sc1", dimension="ACCESS", direction="UP")
    b = claim(target_id="sc2", dimension="CONTROL", direction="UP")
    _, _, m, coll, _, _ = run_isolated([a, b])
    assert m["paradox_candidates_total"] == 1
    pdx = next(iter(coll["paradox_candidates"].values()))
    assert pdx["paradox_type"] == "ACCESS_CONTROL_PARADOX"
    assert m["contradictions_total"] == 0
    print("test_06 OK")


def test_07_counter_evidence_preserves_target():
    ti = full_target_index(SCARCITY_SHIFT=["scar1"])
    rec = {"type": "COUNTER_EVIDENCE", "target_object_type": "SCARCITY_SHIFT", "target_object_id": "scar1",
           "evidence_type": "OPEN_INTEROPERABLE_API", "relationship": "WEAKENS", "scope": "GLOBAL",
           "evidence_ids": ["e1"]}
    out_dir, overrides_path, m, coll, _, _ = run_isolated([rec], target_index=ti)
    assert m["counter_evidence_total"] == 1
    # 대상 객체(5D) 파일에는 이 Layer가 전혀 쓰지 않는다 — 타겟 삭제 없음을 파일 부재로 확인
    assert not (out_dir / "scarcity_shifts.json").exists()
    print("test_07 OK")


def test_08_missing_evidence_not_counter_evidence():
    ti = full_target_index(STRUCTURAL_CHANGE=["sc1"])
    gap = {"type": "EVIDENCE_GAP", "target_object_type": "STRUCTURAL_CHANGE", "target_object_id": "sc1",
           "gap_type": "SOURCE_INDEPENDENCE", "missing_evidence_type": "ORIGINAL_SOURCE_LINEAGE",
           "why_needed_code": "INDEPENDENCE_UNKNOWN", "priority": "HIGH"}
    unc = {"type": "UNCERTAINTY", "target_object_type": "STRUCTURAL_CHANGE", "target_object_id": "sc1",
           "uncertainty_type": "SOURCE_INDEPENDENCE_UNKNOWN", "description_code": "NO_LINEAGE", "scope": "sc1"}
    _, _, m, coll, _, _ = run_isolated([gap, unc], target_index=ti)
    assert m["evidence_gaps_total"] == 1
    assert m["uncertainties_total"] == 1
    assert m["counter_evidence_total"] == 0  # Missing Evidence != Counter Evidence
    print("test_08 OK")


def test_09_causality_uncertain():
    ti = full_target_index(STRUCTURAL_CHANGE=["sc1"])
    unc = {"type": "UNCERTAINTY", "target_object_type": "STRUCTURAL_CHANGE", "target_object_id": "sc1",
           "uncertainty_type": "CAUSALITY_UNCERTAIN", "description_code": "CORRELATION_ONLY", "scope": "sc1"}
    _, _, m, coll, _, _ = run_isolated([unc], target_index=ti)
    assert m["uncertainties_total"] == 1
    obj = next(iter(coll["uncertainties"].values()))
    assert obj["uncertainty_type"] == "CAUSALITY_UNCERTAIN"
    print("test_09 OK")


def test_10_alternative_explanation_preserved():
    ti = full_target_index(STRUCTURAL_CHANGE=["sc1"])
    a = {"type": "ALTERNATIVE_EXPLANATION", "target_object_type": "STRUCTURAL_CHANGE", "target_object_id": "sc1",
         "explanation_code_or_statement": "PERMISSION_BOTTLENECK", "supporting_evidence_ids": ["e1"]}
    b = {"type": "ALTERNATIVE_EXPLANATION", "target_object_type": "STRUCTURAL_CHANGE", "target_object_id": "sc1",
         "explanation_code_or_statement": "TRUST_PROBLEM", "supporting_evidence_ids": ["e2"]}
    _, _, m, coll, _, _ = run_isolated([a, b], target_index=ti)
    assert m["alternative_explanations_total"] == 2
    print("test_10 OK")


def test_11_falsifier_untested():
    ti = full_target_index(STRUCTURAL_CHANGE=["sc1"])
    f = {"type": "FALSIFIER", "target_object_type": "STRUCTURAL_CHANGE", "target_object_id": "sc1",
         "condition_type": "PERMISSION_OPENED", "condition": "permission API becomes open/interoperable",
         "observable_indicator": "public API docs", "required_scope": "sc1"}
    _, _, m, coll, _, _ = run_isolated([f], target_index=ti)
    obj = next(iter(coll["falsifiers"].values()))
    assert obj["status"] == "UNTESTED"
    print("test_11 OK")


def test_12_falsifier_observed_triggers_view_revision():
    ti = full_target_index(STRUCTURAL_CHANGE=["sc1"])
    out_dir, overrides_path = isolated_dir()
    f = {"type": "FALSIFIER", "target_object_type": "STRUCTURAL_CHANGE", "target_object_id": "sc1",
         "condition_type": "PERMISSION_OPENED", "condition": "permission API becomes open",
         "observable_indicator": "public API docs", "required_scope": "sc1"}
    run_isolated([f], target_index=ti, out_dir=out_dir, overrides_path=overrides_path)
    f_observed = dict(f, observed_evidence_ids=["e_observed"])
    _, _, m, coll, revisions, _ = run_isolated([f_observed], target_index=ti, out_dir=out_dir,
                                                overrides_path=overrides_path)
    obj = next(iter(coll["falsifiers"].values()))
    assert obj["status"] == "OBSERVED"
    assert any(r["revision_reason_type"] == "FALSIFIER_OBSERVED" for r in revisions.values())
    print("test_12 OK")


def test_13_epistemic_ceiling():
    targets = {("STRUCTURAL_CHANGE", "sc1"): "HIGH"}
    collections = {"counter_evidence": {}, "contradictions": {}, "tensions": {}, "paradox_candidates": {},
                   "uncertainties": {}, "assumptions": {}, "falsifiers": {}, "evidence_gaps": {},
                   "alternative_explanations": {}}
    ceiling_records = [{"target_object_type": "STRUCTURAL_CHANGE", "target_object_id": "sc1",
                        "upstream_confidence": "MEDIUM", "source_independence_known": True}]
    assessments = build_epistemic_assessments(targets, collections, ceiling_records)
    a = next(iter(assessments.values()))
    assert a["epistemic_ceiling"] == "MEDIUM"
    assert a["confidence_after"] != "HIGH"
    assert cap_confidence("HIGH", "MEDIUM") == "MEDIUM"
    print("test_13 OK")


def test_14_human_reject_persists():
    ti = full_target_index(STRUCTURAL_CHANGE=["sc1", "sc2"])
    out_dir, overrides_path = isolated_dir()
    a = claim(target_id="sc1", direction="UP")
    b = claim(target_id="sc2", direction="DOWN")
    _, _, _, coll, _, _ = run_isolated([a, b], target_index=ti, out_dir=out_dir, overrides_path=overrides_path)
    cid = next(iter(coll["contradictions"].keys()))
    overrides = json.loads(overrides_path.read_text(encoding="utf-8"))
    overrides["contradictions"]["human_rejected"].append(cid)
    overrides_path.write_text(json.dumps(overrides), encoding="utf-8")
    for _ in range(3):
        _, _, _, coll, _, _ = run_isolated([a, b], target_index=ti, out_dir=out_dir, overrides_path=overrides_path)
        assert coll["contradictions"][cid]["status"] == "HUMAN_REJECTED"
        assert coll["contradictions"][cid]["override_status"] == "HUMAN_REJECTED"
    print("test_14 OK")


def test_15_resolution():
    ti = full_target_index(STRUCTURAL_CHANGE=["sc1"])
    out_dir, overrides_path = isolated_dir()
    gap = {"type": "EVIDENCE_GAP", "target_object_type": "STRUCTURAL_CHANGE", "target_object_id": "sc1",
           "gap_type": "SOURCE_INDEPENDENCE", "missing_evidence_type": "ORIGINAL_SOURCE_LINEAGE",
           "why_needed_code": "INDEPENDENCE_UNKNOWN", "priority": "HIGH"}
    _, _, _, coll, _, _ = run_isolated([gap], target_index=ti, out_dir=out_dir, overrides_path=overrides_path)
    gid = next(iter(coll["evidence_gaps"].keys()))
    assert coll["evidence_gaps"][gid]["status"] == "OPEN"
    gap_resolved = dict(gap, status_override="FILLED")
    _, _, _, coll, _, _ = run_isolated([gap_resolved], target_index=ti, out_dir=out_dir, overrides_path=overrides_path)
    assert coll["evidence_gaps"][gid]["status"] == "FILLED"
    assert len(coll["evidence_gaps"][gid]["history"]) >= 2
    print("test_15 OK")


def test_16_reopen():
    ti = full_target_index(STRUCTURAL_CHANGE=["sc1"])
    out_dir, overrides_path = isolated_dir()
    unc = {"type": "UNCERTAINTY", "target_object_type": "STRUCTURAL_CHANGE", "target_object_id": "sc1",
           "uncertainty_type": "SOURCE_INDEPENDENCE_UNKNOWN", "description_code": "NO_LINEAGE", "scope": "sc1"}
    run_isolated([unc], target_index=ti, out_dir=out_dir, overrides_path=overrides_path)
    unc_resolved = dict(unc, status_override="RESOLVED")
    _, _, _, coll, _, _ = run_isolated([unc_resolved], target_index=ti, out_dir=out_dir, overrides_path=overrides_path)
    uid = next(iter(coll["uncertainties"].keys()))
    assert coll["uncertainties"][uid]["status"] == "RESOLVED"
    unc_reopened = dict(unc, status_override="REOPENED")
    _, _, _, coll, _, _ = run_isolated([unc_reopened], target_index=ti, out_dir=out_dir, overrides_path=overrides_path)
    assert coll["uncertainties"][uid]["status"] == "REOPENED"
    assert len(coll["uncertainties"][uid]["history"]) >= 3
    print("test_16 OK")


def test_17_unknown_not_false():
    a = claim(target_id="sc1", direction="UP")
    b = dict(a)
    b.pop("time_period")  # 시간 정보 없음 = UNKNOWN, False 아님
    b["target_object_id"] = "sc2"
    b["direction"] = "DOWN"
    flags = classify_pair(a, b)[2]
    assert flags["temporal_match"] is None  # False가 아니라 None(unknown)
    print("test_17 OK")


def test_18_idempotency():
    ti = full_target_index(STRUCTURAL_CHANGE=["sc1", "sc2"])
    out_dir, overrides_path = isolated_dir()
    a = claim(target_id="sc1", direction="UP")
    b = claim(target_id="sc2", direction="DOWN")
    _, _, _, coll1, _, _ = run_isolated([a, b], target_index=ti, out_dir=out_dir, overrides_path=overrides_path)
    ids1 = sorted(coll1["contradictions"].keys())
    _, _, _, coll2, _, _ = run_isolated([a, b], target_index=ti, out_dir=out_dir, overrides_path=overrides_path)
    ids2 = sorted(coll2["contradictions"].keys())
    assert ids1 == ids2
    print("test_18 OK")


def test_19_evidence_lineage():
    ti = full_target_index(SCARCITY_SHIFT=["scar1"])
    ce = {"type": "COUNTER_EVIDENCE", "target_object_type": "SCARCITY_SHIFT", "target_object_id": "scar1",
          "evidence_type": "OPEN_API", "relationship": "WEAKENS", "scope": "GLOBAL", "evidence_ids": ["e1"]}
    _, _, m, coll, _, assessments = run_isolated([ce], target_index=ti)
    a = next(iter(assessments.values()))
    assert a["target_object_type"] == "SCARCITY_SHIFT" and a["target_object_id"] == "scar1"
    assert a["counter_evidence_count"] == 1
    print("test_19 OK")


def test_20_empty_state():
    ti = full_target_index()  # 5D 대상 객체 0건
    _, _, m, coll, revisions, assessments = run_isolated([], target_index=ti)
    for name in ("counter_evidence_total", "contradictions_total", "tensions_total",
                 "paradox_candidates_total", "uncertainties_total", "assumptions_total",
                 "falsifiers_total", "evidence_gaps_total", "alternative_explanations_total",
                 "view_revisions_total", "epistemic_assessments_total"):
        assert m[name] == 0, name
    print("test_20 OK")


def test_21_missing_not_counter():
    ti = full_target_index(STRUCTURAL_CHANGE=["sc1"])
    gap = {"type": "EVIDENCE_GAP", "target_object_type": "STRUCTURAL_CHANGE", "target_object_id": "sc1",
           "gap_type": "PRIMARY_EVIDENCE", "missing_evidence_type": "PRIMARY_SOURCE",
           "why_needed_code": "NO_PRIMARY", "priority": "HIGH"}
    _, _, m, coll, _, _ = run_isolated([gap], target_index=ti)
    assert m["evidence_gaps_total"] == 1
    assert m["counter_evidence_total"] == 0
    print("test_21 OK")


def test_22_paradox_not_contradiction():
    a = claim(target_id="sc1", dimension="ACCESS", direction="UP")
    b = claim(target_id="sc2", dimension="CONTROL", direction="UP")
    _, _, m, coll, _, _ = run_isolated([a, b])
    assert m["paradox_candidates_total"] == 1
    assert m["contradictions_total"] == 0
    print("test_22 OK")


def test_23_confidence_vs_uncertainty_coexist():
    ti = full_target_index(STRUCTURAL_CHANGE=["sc1"])
    unc = {"type": "UNCERTAINTY", "target_object_type": "STRUCTURAL_CHANGE", "target_object_id": "sc1",
           "uncertainty_type": "CAUSALITY_UNCERTAIN", "description_code": "CORRELATION_ONLY", "scope": "sc1"}
    targets = {("STRUCTURAL_CHANGE", "sc1"): "HIGH"}
    _, _, m, coll, _, _ = run_isolated([unc], target_index=ti)
    collections = {"counter_evidence": {}, "contradictions": {}, "tensions": {}, "paradox_candidates": {},
                   "uncertainties": coll["uncertainties"], "assumptions": {}, "falsifiers": {},
                   "evidence_gaps": {}, "alternative_explanations": {}}
    assessments = build_epistemic_assessments(targets, collections, [])
    a = next(iter(assessments.values()))
    assert a["confidence_before"] == "HIGH"
    assert len(a["uncertainty_ids"]) == 1  # HIGH confidence와 CAUSALITY_UNCERTAIN 공존 가능
    print("test_23 OK")


def test_24_source_count_vs_independence():
    fp_metrics = {"independent_source_count": None}  # pipeline이 항상 이렇게 채움(추정 금지)
    assert fp_metrics["independent_source_count"] is None
    ti = full_target_index(SCARCITY_SHIFT=["scar1"])
    ce = {"type": "COUNTER_EVIDENCE", "target_object_type": "SCARCITY_SHIFT", "target_object_id": "scar1",
          "evidence_type": "OPEN_API", "relationship": "WEAKENS", "scope": "GLOBAL", "evidence_ids": ["e1", "e2"]}
    out_dir, _, m, coll, _, _ = run_isolated([ce], target_index=ti)
    fact_packs = json.loads((out_dir / "epistemic_fact_packs.json").read_text(encoding="utf-8"))
    fp = next(iter(fact_packs.values()))
    assert fp["independence_metrics"]["independent_source_count"] is None
    print("test_24 OK")


def run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
    print(f"\n{len(fns)}/{len(fns)} PASSED")


if __name__ == "__main__":
    run_all()
