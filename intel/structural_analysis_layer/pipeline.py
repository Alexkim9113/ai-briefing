#!/usr/bin/env python3
# PHASE 5D — DRIVER/DEPENDENCY/POWER·VALUE·SCARCITY INTELLIGENCE Pipeline.
# intel/structural_change_layer/structural_changes.json을 읽기 전용으로만 쓴다.
# Public/Evidence/Fact/Event/Change/Signal/Pattern/Structural Change 전부 미변경.
#
# 이 Layer는 아직 원문 기사에서 Dependency/Control/Power/Value/Scarcity/Bottleneck을 자동
# 추출하는 NLP/LLM 파이프라인을 갖지 않는다(운영자 지시 44번: 이번 Foundation은 LLM 호출
# 금지). 따라서 후보 생성은 명시적으로 제공된 Evidence Record만 입력으로 받는다 — 이렇게
# 해야 "Evidence 없이 자동 생성 금지"(Acceptance 1~7번)를 코드로 강제할 수 있다.
# 실제 Production에는 이런 Evidence Record 소스가 아직 없으므로(=Structural Change도
# 0이므로) 이 Layer의 실제 산출물은 항상 0이다.
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

from schema import new_structural_analysis_shell  # noqa: E402
from driver import generate_driver_candidates  # noqa: E402
from dependency import generate_dependency_candidates  # noqa: E402
from control import generate_control_candidates  # noqa: E402
from power import generate_power_shift_candidates  # noqa: E402
from value import generate_value_shift_candidates  # noqa: E402
from scarcity import generate_scarcity_shift_candidates  # noqa: E402
from bottleneck import generate_bottleneck_candidates  # noqa: E402
from evidence import collect_evidence_ids, uncertainty_flags_for  # noqa: E402
from fact_pack import build_structural_analysis_fact_pack  # noqa: E402
from overrides import load_overrides, apply_overrides  # noqa: E402
from memory import upsert_collection  # noqa: E402
from metrics import count_by  # noqa: E402

STRUCTURAL_CHANGE_DIR = ROOT / "intel" / "structural_change_layer"
EVIDENCE_INPUT_PATH = HERE / "structural_evidence_input.json"

COLLECTION_NAMES = ("drivers", "dependencies", "controls", "power_shifts", "value_shifts",
                    "scarcity_shifts", "bottlenecks")


def load_active_structural_changes():
    path = STRUCTURAL_CHANGE_DIR / "structural_changes.json"
    if not path.exists():
        return {}
    all_sc = json.loads(path.read_text(encoding="utf-8"))
    return {scid: sc for scid, sc in all_sc.items()
            if sc.get("status") != "REJECTED" and sc.get("override_status") != "HUMAN_REJECTED"}


