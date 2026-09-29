#!/usr/bin/env python3
# PHASE 5F — FUTURES INTELLIGENCE Pipeline (TRAJECTORY→OUTLOOK→ALTERNATIVE PATH→SCENARIO→
# 2ND/3RD-ORDER EFFECT→FORECAST→FORECAST MEMORY).
# intel/epistemic_layer/epistemic_assessments.json을 읽기 전용으로만 쓴다 — 5E를 우회한
# Futures 생성을 막기 위해 target_index를 오직 이 파일에서만 구성한다(운영자 지시 2번).
# Public/Evidence/Fact/Event/Change/Signal/Pattern/Structural Change/Structural
# Analysis/Epistemic Layer 전부 미변경.
#
# 원문에서 미래를 자동 추론하는 NLP/LLM 파이프라인은 없다(운영자 지시 67번: LLM 호출 금지).
# 후보 생성은 명시적으로 제공된 Evidence/Claim Record만 입력으로 받는다. 실제 Production에는
# 이런 Record 소스가 아직 없고 Epistemic Assessment도 0이므로, 이 Layer의 실제 산출물은
# 항상 0이다 — 이것이 정상이다(운영자 지시 57번).
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

from trajectory import generate_trajectory_candidates  # noqa: E402
from outlook import generate_outlook_candidates  # noqa: E402
from alternative_path import generate_alternative_path_candidates  # noqa: E402
from scenario import generate_scenario_candidates  # noqa: E402
from effects import generate_second_order_effects, generate_third_order_effects  # noqa: E402
from forecast import generate_forecast_candidates  # noqa: E402
from forecast_observation import generate_forecast_observations, apply_observations_to_forecast_status  # noqa: E402
from forecast_revision import generate_forecast_revisions  # noqa: E402
from assessment import build_futures_assessments  # noqa: E402
from fact_pack import build_futures_fact_pack  # noqa: E402
from overrides import load_overrides, apply_overrides  # noqa: E402
from memory import upsert_collection  # noqa: E402
from metrics import count_by  # noqa: E402

EPISTEMIC_DIR = ROOT / "intel" / "epistemic_layer"
EVIDENCE_INPUT_PATH = HERE / "futures_evidence_input.json"

COLLECTION_NAMES = ("trajectories", "outlooks", "alternative_paths", "scenarios",
                    "second_order_effects", "third_order_effects", "forecasts")


def load_epistemic_context(epistemic_assessments_override=None):
    """5E Epistemic Assessment가 실제로 존재하는 (target_type, target_id)만 target_index에
    담는다 — Structural Change가 있어도 Epistemic Assessment가 없으면 대상에서 제외된다
    (운영자 지시 58번 TEST 2: 5E BYPASS 금지)."""
    if epistemic_assessments_override is not None:
        assessments = epistemic_assessments_override
    else:
        path = EPISTEMIC_DIR / "epistemic_assessments.json"
        assessments = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    target_index = {}
    ceiling_map = {}
    for a in assessments.values():
        tt, tid = a.get("target_object_type"), a.get("target_object_id")
        if not tt or not tid:
            continue
        target_index.setdefault(tt, set()).add(tid)
        ceiling_map[(tt, tid)] = a.get("epistemic_ceiling", "UNKNOWN")
    return target_index, ceiling_map


