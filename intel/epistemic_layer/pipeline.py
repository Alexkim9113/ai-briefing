#!/usr/bin/env python3
# PHASE 5E — CONTRADICTION/COUNTER-EVIDENCE/UNCERTAINTY INTELLIGENCE Pipeline.
# intel/structural_analysis_layer/*.json, intel/structural_change_layer/structural_changes.json을
# 읽기 전용으로만 쓴다. Public/Evidence/Fact/Event/Change/Signal/Pattern/Structural
# Change/Structural Analysis 전부 미변경.
#
# 이 Layer도 원문에서 Contradiction/Assumption 등을 자동 추출하는 NLP/LLM 파이프라인을
# 갖지 않는다(운영자 지시 48번: 이번 Foundation은 LLM 호출 금지). 따라서 후보 생성은
# 명시적으로 제공된 Evidence/Claim Record만 입력으로 받는다. 실제 Production에는 이런
# Record 소스가 아직 없고(=Structural Analysis Objects도 0이므로) 이 Layer의 실제
# 산출물은 항상 0이다 — 이것이 정상이다(운영자 지시 39~40번).
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

from counter_evidence import generate_counter_evidence_candidates  # noqa: E402
from contradiction import generate_contradiction_candidates  # noqa: E402
from tension import generate_tension_candidates  # noqa: E402
from paradox import generate_paradox_candidates  # noqa: E402
from uncertainty import generate_uncertainty_candidates  # noqa: E402
from assumption import generate_assumption_candidates  # noqa: E402
from falsifier import generate_falsifier_candidates  # noqa: E402
from evidence_gap import generate_evidence_gap_candidates  # noqa: E402
from alternative_explanation import generate_alternative_explanation_candidates  # noqa: E402
from revision import generate_view_revision_candidates  # noqa: E402
from assessment import build_epistemic_assessments  # noqa: E402
from fact_pack import build_epistemic_fact_pack  # noqa: E402
from overrides import load_overrides, apply_overrides  # noqa: E402
from memory import upsert_collection  # noqa: E402
from metrics import count_by  # noqa: E402

STRUCTURAL_ANALYSIS_DIR = ROOT / "intel" / "structural_analysis_layer"
STRUCTURAL_CHANGE_DIR = ROOT / "intel" / "structural_change_layer"
EVIDENCE_INPUT_PATH = HERE / "epistemic_evidence_input.json"

COLLECTION_NAMES = ("counter_evidence", "contradictions", "tensions", "paradox_candidates",
                    "uncertainties", "assumptions", "falsifiers", "evidence_gaps",
                    "alternative_explanations")

_ID_FIELD = {
    "counter_evidence": "counter_evidence_id", "contradictions": "contradiction_id",
    "tensions": "tension_id", "paradox_candidates": "paradox_candidate_id",
    "uncertainties": "uncertainty_id", "assumptions": "assumption_id",
    "falsifiers": "falsifier_id", "evidence_gaps": "evidence_gap_id",
    "alternative_explanations": "alternative_explanation_id",
}

_TARGET_FILE = {
    "STRUCTURAL_ANALYSIS": "structural_analyses.json", "DRIVER": "drivers.json",
    "DEPENDENCY": "dependencies.json", "CONTROL": "controls.json",
    "POWER_SHIFT": "power_shifts.json", "VALUE_SHIFT": "value_shifts.json",
    "SCARCITY_SHIFT": "scarcity_shifts.json", "BOTTLENECK": "bottlenecks.json",
}


def load_target_index(structural_analysis_override=None, structural_changes_override=None):
    """5D/5C 대상 객체의 id 집합을 타입별로 모은다 — 5D 대상이 실제 존재할 때만 5E 객체를
    만들 수 있게 하기 위함(Acceptance: 5D 대상 없이 5E 객체 없음)."""
    index = {t: set() for t in list(_TARGET_FILE.keys()) + ["STRUCTURAL_CHANGE"]}
    if structural_changes_override is not None:
        index["STRUCTURAL_CHANGE"] = set(structural_changes_override.keys())
    else:
        path = STRUCTURAL_CHANGE_DIR / "structural_changes.json"
        if path.exists():
            index["STRUCTURAL_CHANGE"] = set(json.loads(path.read_text(encoding="utf-8")).keys())

    if structural_analysis_override is not None:
        for target_type, ids in structural_analysis_override.items():
            index[target_type] = set(ids)
        return index

    for target_type, filename in _TARGET_FILE.items():
        path = STRUCTURAL_ANALYSIS_DIR / filename
        if path.exists():
            index[target_type] = set(json.loads(path.read_text(encoding="utf-8")).keys())
    return index


