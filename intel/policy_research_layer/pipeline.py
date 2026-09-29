#!/usr/bin/env python3
# PHASE 5G — POLICY/RESEARCH INTELLIGENCE Pipeline. intel/futures_layer/futures_assessments.json을
# 읽기 전용으로만 쓴다 — 5F를 우회한 Policy/Research 생성을 막기 위해 target_index를 오직
# 이 파일에서만 구성한다(운영자 지시 2번). Public/5A~5F 전부 미변경.
#
# 원문에서 정책/연구 객체를 직접 만드는 NLP/LLM 파이프라인은 없다(운영자 지시 70번: LLM 호출
# 금지). 후보 생성은 명시적으로 제공된 Evidence/Claim Record만 입력으로 받는다. 실제
# Production에는 이런 Record 소스가 아직 없고 Futures Assessment도 0이므로, 이 Layer의
# 실제 산출물은 항상 0이다 — 이것이 정상이다(운영자 지시 69번).
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

from policy_question import generate_policy_question_candidates  # noqa: E402
from policy_option import generate_policy_option_candidates  # noqa: E402
from tradeoff import generate_tradeoff_candidates  # noqa: E402
from stakeholder import generate_stakeholder_impact_candidates  # noqa: E402
from constraint import generate_constraint_candidates  # noqa: E402
from policy_uncertainty import generate_policy_uncertainty_candidates  # noqa: E402
from research_question import generate_research_question_candidates  # noqa: E402
from research_gap import generate_research_gap_candidates  # noqa: E402
from evidence_need import generate_evidence_need_candidates  # noqa: E402
from monitoring_indicator import generate_monitoring_indicator_candidates  # noqa: E402
from assessment import build_policy_research_assessments  # noqa: E402
from fact_pack import build_policy_research_fact_pack  # noqa: E402
from overrides import load_overrides, apply_overrides  # noqa: E402
from memory import upsert_collection  # noqa: E402
from metrics import count_by  # noqa: E402

FUTURES_DIR = ROOT / "intel" / "futures_layer"
EVIDENCE_INPUT_PATH = HERE / "policy_research_evidence_input.json"

COLLECTION_NAMES = ("policy_questions", "policy_options", "policy_tradeoffs", "stakeholder_impacts",
                    "policy_constraints", "policy_uncertainties", "research_questions",
                    "research_gaps", "evidence_needs", "monitoring_indicators")


def load_futures_context(futures_assessments_override=None):
    """5F Futures Assessment가 실제로 존재하는 Structural Change만 target_index에 담는다 —
    Structural Change/Futures가 있어도 Futures Assessment가 없으면 대상에서 제외된다
    (운영자 지시 65번 TEST 1: 5F BYPASS 금지)."""
    if futures_assessments_override is not None:
        assessments = futures_assessments_override
    else:
        path = FUTURES_DIR / "futures_assessments.json"
        assessments = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    target_index = {"STRUCTURAL_CHANGE": set()}
    ceiling_map = {}
    futures_assessment_map = {}
    for faid, a in assessments.items():
        for scid in a.get("target_structural_change_ids", []):
            target_index["STRUCTURAL_CHANGE"].add(scid)
            ceiling_map[("STRUCTURAL_CHANGE", scid)] = a.get("epistemic_ceiling", "UNKNOWN")
            futures_assessment_map.setdefault(scid, []).append(faid)
    return target_index, ceiling_map, futures_assessment_map