def load_evidence_records(path=EVIDENCE_INPUT_PATH):
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _load_existing(out_dir, name):
    p = out_dir / f"{name}.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def run(target_index_override=None, ceiling_map_override=None, evidence_records_override=None,
        out_dir=None, overrides_path=None, epistemic_assessments_override=None):
    """*_override/out_dir/overrides_path는 synthetic fixture 전용 격리 경로."""
    out_dir = Path(out_dir) if out_dir else HERE
    if target_index_override is not None:
        target_index, ceiling_map = target_index_override, (ceiling_map_override or {})
    else:
        target_index, ceiling_map = load_epistemic_context(epistemic_assessments_override)
    evidence_records = (evidence_records_override if evidence_records_override is not None
                         else load_evidence_records())

    existing = {name: _load_existing(out_dir, name) for name in COLLECTION_NAMES}

    trajectories_new = generate_trajectory_candidates(evidence_records, target_index, ceiling_map)
    trajectories = {**existing["trajectories"], **trajectories_new}  # Outlook/Path가 참조할 수 있게 병합 뷰
    outlooks_new = generate_outlook_candidates(evidence_records, trajectories, ceiling_map)
    alt_paths_new = generate_alternative_path_candidates(evidence_records, trajectories, ceiling_map)
    alt_paths = {**existing["alternative_paths"], **alt_paths_new}
    scenarios_new = generate_scenario_candidates(evidence_records, trajectories, alt_paths, ceiling_map)
    eff2_new = generate_second_order_effects(evidence_records, target_index, ceiling_map)
    eff2 = {**existing["second_order_effects"], **eff2_new}
    eff3_new = generate_third_order_effects(evidence_records, eff2, ceiling_map)
    forecasts_new = generate_forecast_candidates(evidence_records, target_index, ceiling_map)

    overrides = load_overrides(Path(overrides_path)) if overrides_path else load_overrides()

    new_by_name = {
        "trajectories": trajectories_new, "outlooks": outlooks_new, "alternative_paths": alt_paths_new,
        "scenarios": scenarios_new, "second_order_effects": eff2_new, "third_order_effects": eff3_new,
        "forecasts": forecasts_new,
    }

    collections = {}
    for name in COLLECTION_NAMES:
        merged = upsert_collection(existing[name], new_by_name[name])
        merged = apply_overrides(name, merged, overrides.get(name, {"human_confirmed": [], "human_rejected": []}))
        collections[name] = merged

    # Forecast Observation/Revision — Forecast 본문을 직접 갱신(삭제 없이 Revision으로만 기록).
    observations_new = generate_forecast_observations(evidence_records, collections["forecasts"])
    collections["forecasts"] = apply_observations_to_forecast_status(collections["forecasts"], observations_new)
    revisions_new, collections["forecasts"] = generate_forecast_revisions(evidence_records, collections["forecasts"])

    existing_observations = _load_existing(out_dir, "forecast_observations")
    observations = dict(existing_observations)
    observations.update(observations_new)  # 이벤트 로그 — 누적만
    existing_revisions = _load_existing(out_dir, "forecast_revisions")
    revisions = dict(existing_revisions)
    revisions.update(revisions_new)

    for name in COLLECTION_NAMES:
        out_dir.joinpath(f"{name}.json").write_text(
            json.dumps(collections[name], ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    out_dir.joinpath("forecast_observations.json").write_text(
        json.dumps(observations, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    out_dir.joinpath("forecast_revisions.json").write_text(
        json.dumps(revisions, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

    structural_change_ids = sorted(target_index.get("STRUCTURAL_CHANGE", set()))
    assessments_new = build_futures_assessments(structural_change_ids, collections, ceiling_map)
    existing_assessments = _load_existing(out_dir, "futures_assessments")
    assessments = upsert_collection(existing_assessments, assessments_new)
    assessments = apply_overrides("futures_assessments", assessments,
                                   overrides.get("futures_assessments", {"human_confirmed": [], "human_rejected": []}))
    out_dir.joinpath("futures_assessments.json").write_text(
        json.dumps(assessments, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

    fact_packs = {faid: build_futures_fact_pack(a) for faid, a in assessments.items()}
    out_dir.joinpath("futures_fact_packs.json").write_text(
        json.dumps(fact_packs, ensure_ascii=False, indent=1), encoding="utf-8")
    out_dir.joinpath("futures_evidence.json").write_text(
        json.dumps({faid: {"counter_evidence_ids": a.get("counter_evidence_ids", [])}
                   for faid, a in assessments.items()}, ensure_ascii=False, indent=1), encoding="utf-8")
    out_dir.joinpath("futures_history.json").write_text(
        json.dumps({name: {oid: o.get("history", []) for oid, o in collections[name].items()}
                   for name in COLLECTION_NAMES}, ensure_ascii=False, indent=1), encoding="utf-8")

    readiness = {
        "supports_weekly_queries": [
            "TRAJECTORIES_STRENGTHENING", "TRAJECTORIES_WEAKENING", "NEW_OUTLOOKS",
            "NEW_ALTERNATIVE_PATHS", "NEW_SCENARIOS", "SCENARIOS_WEAKENED",
            "NEW_SECOND_ORDER_EFFECTS", "NEW_THIRD_ORDER_EFFECTS", "NEW_FORECASTS",
            "FORECASTS_SUPPORTED", "FORECASTS_WEAKENED", "FORECASTS_CONTRADICTED",
            "FORECAST_REVISIONS", "WHAT_CHANGED_OUR_VIEW", "WHAT_WOULD_CHANGE_OUR_VIEW",
            "NEXT_WEEK_WATCHLIST",
        ],
        "supports_ask_metaxis_queries": [
            "이 변화는 어디로 향하고 있나?", "현재 방향이 계속되면 어떻게 되나?", "다른 경로는 무엇인가?",
            "어떤 조건에서 방향이 바뀌나?", "2차 효과는 무엇인가?", "3차 효과는 무엇인가?",
            "이 전망을 깨는 Evidence는?", "우리가 과거에 무엇을 예상했나?", "어떤 전망을 수정했나?", "왜 수정했나?",
        ],
        "report_chain_ready": ["OBSERVED", "CHANGE", "STRUCTURAL_CHANGE", "TRAJECTORY", "OUTLOOK",
                               "ALTERNATIVE_PATHS", "SCENARIOS", "2ND_3RD_ORDER_EFFECTS",
                               "COUNTER_EVIDENCE", "CONFIDENCE", "WHAT_TO_WATCH"],
        "human_judgment_required_for": ["SCENARIO_INTERPRETATION", "FORECAST_WORDING",
                                        "HIGH_STAKES_IMPLICATIONS", "PUBLIC_PUBLICATION", "POLICY_IMPLICATIONS"],
        "5g_readiness": {
            "policy_research_intelligence_must_receive": [
                "trajectories", "outlooks", "alternative_paths", "scenarios",
                "second_order_effects", "third_order_effects", "forecasts", "futures_assessments",
                "counter_evidence", "uncertainties", "assumptions", "falsifiers", "epistemic_ceiling",
            ],
            "bypass_5f_forbidden": True,
        },
        "policy_recommendation_generated": False, "research_recommendation_generated": False,
        "storytelling_generated": False,
    }
    out_dir.joinpath("futures_readiness.json").write_text(
        json.dumps(readiness, ensure_ascii=False, indent=1), encoding="utf-8")

    metrics = {
        "input_target_objects": sum(len(v) for v in target_index.values()),
        "input_evidence_records": len(evidence_records),
        "trajectories_total": len(collections["trajectories"]), "outlooks_total": len(collections["outlooks"]),
        "alternative_paths_total": len(collections["alternative_paths"]),
        "scenarios_total": len(collections["scenarios"]),
        "second_order_effects_total": len(collections["second_order_effects"]),
        "third_order_effects_total": len(collections["third_order_effects"]),
        "forecasts_total": len(collections["forecasts"]),
        "forecast_observations_total": len(observations), "forecast_revisions_total": len(revisions),
        "futures_assessments_total": len(assessments),
        "scenarios_by_type": count_by(collections["scenarios"], "scenario_type"),
        "gemini_calls_added": 0, "claude_calls_added": 0, "embedding_calls": 0, "external_api_calls": 0,
    }
    out_dir.joinpath("futures_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")

    return metrics, collections, observations, revisions, assessments


if __name__ == "__main__":
    m, *_ = run()
    print(json.dumps(m, ensure_ascii=False, indent=1))