def load_evidence_records(path=EVIDENCE_INPUT_PATH):
    """실제 Production에는 아직 이 Evidence/Claim Record 소스가 없다(운영자 지시 48번:
    LLM으로 자동 채우지 않음). 파일이 없으면 빈 리스트 — 0건이 정직한 기본값이다."""
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _load_existing(out_dir, name):
    p = out_dir / f"{name}.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _target_objects_from(collections):
    targets = {}
    for coll in collections.values():
        for obj in coll.values():
            for tt_key, tid_key in (("target_object_type", "target_object_id"),
                                     ("object_a_type", "object_a_id"), ("object_b_type", "object_b_id")):
                tt, tid = obj.get(tt_key), obj.get(tid_key)
                if tt and tid:
                    targets.setdefault((tt, tid), None)
    return targets


def run(target_index_override=None, evidence_records_override=None, out_dir=None,
        overrides_path=None, ceiling_records_override=None):
    """*_override/out_dir/overrides_path는 synthetic fixture 전용 격리 경로."""
    out_dir = Path(out_dir) if out_dir else HERE
    target_index = target_index_override if target_index_override is not None else load_target_index()
    evidence_records = (evidence_records_override if evidence_records_override is not None
                         else load_evidence_records())
    ceiling_records = (ceiling_records_override if ceiling_records_override is not None
                       else [r for r in evidence_records if r.get("type") == "EPISTEMIC_CEILING"])

    existing = {name: _load_existing(out_dir, name) for name in COLLECTION_NAMES}

    counter_evidence_new = generate_counter_evidence_candidates(evidence_records, target_index)
    contradictions_new = generate_contradiction_candidates(evidence_records, target_index)
    tensions_new = generate_tension_candidates(evidence_records, target_index)
    paradoxes_new = generate_paradox_candidates(evidence_records, target_index)
    uncertainties_new = generate_uncertainty_candidates(evidence_records, target_index)
    assumptions_new = generate_assumption_candidates(evidence_records, target_index)
    falsifiers_new = generate_falsifier_candidates(evidence_records, target_index, existing["falsifiers"])
    evidence_gaps_new = generate_evidence_gap_candidates(evidence_records, target_index)
    alt_explanations_new = generate_alternative_explanation_candidates(evidence_records, target_index)

    overrides = load_overrides(Path(overrides_path)) if overrides_path else load_overrides()

    new_by_name = {
        "counter_evidence": counter_evidence_new, "contradictions": contradictions_new,
        "tensions": tensions_new, "paradox_candidates": paradoxes_new,
        "uncertainties": uncertainties_new, "assumptions": assumptions_new,
        "falsifiers": falsifiers_new, "evidence_gaps": evidence_gaps_new,
        "alternative_explanations": alt_explanations_new,
    }

    collections = {}
    for name in COLLECTION_NAMES:
        merged = upsert_collection(existing[name], new_by_name[name])
        merged = apply_overrides(name, merged, overrides.get(name, {"human_confirmed": [], "human_rejected": []}))
        collections[name] = merged
        out_dir.joinpath(f"{name}.json").write_text(
            json.dumps(merged, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

    # View Revision — falsifiers_new/existing["falsifiers"]로 자동 OBSERVED 전이를 감지한다.
    view_revisions_new = generate_view_revision_candidates(
        evidence_records, target_index, collections["falsifiers"], existing["falsifiers"])
    existing_revisions = _load_existing(out_dir, "view_revisions")
    view_revisions = dict(existing_revisions)
    view_revisions.update(view_revisions_new)  # View Revision은 이벤트 로그 성격 — 덮어쓰지 않고 누적
    out_dir.joinpath("view_revisions.json").write_text(
        json.dumps(view_revisions, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

    target_objects = _target_objects_from(collections)
    assessments_new = build_epistemic_assessments(target_objects, collections, ceiling_records)
    existing_assessments = _load_existing(out_dir, "epistemic_assessments")
    assessments = upsert_collection(existing_assessments, assessments_new)
    assessments = apply_overrides("epistemic_assessments", assessments,
                                   overrides.get("epistemic_assessments", {"human_confirmed": [], "human_rejected": []}))
    out_dir.joinpath("epistemic_assessments.json").write_text(
        json.dumps(assessments, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

    fact_packs = {}
    for eaid, assessment in assessments.items():
        fact_packs[eaid] = build_epistemic_fact_pack(
            assessment["target_object_type"], assessment["target_object_id"], assessment,
            {"independent_source_count": None})  # Source lineage 없음 — 추정 금지(5C 원칙 유지)
    out_dir.joinpath("epistemic_fact_packs.json").write_text(
        json.dumps(fact_packs, ensure_ascii=False, indent=1), encoding="utf-8")

    out_dir.joinpath("epistemic_evidence.json").write_text(
        json.dumps({eaid: {"counter_evidence_count": a.get("counter_evidence_count", 0)}
                   for eaid, a in assessments.items()}, ensure_ascii=False, indent=1), encoding="utf-8")
    out_dir.joinpath("epistemic_history.json").write_text(
        json.dumps({name: {oid: o.get("history", []) for oid, o in collections[name].items()}
                   for name in COLLECTION_NAMES}, ensure_ascii=False, indent=1), encoding="utf-8")

    readiness = {
        "supports_weekly_queries": ["WHAT_CHANGED_OUR_VIEW", "OPEN_CONTRADICTIONS", "OPEN_TENSIONS",
                                     "PARADOX_CANDIDATES", "TOP_UNCERTAINTIES", "UNRESOLVED_EVIDENCE_GAPS"],
        "supports_ask_metaxis_queries": [
            "이 판단의 반대 증거는?", "무엇을 아직 모르는가?", "이 판단에 숨어 있는 가정은?",
            "이 판단이 틀렸다면 무엇이 관측되어야 하는가?", "다른 설명 가능성은?",
            "이 판단은 얼마나 많은 독립적 근거에 기반하는가?", "이 결론과 모순되는 다른 결론이 있는가?",
            "이것은 모순인가 긴장인가 역설인가?", "이 판단은 언제 마지막으로 수정되었는가?",
        ],
        "5f_futures_readiness": {
            "trajectory_outlook_scenario_must_receive": [
                "counter_evidence", "contradictions", "tensions", "uncertainties", "assumptions",
                "falsifiers", "evidence_gaps", "alternative_explanations", "epistemic_ceiling",
            ],
            "bypass_5e_forbidden": True,
        },
        "trajectory_generated": False, "outlook_generated": False, "scenario_generated": False,
        "policy_recommendation_generated": False, "research_recommendation_generated": False,
    }
    out_dir.joinpath("epistemic_readiness.json").write_text(
        json.dumps(readiness, ensure_ascii=False, indent=1), encoding="utf-8")

    metrics = {
        "input_target_objects": sum(len(v) for v in target_index.values()),
        "input_evidence_records": len(evidence_records),
        "counter_evidence_total": len(collections["counter_evidence"]),
        "contradictions_total": len(collections["contradictions"]),
        "tensions_total": len(collections["tensions"]),
        "paradox_candidates_total": len(collections["paradox_candidates"]),
        "uncertainties_total": len(collections["uncertainties"]),
        "assumptions_total": len(collections["assumptions"]),
        "falsifiers_total": len(collections["falsifiers"]),
        "evidence_gaps_total": len(collections["evidence_gaps"]),
        "alternative_explanations_total": len(collections["alternative_explanations"]),
        "view_revisions_total": len(view_revisions),
        "epistemic_assessments_total": len(assessments),
        "contradictions_by_conflict_type": count_by(collections["contradictions"], "conflict_type"),
        "gemini_calls_added": 0, "claude_calls_added": 0, "embedding_calls": 0, "external_api_calls": 0,
    }
    out_dir.joinpath("epistemic_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")

    return metrics, collections, view_revisions, assessments


if __name__ == "__main__":
    m, *_ = run()
    print(json.dumps(m, ensure_ascii=False, indent=1))