def load_evidence_records(path=EVIDENCE_INPUT_PATH):
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _load_existing(out_dir, name):
    p = out_dir / f"{name}.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def run(target_index_override=None, ceiling_map_override=None, futures_assessment_map_override=None,
        evidence_records_override=None, out_dir=None, overrides_path=None,
        futures_assessments_override=None):
    """*_override/out_dir/overrides_path는 synthetic fixture 전용 격리 경로."""
    out_dir = Path(out_dir) if out_dir else HERE
    if target_index_override is not None:
        target_index = target_index_override
        ceiling_map = ceiling_map_override or {}
        futures_assessment_map = futures_assessment_map_override or {}
    else:
        target_index, ceiling_map, futures_assessment_map = load_futures_context(futures_assessments_override)
    evidence_records = (evidence_records_override if evidence_records_override is not None
                         else load_evidence_records())

    existing = {name: _load_existing(out_dir, name) for name in COLLECTION_NAMES}

    pq_new = generate_policy_question_candidates(evidence_records, target_index)
    policy_questions = {**existing["policy_questions"], **pq_new}
    opt_new = generate_policy_option_candidates(evidence_records, policy_questions)
    policy_options = {**existing["policy_options"], **opt_new}
    tradeoffs_new = generate_tradeoff_candidates(evidence_records, policy_options)
    stakeholders_new = generate_stakeholder_impact_candidates(evidence_records, policy_options)
    constraints_new = generate_constraint_candidates(evidence_records, policy_options)
    policy_unc_new = generate_policy_uncertainty_candidates(evidence_records, policy_questions, policy_options)
    rq_new = generate_research_question_candidates(evidence_records, policy_questions)
    research_questions = {**existing["research_questions"], **rq_new}
    rgap_new = generate_research_gap_candidates(evidence_records, target_index)
    eneed_new = generate_evidence_need_candidates(evidence_records, research_questions, policy_questions)
    mon_new = generate_monitoring_indicator_candidates(evidence_records)

    overrides = load_overrides(Path(overrides_path)) if overrides_path else load_overrides()

    new_by_name = {
        "policy_questions": pq_new, "policy_options": opt_new, "policy_tradeoffs": tradeoffs_new,
        "stakeholder_impacts": stakeholders_new, "policy_constraints": constraints_new,
        "policy_uncertainties": policy_unc_new, "research_questions": rq_new,
        "research_gaps": rgap_new, "evidence_needs": eneed_new, "monitoring_indicators": mon_new,
    }

    collections = {}
    for name in COLLECTION_NAMES:
        merged = upsert_collection(existing[name], new_by_name[name])
        merged = apply_overrides(name, merged, overrides.get(name, {"human_confirmed": [], "human_rejected": []}))
        collections[name] = merged

    for name in COLLECTION_NAMES:
        out_dir.joinpath(f"{name}.json").write_text(
            json.dumps(collections[name], ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

    structural_change_ids = sorted(target_index.get("STRUCTURAL_CHANGE", set()))
    assessments_new = build_policy_research_assessments(structural_change_ids, futures_assessment_map,
                                                          collections, ceiling_map)
    existing_assessments = _load_existing(out_dir, "policy_research_assessments")
    assessments = upsert_collection(existing_assessments, assessments_new)
    assessments = apply_overrides("policy_research_assessments", assessments,
                                   overrides.get("policy_research_assessments",
                                                 {"human_confirmed": [], "human_rejected": []}))
    out_dir.joinpath("policy_research_assessments.json").write_text(
        json.dumps(assessments, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

    fact_packs = {paid: build_policy_research_fact_pack(a) for paid, a in assessments.items()}
    out_dir.joinpath("policy_research_fact_packs.json").write_text(
        json.dumps(fact_packs, ensure_ascii=False, indent=1), encoding="utf-8")
    out_dir.joinpath("policy_research_evidence.json").write_text(
        json.dumps({paid: {"counter_evidence_ids": a.get("counter_evidence_ids", [])}
                   for paid, a in assessments.items()}, ensure_ascii=False, indent=1), encoding="utf-8")
    out_dir.joinpath("policy_research_history.json").write_text(
        json.dumps({name: {oid: o.get("history", []) for oid, o in collections[name].items()}
                   for name in COLLECTION_NAMES}, ensure_ascii=False, indent=1), encoding="utf-8")

    readiness = {
        "supports_weekly_queries": [
            "NEW_POLICY_QUESTIONS", "NEW_POLICY_OPTIONS", "NEW_TRADEOFFS", "NEW_STAKEHOLDER_IMPACTS",
            "NEW_POLICY_CONSTRAINTS", "NEW_RESEARCH_QUESTIONS", "NEW_RESEARCH_GAPS",
            "NEW_EVIDENCE_NEEDS", "EVIDENCE_GAPS_FILLED", "NEW_MONITORING_INDICATORS",
            "POLICY_QUESTIONS_CHANGED", "RESEARCH_QUESTIONS_RESOLVED", "DECISION_POINTS_TO_WATCH",
        ],
        "supports_ask_metaxis_queries": [
            "이 변화가 어떤 정책 문제를 만드는가?", "선택지는 무엇인가?", "어떤 선택이 누구에게 어떤 영향을 주나?",
            "Trade-off는 무엇인가?", "왜 지금 결정해야 하나?", "정책 개입을 안 하면 어떤 경로인가?",
            "무엇을 아직 모르는가?", "어떤 연구가 필요한가?", "무슨 데이터를 모아야 하나?",
            "어떤 지표를 계속 봐야 하나?", "이 정책 판단을 바꿀 Evidence는?",
        ],
        "decision_memo_ready": ["DECISION_QUESTION", "WHY_NOW", "STRUCTURAL_CHANGE", "FUTURES_PATHS",
                                "OPTIONS", "TRADEOFFS", "STAKEHOLDERS", "CONSTRAINTS", "UNCERTAINTIES",
                                "WHAT_WE_KNOW", "WHAT_WE_DONT_KNOW", "RESEARCH_QUESTIONS",
                                "EVIDENCE_NEEDED", "WHAT_TO_MONITOR", "WHAT_WOULD_CHANGE_OUR_VIEW"],
        "research_agenda_ready": ["QUESTION", "WHY_IT_MATTERS", "CURRENT_EVIDENCE", "COUNTER_EVIDENCE",
                                  "GAP", "METHOD_NEEDED", "DATA_NEEDED", "POPULATION", "GEOGRAPHY",
                                  "TIME", "POLICY_RELEVANCE", "FALSIFIER", "MONITORING_INDICATOR"],
        "human_judgment_required_for": ["PREFERRED_OPTION", "POLICY_RECOMMENDATION", "NORMATIVE_PRIORITY",
                                        "POLITICAL_JUDGMENT", "PUBLIC_RECOMMENDATION", "FINAL_RESEARCH_THESIS"],
        "stage5_completion_readiness": {
            "chain_complete": ["STRUCTURAL_CHANGE", "STRUCTURAL_ANALYSIS", "EPISTEMIC_CHECK",
                              "FUTURES_INTELLIGENCE", "POLICY_RESEARCH_INTELLIGENCE"],
            "architecture_debt": ["EVIDENCE_EXTRACTION_INTERPRETATION_PIPELINE_NOT_YET_CONNECTED"],
        },
        "policy_recommendation_generated": False, "research_finding_auto_evaluated": False,
        "composite_policy_score_generated": False,
    }
    out_dir.joinpath("policy_research_readiness.json").write_text(
        json.dumps(readiness, ensure_ascii=False, indent=1), encoding="utf-8")

    metrics = {
        "input_structural_changes_with_futures_assessment": len(target_index.get("STRUCTURAL_CHANGE", set())),
        "input_evidence_records": len(evidence_records),
        "policy_questions_total": len(collections["policy_questions"]),
        "policy_options_total": len(collections["policy_options"]),
        "policy_tradeoffs_total": len(collections["policy_tradeoffs"]),
        "stakeholder_impacts_total": len(collections["stakeholder_impacts"]),
        "policy_constraints_total": len(collections["policy_constraints"]),
        "policy_uncertainties_total": len(collections["policy_uncertainties"]),
        "research_questions_total": len(collections["research_questions"]),
        "research_gaps_total": len(collections["research_gaps"]),
        "evidence_needs_total": len(collections["evidence_needs"]),
        "monitoring_indicators_total": len(collections["monitoring_indicators"]),
        "policy_research_assessments_total": len(assessments),
        "policy_options_by_type": count_by(collections["policy_options"], "option_type"),
        "policy_tradeoffs_by_status": count_by(collections["policy_tradeoffs"], "status"),
        "gemini_calls_added": 0, "claude_calls_added": 0, "embedding_calls": 0, "external_api_calls": 0,
    }
    out_dir.joinpath("policy_research_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")

    return metrics, collections, assessments


if __name__ == "__main__":
    m, *_ = run()
    print(json.dumps(m, ensure_ascii=False, indent=1))