def load_evidence_records(path=EVIDENCE_INPUT_PATH):
    """실제 Production에는 아직 이 Evidence Record 소스가 없다(운영자 지시 44번: LLM으로
    자동 채우지 않음). 파일이 없으면 빈 리스트 — 즉 0건이 정직한 기본값이다."""
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _load_existing(out_dir, name):
    p = out_dir / f"{name}.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def run(structural_changes_override=None, evidence_records_override=None, out_dir=None,
        overrides_path=None):
    """*_override/out_dir/overrides_path는 synthetic fixture 전용 격리 경로."""
    out_dir = Path(out_dir) if out_dir else HERE
    active_sc = (structural_changes_override if structural_changes_override is not None
                 else load_active_structural_changes())
    evidence_records = (evidence_records_override if evidence_records_override is not None
                         else load_evidence_records())

    drivers_new = generate_driver_candidates(evidence_records, active_sc)
    dependencies_new = generate_dependency_candidates(evidence_records, active_sc)
    controls_new = generate_control_candidates(evidence_records, active_sc)
    power_shifts_new = generate_power_shift_candidates(dependencies_new, controls_new, active_sc, evidence_records)
    value_shifts_new = generate_value_shift_candidates(evidence_records, active_sc)
    scarcity_shifts_new = generate_scarcity_shift_candidates(evidence_records, active_sc)
    bottlenecks_new = generate_bottleneck_candidates(evidence_records, active_sc)

    overrides = load_overrides(Path(overrides_path)) if overrides_path else load_overrides()

    collections = {}
    for name, new_candidates in (
        ("drivers", drivers_new), ("dependencies", dependencies_new), ("controls", controls_new),
        ("power_shifts", power_shifts_new), ("value_shifts", value_shifts_new),
        ("scarcity_shifts", scarcity_shifts_new), ("bottlenecks", bottlenecks_new),
    ):
        existing = _load_existing(out_dir, name)
        merged = upsert_collection(existing, new_candidates)
        merged = apply_overrides(merged, overrides.get(name, {"human_confirmed": [], "human_rejected": []}))
        collections[name] = merged
        out_dir.joinpath(f"{name}.json").write_text(
            json.dumps(merged, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

    # Structural Analysis 통합 객체 — Structural Change 1개당 1개, 그 아래 7종 객체를 묶는다.
    structural_analyses = {}
    for scid in active_sc:
        per_sc = {name: {oid: o for oid, o in coll.items() if scid in o.get(
            "related_structural_change_ids" if name == "drivers" else "supporting_structural_change_ids", [])}
            for name, coll in collections.items()}
        if not any(per_sc.values()):
            continue
        aid = "sa_" + hashlib.sha1(scid.encode("utf-8")).hexdigest()[:16]
        shell = new_structural_analysis_shell(aid, scid)
        shell["driver_ids"] = sorted(per_sc["drivers"].keys())
        shell["dependency_ids"] = sorted(per_sc["dependencies"].keys())
        shell["control_ids"] = sorted(per_sc["controls"].keys())
        shell["power_shift_ids"] = sorted(per_sc["power_shifts"].keys())
        shell["value_shift_ids"] = sorted(per_sc["value_shifts"].keys())
        shell["scarcity_shift_ids"] = sorted(per_sc["scarcity_shifts"].keys())
        shell["bottleneck_ids"] = sorted(per_sc["bottlenecks"].keys())

        supporting, counter = collect_evidence_ids(*per_sc.values())
        shell["supporting_evidence_ids"] = supporting
        shell["counter_evidence_ids"] = counter
        flags = uncertainty_flags_for(per_sc)
        shell["uncertainties"] = flags
        confidences = [o.get("confidence", "LOW") for coll in per_sc.values() for o in coll.values()]
        shell["confidence"] = "HIGH" if confidences and all(c == "HIGH" for c in confidences) else (
            "MEDIUM" if "MEDIUM" in confidences or "HIGH" in confidences else "LOW")
        structural_analyses[aid] = shell

    existing_analyses = _load_existing(out_dir, "structural_analyses")
    structural_analyses = upsert_collection(existing_analyses, structural_analyses) if structural_analyses else {
        aid: a for aid, a in existing_analyses.items()}
    out_dir.joinpath("structural_analyses.json").write_text(
        json.dumps(structural_analyses, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

    fact_packs = {}
    for aid, sa in structural_analyses.items():
        fact_packs[aid] = build_structural_analysis_fact_pack(
            aid, sa["structural_change_id"], sa["driver_ids"], sa["dependency_ids"], sa["control_ids"],
            sa["power_shift_ids"], sa["value_shift_ids"], sa["scarcity_shift_ids"], sa["bottleneck_ids"],
            [], [], [], [], [], [], [], [],
            sa["counter_evidence_ids"], sa["uncertainties"],
            {"independent_driver_count": len(sa["driver_ids"]), "independent_dependency_count": len(sa["dependency_ids"]),
             "independent_source_count": None},  # Source lineage 없음 — 5C 원칙 유지, 0으로 추정 금지
            None, None)
    out_dir.joinpath("structural_analysis_fact_packs.json").write_text(
        json.dumps(fact_packs, ensure_ascii=False, indent=1), encoding="utf-8")
    out_dir.joinpath("structural_analysis_evidence.json").write_text(
        json.dumps({aid: {"supporting_evidence_ids": sa["supporting_evidence_ids"],
                          "counter_evidence_ids": sa["counter_evidence_ids"]}
                   for aid, sa in structural_analyses.items()}, ensure_ascii=False, indent=1), encoding="utf-8")
    out_dir.joinpath("structural_analysis_history.json").write_text(
        json.dumps({name: {oid: o.get("history", []) for oid, o in collections[name].items()}
                   for name in COLLECTION_NAMES}, ensure_ascii=False, indent=1), encoding="utf-8")

    readiness = {
        "supports_weekly_queries": ["NEW_DRIVERS", "NEW_DEPENDENCIES", "NEW_BOTTLENECKS", "POWER_SHIFTS",
                                     "VALUE_SHIFTS", "SCARCITY_SHIFTS", "CONTROL_CONCENTRATION",
                                     "DEPENDENCY_EXPANSION", "STRUCTURAL_CONTRADICTIONS"],
        "supports_ask_metaxis_queries": ["dimensions", "from_state", "to_state", "time", "domains",
                                          "event_types", "entities", "institutions", "resources"],
        "obsidian_export_ready_ids": True,
        "contradiction_uncertainty_generated": False, "scenario_generated": False,
        "policy_recommendation_generated": False,
    }
    out_dir.joinpath("structural_analysis_readiness.json").write_text(
        json.dumps(readiness, ensure_ascii=False, indent=1), encoding="utf-8")

    metrics = {
        "input_active_structural_changes": len(active_sc),
        "input_evidence_records": len(evidence_records),
        "drivers_total": len(collections["drivers"]), "dependencies_total": len(collections["dependencies"]),
        "controls_total": len(collections["controls"]), "power_shifts_total": len(collections["power_shifts"]),
        "value_shifts_total": len(collections["value_shifts"]),
        "scarcity_shifts_total": len(collections["scarcity_shifts"]),
        "bottlenecks_total": len(collections["bottlenecks"]),
        "structural_analyses_total": len(structural_analyses),
        "drivers_by_status": count_by(collections["drivers"], "status"),
        "gemini_calls_added": 0, "claude_calls_added": 0, "embedding_calls": 0, "external_api_calls": 0,
    }
    out_dir.joinpath("structural_analysis_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")

    return metrics, collections, structural_analyses


if __name__ == "__main__":
    m, *_ = run()
    print(json.dumps(m, ensure_ascii=False, indent=1))
