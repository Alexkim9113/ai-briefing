#!/usr/bin/env python3
# PHASE 5G — 44개 Synthetic Fixture 테스트(운영자 지시 65, 73번). 전부 tempfile.mkdtemp()로
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


def futures_context(*entries):
    """entries: (scid, ceiling, faid) 튜플들. 5F Futures Assessment가 실제 존재하는
    Structural Change만 target_index에 들어간다 — bypass guard의 핵심."""
    target_index = {"STRUCTURAL_CHANGE": set()}
    ceiling_map, fa_map = {}, {}
    for scid, ceiling, faid in entries:
        target_index["STRUCTURAL_CHANGE"].add(scid)
        ceiling_map[("STRUCTURAL_CHANGE", scid)] = ceiling
        fa_map.setdefault(scid, []).append(faid)
    return target_index, ceiling_map, fa_map


def isolated_dir():
    d = Path(tempfile.mkdtemp(prefix="policy_research_test_"))
    overrides_path = d / "overrides.json"
    from overrides import COLLECTIONS
    overrides_path.write_text(json.dumps(
        {c: {"human_confirmed": [], "human_rejected": []} for c in COLLECTIONS}), encoding="utf-8")
    return d, overrides_path


def run_isolated(records, ti, cm, fam, out_dir=None, overrides_path=None):
    if out_dir is None:
        out_dir, overrides_path = isolated_dir()
    metrics, collections, assessments = pipeline.run(
        target_index_override=ti, ceiling_map_override=cm, futures_assessment_map_override=fam,
        evidence_records_override=records, out_dir=out_dir, overrides_path=overrides_path)
    return out_dir, overrides_path, metrics, collections, assessments


def pq_rec(scid="sc1", **kw):
    base = {"type": "POLICY_QUESTION", "target_structural_change_ids": [scid],
            "futures_assessment_ids": ["fa1"], "question": "Agent transaction liability 배분",
            "question_type": "LIABILITY", "trigger_conditions": ["AI Agent가 결제를 대신 실행"],
            "decision_level": "NATIONAL", "evidence_ids": ["e1"]}
    base.update(kw)
    return base


def pq_and_dir(ti, cm, fam):
    out_dir, overrides_path, _, coll, _ = run_isolated([pq_rec()], ti, cm, fam)
    pqid = next(iter(coll["policy_questions"].keys()))
    return out_dir, overrides_path, pqid


def opt_rec(pqid, name="OPTION_A", option_type="LIABILITY_RULE", **kw):
    base = {"type": "POLICY_OPTION", "policy_question_id": pqid, "option_name": name,
            "option_type": option_type, "mechanism": "principal-agent liability 적용",
            "target_actor": "PLATFORM", "implementation_level": "NATIONAL"}
    base.update(kw)
    return base


def test_01_5f_bypass():
    ti, cm, fam = futures_context()  # sc1에 대한 Futures Assessment 없음
    _, _, m, *_ = run_isolated([pq_rec()], ti, cm, fam)
    assert m["policy_questions_total"] == 0
    print("test_01 OK")


def test_02_policy_question():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    _, _, m, coll, _ = run_isolated([pq_rec()], ti, cm, fam)
    assert m["policy_questions_total"] == 1
    print("test_02 OK")


def test_03_no_decision_issue():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    rec = pq_rec(trigger_conditions=[])
    _, _, m, *_ = run_isolated([rec], ti, cm, fam)
    assert m["policy_questions_total"] == 0
    print("test_03 OK")


def test_04_policy_option():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    out_dir, overrides_path, pqid = pq_and_dir(ti, cm, fam)
    _, _, m, coll, _ = run_isolated([pq_rec(), opt_rec(pqid)], ti, cm, fam, out_dir=out_dir,
                                     overrides_path=overrides_path)
    assert m["policy_options_total"] == 1
    print("test_04 OK")


def test_05_no_option_invention():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    out_dir, overrides_path, pqid = pq_and_dir(ti, cm, fam)
    _, _, m, *_ = run_isolated([pq_rec()], ti, cm, fam, out_dir=out_dir, overrides_path=overrides_path)
    assert m["policy_options_total"] == 0
    print("test_05 OK")


def test_06_no_action_option():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    out_dir, overrides_path, pqid = pq_and_dir(ti, cm, fam)
    rec = opt_rec(pqid, name="STATUS_QUO", option_type="NO_ACTION", mechanism=None)
    _, _, m, coll, _ = run_isolated([pq_rec(), rec], ti, cm, fam, out_dir=out_dir, overrides_path=overrides_path)
    assert m["policy_options_total"] == 1
    o = next(iter(coll["policy_options"].values()))
    assert o["option_type"] == "NO_ACTION"
    print("test_06 OK")


def test_07_no_ranking():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    out_dir, overrides_path, pqid = pq_and_dir(ti, cm, fam)
    recs = [pq_rec(), opt_rec(pqid, "A"), opt_rec(pqid, "B"), opt_rec(pqid, "C")]
    _, _, m, coll, _ = run_isolated(recs, ti, cm, fam, out_dir=out_dir, overrides_path=overrides_path)
    assert m["policy_options_total"] == 3
    for o in coll["policy_options"].values():
        assert "winner" not in o and "recommended" not in o and "preferred" not in o and "score" not in o
    print("test_07 OK")


def _pq_opt(ti, cm, fam):
    out_dir, overrides_path, pqid = pq_and_dir(ti, cm, fam)
    out_dir, overrides_path, _, coll, _ = run_isolated([pq_rec(), opt_rec(pqid)], ti, cm, fam,
                                                        out_dir=out_dir, overrides_path=overrides_path)
    oid = next(iter(coll["policy_options"].keys()))
    return out_dir, overrides_path, pqid, oid


def test_08_tradeoff():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    out_dir, overrides_path, pqid, oid = _pq_opt(ti, cm, fam)
    tof = {"type": "POLICY_TRADEOFF", "policy_option_id": oid, "dimension_a": "ACCESS",
           "direction_a": "INCREASING", "dimension_b": "SECURITY", "direction_b": "DECREASING",
           "mechanism": "interoperability requirement가 접근성을 높이지만 보안 부담 증가",
           "evidence_ids": ["e1"]}
    records = [pq_rec(), opt_rec(pqid), tof]
    _, _, m, coll, _ = run_isolated(records, ti, cm, fam, out_dir=out_dir, overrides_path=overrides_path)
    assert m["policy_tradeoffs_total"] == 1
    t = next(iter(coll["policy_tradeoffs"].values()))
    assert t["status"] == "CONFIRMED_TRADEOFF"
    print("test_08 OK")


def test_09_tradeoff_uncertain():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    out_dir, overrides_path, pqid, oid = _pq_opt(ti, cm, fam)
    tof = {"type": "POLICY_TRADEOFF", "policy_option_id": oid, "dimension_a": "SAFETY",
           "direction_a": "INCREASING", "dimension_b": "INNOVATION", "direction_b": "DECREASING",
           "mechanism": "약한 근거"}
    records = [pq_rec(), opt_rec(pqid), tof]
    _, _, m, coll, _ = run_isolated(records, ti, cm, fam, out_dir=out_dir, overrides_path=overrides_path)
    t = next(iter(coll["policy_tradeoffs"].values()))
    assert t["status"] == "POTENTIAL_TRADEOFF"
    print("test_09 OK")


def test_10_stakeholder_difference():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    out_dir, overrides_path, pqid, oid = _pq_opt(ti, cm, fam)
    s1 = {"type": "STAKEHOLDER_IMPACT", "policy_option_id": oid, "stakeholder_type": "PLATFORM",
          "stakeholder_id_or_label": "LARGE_PLATFORM", "impact_dimension": "COST", "direction": "COST",
          "mechanism": "컴플라이언스 비용 증가"}
    s2 = {"type": "STAKEHOLDER_IMPACT", "policy_option_id": oid, "stakeholder_type": "STARTUP",
          "stakeholder_id_or_label": "STARTUP", "impact_dimension": "ACCESS", "direction": "OPPORTUNITY",
          "mechanism": "신규 시장 접근 기회"}
    records = [pq_rec(), opt_rec(pqid), s1, s2]
    _, _, m, coll, _ = run_isolated(records, ti, cm, fam, out_dir=out_dir, overrides_path=overrides_path)
    assert m["stakeholder_impacts_total"] == 2
    directions = {s["direction"] for s in coll["stakeholder_impacts"].values()}
    assert directions == {"COST", "OPPORTUNITY"}
    print("test_10 OK")


def test_11_no_moral_ranking():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    out_dir, overrides_path, pqid, oid = _pq_opt(ti, cm, fam)
    s1 = {"type": "STAKEHOLDER_IMPACT", "policy_option_id": oid, "stakeholder_type": "CONSUMER",
          "stakeholder_id_or_label": "CONSUMER", "impact_dimension": "RIGHTS", "direction": "BENEFIT",
          "mechanism": "m"}
    _, _, m, coll, _ = run_isolated([pq_rec(), opt_rec(pqid), s1], ti, cm, fam, out_dir=out_dir,
                                     overrides_path=overrides_path)
    for s in coll["stakeholder_impacts"].values():
        assert "priority" not in s and "moral_rank" not in s
    print("test_11 OK")


def test_12_policy_constraint():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    out_dir, overrides_path, pqid, oid = _pq_opt(ti, cm, fam)
    con = {"type": "POLICY_CONSTRAINT", "policy_option_id": oid, "constraint_type": "LEGAL",
           "constraint": "현행법상 규제 권한 불명확", "severity": "MEDIUM"}
    _, _, m, coll, _ = run_isolated([pq_rec(), opt_rec(pqid), con], ti, cm, fam, out_dir=out_dir,
                                     overrides_path=overrides_path)
    assert m["policy_constraints_total"] == 1
    c = next(iter(coll["policy_constraints"].values()))
    assert c["constraint_type"] == "LEGAL"
    print("test_12 OK")


def test_13_feasibility_not_desirability():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    out_dir, overrides_path, pqid = pq_and_dir(ti, cm, fam)
    rec = opt_rec(pqid, evaluation_feasibility="POSITIVE")
    _, _, m, coll, _ = run_isolated([pq_rec(), rec], ti, cm, fam, out_dir=out_dir, overrides_path=overrides_path)
    o = next(iter(coll["policy_options"].values()))
    assert o["evaluation"]["feasibility"] == "POSITIVE"
    assert "desirability" not in o["evaluation"]  # feasibility가 desirability를 자동 생성하지 않음
    print("test_13 OK")


def test_14_policy_uncertainty():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    out_dir, overrides_path, pqid, oid = _pq_opt(ti, cm, fam)
    pu = {"type": "POLICY_UNCERTAINTY", "policy_option_id": oid,
          "uncertainty_type": "IMPLEMENTATION_UNCERTAINTY", "description_code": "ENFORCEMENT_UNCLEAR"}
    _, _, m, coll, _ = run_isolated([pq_rec(), opt_rec(pqid), pu], ti, cm, fam, out_dir=out_dir,
                                     overrides_path=overrides_path)
    assert m["policy_uncertainties_total"] == 1
    print("test_14 OK")


def test_15_research_question_from_gap():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    rq = {"type": "RESEARCH_QUESTION", "question": "실제 사고 유형은 무엇인가?", "question_type": "DESCRIPTIVE",
          "evidence_gap_ids": ["gap1"]}
    _, _, m, coll, _ = run_isolated([rq], ti, cm, fam)
    assert m["research_questions_total"] == 1
    print("test_15 OK")


def test_16_research_question_from_contradiction():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    rq = {"type": "RESEARCH_QUESTION", "question": "상충하는 근거를 어떻게 해석할 것인가?",
          "question_type": "CAUSAL", "counter_hypothesis_ids": ["ch1"]}
    _, _, m, coll, _ = run_isolated([rq], ti, cm, fam)
    assert m["research_questions_total"] == 1
    print("test_16 OK")


def test_17_no_random_research_question():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    rq = {"type": "RESEARCH_QUESTION", "question": "임의 관심 주제", "question_type": "DESCRIPTIVE"}
    _, _, m, *_ = run_isolated([rq], ti, cm, fam)
    assert m["research_questions_total"] == 0
    print("test_17 OK")


def test_18_research_gap():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    gap = {"type": "RESEARCH_GAP", "target_object_type": "STRUCTURAL_CHANGE", "target_object_id": "sc1",
           "gap_type": "NO_CAUSAL_EVIDENCE", "gap_description_code": "NO_CAUSAL_LINK_ESTABLISHED"}
    _, _, m, coll, _ = run_isolated([gap], ti, cm, fam)
    assert m["research_gaps_total"] == 1
    g = next(iter(coll["research_gaps"].values()))
    assert g["gap_type"] == "NO_CAUSAL_EVIDENCE"
    print("test_18 OK")


def test_19_gap_not_absence_proof():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    gap = {"type": "RESEARCH_GAP", "target_object_type": "STRUCTURAL_CHANGE", "target_object_id": "sc1",
           "gap_type": "NO_LONGITUDINAL_DATA", "gap_description_code": "NO_LONGITUDINAL"}
    _, _, m, coll, _ = run_isolated([gap], ti, cm, fam)
    g = next(iter(coll["research_gaps"].values()))
    assert "no_research_exists" not in g and "absence_proven" not in g
    print("test_19 OK")


def test_20_evidence_need():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    rq = {"type": "RESEARCH_QUESTION", "question": "Q1", "question_type": "DESCRIPTIVE",
          "evidence_gap_ids": ["gap1"]}
    out_dir, overrides_path, _, coll, _ = run_isolated([rq], ti, cm, fam)
    rid = next(iter(coll["research_questions"].keys()))
    eneed = {"type": "EVIDENCE_NEED", "evidence_type": "PLATFORM_API_ACCESS_RECORDS",
             "description_code": "API_POLICY_RECORDS", "related_research_question_ids": [rid],
             "priority": "HIGH"}
    _, _, m, coll2, _ = run_isolated([rq, eneed], ti, cm, fam, out_dir=out_dir, overrides_path=overrides_path)
    assert m["evidence_needs_total"] == 1
    print("test_20 OK")


def test_21_evidence_need_not_counter():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    rq = {"type": "RESEARCH_QUESTION", "question": "Q1", "question_type": "DESCRIPTIVE",
          "evidence_gap_ids": ["gap1"]}
    out_dir, overrides_path, _, coll, _ = run_isolated([rq], ti, cm, fam)
    rid = next(iter(coll["research_questions"].keys()))
    eneed = {"type": "EVIDENCE_NEED", "evidence_type": "DEPLOYMENT_DATA", "description_code": "MISSING_DATASET",
             "related_research_question_ids": [rid]}
    _, _, m, *_ = run_isolated([rq, eneed], ti, cm, fam, out_dir=out_dir, overrides_path=overrides_path)
    assert m["evidence_needs_total"] == 1
    # Evidence Need가 생성돼도 Counter Evidence(5E 개념)는 여기서 생성되지 않음 — 구조상 무관 컬렉션
    print("test_21 OK")


def test_22_monitoring_indicator():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    mon = {"type": "MONITORING_INDICATOR", "indicator_name": "AGENT_AUTH_ADOPTION",
           "indicator_type": "ADOPTION", "measurement_definition": "agent-specific authentication를 제공하는 주요 플랫폼 수",
           "unit": "COUNT", "direction_of_interest": "INCREASING"}
    _, _, m, coll, _ = run_isolated([mon], ti, cm, fam)
    assert m["monitoring_indicators_total"] == 1
    print("test_22 OK")


def test_23_indicator_null_not_zero():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    mon = {"type": "MONITORING_INDICATOR", "indicator_name": "NO_DATA_YET",
           "measurement_definition": "명확한 정의, 데이터 없음"}
    _, _, m, coll, _ = run_isolated([mon], ti, cm, fam)
    ind = next(iter(coll["monitoring_indicators"].values()))
    assert ind["baseline_value"] is None and ind["latest_value"] is None
    assert ind["status"] == "MONITORING_CANDIDATE"
    print("test_23 OK")


def test_24_indicator_not_forecast():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    mon = {"type": "MONITORING_INDICATOR", "indicator_name": "IND1", "measurement_definition": "def"}
    _, _, m, *_ = run_isolated([mon], ti, cm, fam)
    assert m["monitoring_indicators_total"] == 1
    assert "forecasts_total" not in m  # 5G는 Forecast를 생성하지 않는다
    print("test_24 OK")


def test_25_policy_research_loop_lineage():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    out_dir, overrides_path, pqid = pq_and_dir(ti, cm, fam)
    rq = {"type": "RESEARCH_QUESTION", "question": "Q1", "question_type": "DESCRIPTIVE",
          "related_policy_question_ids": [pqid]}
    out_dir, overrides_path, _, coll, _ = run_isolated([pq_rec(), rq], ti, cm, fam, out_dir=out_dir,
                                                        overrides_path=overrides_path)
    rid = next(iter(coll["research_questions"].keys()))
    eneed = {"type": "EVIDENCE_NEED", "evidence_type": "DATA1", "description_code": "D1",
             "related_research_question_ids": [rid]}
    mon = {"type": "MONITORING_INDICATOR", "indicator_name": "IND_LOOP", "measurement_definition": "def",
           "related_monitoring_indicator_ids": []}
    _, _, m, coll2, _ = run_isolated([pq_rec(), rq, eneed, mon], ti, cm, fam, out_dir=out_dir,
                                      overrides_path=overrides_path)
    assert m["policy_questions_total"] == 1 and m["research_questions_total"] == 1 and m["evidence_needs_total"] == 1
    print("test_25 OK")


def test_26_multiple_options_no_winner():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    out_dir, overrides_path, pqid = pq_and_dir(ti, cm, fam)
    recs = [pq_rec(), opt_rec(pqid, "A"), opt_rec(pqid, "B")]
    _, _, m, coll, _ = run_isolated(recs, ti, cm, fam, out_dir=out_dir, overrides_path=overrides_path)
    assert m["policy_options_total"] == 2
    print("test_26 OK")


def test_27_multiple_tradeoffs():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    out_dir, overrides_path, pqid, oid = _pq_opt(ti, cm, fam)
    t1 = {"type": "POLICY_TRADEOFF", "policy_option_id": oid, "dimension_a": "SAFETY",
          "direction_a": "INCREASING", "dimension_b": "ACCESS", "direction_b": "DECREASING",
          "mechanism": "m1", "evidence_ids": ["e1"]}
    t2 = {"type": "POLICY_TRADEOFF", "policy_option_id": oid, "dimension_a": "COST",
          "direction_a": "INCREASING", "dimension_b": "ENFORCEABILITY", "direction_b": "INCREASING",
          "mechanism": "m2", "evidence_ids": ["e2"]}
    records = [pq_rec(), opt_rec(pqid), t1, t2]
    _, _, m, coll, _ = run_isolated(records, ti, cm, fam, out_dir=out_dir, overrides_path=overrides_path)
    assert m["policy_tradeoffs_total"] == 2
    print("test_27 OK")


def test_28_normative_assumption_separated():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    out_dir, overrides_path, pqid = pq_and_dir(ti, cm, fam)
    rec = opt_rec(pqid, normative_assumption_ids=["norm1"])
    _, _, m, coll, _ = run_isolated([pq_rec(), rec], ti, cm, fam, out_dir=out_dir, overrides_path=overrides_path)
    o = next(iter(coll["policy_options"].values()))
    assert o["normative_assumption_ids"] == ["norm1"]
    print("test_28 OK")


def test_29_jurisdiction_not_generalized():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    out_dir, overrides_path, pqid = pq_and_dir(ti, cm, fam)
    rec = opt_rec(pqid, jurisdiction="EU")
    _, _, m, coll, _ = run_isolated([pq_rec(), rec], ti, cm, fam, out_dir=out_dir, overrides_path=overrides_path)
    o = next(iter(coll["policy_options"].values()))
    assert o["jurisdiction"] == "EU"  # KR로 일반화되지 않음
    print("test_29 OK")


def test_30_temporal_validity_null_preserved():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    out_dir, overrides_path, pqid = pq_and_dir(ti, cm, fam)
    rec = opt_rec(pqid, valid_from="2026-01-01")
    _, _, m, coll, _ = run_isolated([pq_rec(), rec], ti, cm, fam, out_dir=out_dir, overrides_path=overrides_path)
    o = next(iter(coll["policy_options"].values()))
    assert o["valid_from"] == "2026-01-01" and o["valid_to"] is None
    print("test_30 OK")


def test_31_current_law_not_option():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    # CURRENT_LAW 타입 레코드는 POLICY_OPTION 생성기가 처리하지 않음(다른 type 문자열)
    rec = {"type": "CURRENT_LAW", "law_name": "Existing Liability Act"}
    _, _, m, *_ = run_isolated([rec], ti, cm, fam)
    assert m["policy_options_total"] == 0
    print("test_31 OK")


def test_32_research_news_not_research():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    # DOCUMENT 타입(뉴스)은 RESEARCH_QUESTION 생성기가 처리하지 않음
    rec = {"type": "DOCUMENT", "title": "AI 연구 관련 뉴스 기사"}
    _, _, m, *_ = run_isolated([rec], ti, cm, fam)
    assert m["research_questions_total"] == 0
    print("test_32 OK")


def test_33_primary_evidence_unknown_preserved():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    gap = {"type": "RESEARCH_GAP", "target_object_type": "STRUCTURAL_CHANGE", "target_object_id": "sc1",
           "gap_type": "NO_PRIMARY_EVIDENCE", "gap_description_code": "MISSING_PRIMARY_EVIDENCE"}
    _, _, m, coll, _ = run_isolated([gap], ti, cm, fam)
    g = next(iter(coll["research_gaps"].values()))
    assert g["gap_type"] == "NO_PRIMARY_EVIDENCE"
    print("test_33 OK")


def test_34_cross_domain():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    rec = pq_rec(affected_domains=["TECHNOLOGY_INFRASTRUCTURE", "POLICY_LAW_GOVERNANCE",
                                   "ECONOMY_INDUSTRY_LABOR", "HUMAN_SOCIETY_EDUCATION"])
    _, _, m, coll, _ = run_isolated([rec], ti, cm, fam)
    pq = next(iter(coll["policy_questions"].values()))
    assert set(pq["affected_domains"]) == {"TECHNOLOGY_INFRASTRUCTURE", "POLICY_LAW_GOVERNANCE",
                                            "ECONOMY_INDUSTRY_LABOR", "HUMAN_SOCIETY_EDUCATION"}
    print("test_34 OK")


def test_35_planet_domain():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    rec = pq_rec(affected_domains=["PLANET"], question_type="ENERGY")
    _, _, m, coll, _ = run_isolated([rec], ti, cm, fam)
    pq = next(iter(coll["policy_questions"].values()))
    assert "PLANET" in pq["affected_domains"]
    print("test_35 OK")


def test_36_culture_domain():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    rec = pq_rec(affected_domains=["CULTURE_ARTS_MEDIA"], question_type="CREATIVE_RIGHTS")
    _, _, m, coll, _ = run_isolated([rec], ti, cm, fam)
    pq = next(iter(coll["policy_questions"].values()))
    assert "CULTURE_ARTS_MEDIA" in pq["affected_domains"]
    print("test_36 OK")


def test_37_epistemic_ceiling():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    out_dir, overrides_path, pqid, oid = _pq_opt(ti, cm, fam)
    tof = {"type": "POLICY_TRADEOFF", "policy_option_id": oid, "dimension_a": "SAFETY",
           "direction_a": "INCREASING", "dimension_b": "ACCESS", "direction_b": "DECREASING",
           "mechanism": "m", "evidence_ids": ["e1"]}
    _, _, m, coll, assessments = run_isolated([pq_rec(), opt_rec(pqid), tof], ti, cm, fam,
                                               out_dir=out_dir, overrides_path=overrides_path)
    a = next(iter(assessments.values()))
    assert a["epistemic_ceiling"] == "MEDIUM"
    print("test_37 OK")


def test_38_uncertainty_propagation():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    rec = pq_rec(uncertainty_ids=["unc_causality"])
    _, _, m, coll, _ = run_isolated([rec], ti, cm, fam)
    pq = next(iter(coll["policy_questions"].values()))
    assert pq["uncertainty_ids"] == ["unc_causality"]
    print("test_38 OK")


def test_39_falsifier_propagation():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    rec = pq_rec(falsifier_ids=["fls1"])
    rq = {"type": "RESEARCH_QUESTION", "question": "Q1", "question_type": "DESCRIPTIVE",
          "evidence_gap_ids": ["gap1"]}
    out_dir, overrides_path, _, coll, _ = run_isolated([rec, rq], ti, cm, fam)
    pq = next(iter(coll["policy_questions"].values()))
    assert pq["falsifier_ids"] == ["fls1"]
    print("test_39 OK")


def test_40_human_reject_persists():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    out_dir, overrides_path, pqid = pq_and_dir(ti, cm, fam)
    records = [pq_rec(), opt_rec(pqid)]
    out_dir, overrides_path, _, coll, _ = run_isolated(records, ti, cm, fam, out_dir=out_dir,
                                                        overrides_path=overrides_path)
    oid = next(iter(coll["policy_options"].keys()))
    overrides = json.loads(overrides_path.read_text(encoding="utf-8"))
    overrides["policy_options"]["human_rejected"].append(oid)
    overrides_path.write_text(json.dumps(overrides), encoding="utf-8")
    for _ in range(3):
        _, _, _, coll, _ = run_isolated(records, ti, cm, fam, out_dir=out_dir, overrides_path=overrides_path)
        assert coll["policy_options"][oid]["status"] == "HUMAN_REJECTED"
    print("test_40 OK")


def test_41_memory_preserves_undetected():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    out_dir, overrides_path, pqid = pq_and_dir(ti, cm, fam)
    _, _, _, coll, _ = run_isolated([], ti, cm, fam, out_dir=out_dir, overrides_path=overrides_path)
    assert pqid in coll["policy_questions"]  # 재감지 안 돼도 보존
    print("test_41 OK")


def test_42_idempotency():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    out_dir, overrides_path = isolated_dir()
    rec = pq_rec()
    _, _, _, coll1, _ = run_isolated([rec], ti, cm, fam, out_dir=out_dir, overrides_path=overrides_path)
    ids1 = sorted(coll1["policy_questions"].keys())
    _, _, _, coll2, _ = run_isolated([rec], ti, cm, fam, out_dir=out_dir, overrides_path=overrides_path)
    ids2 = sorted(coll2["policy_questions"].keys())
    assert ids1 == ids2
    print("test_42 OK")


def test_43_lineage():
    ti, cm, fam = futures_context(("sc1", "MEDIUM", "fa1"))
    out_dir, overrides_path, pqid = pq_and_dir(ti, cm, fam)
    rq = {"type": "RESEARCH_QUESTION", "question": "Q1", "question_type": "DESCRIPTIVE",
          "related_policy_question_ids": [pqid]}
    out_dir, overrides_path, _, coll, _ = run_isolated([pq_rec(), rq], ti, cm, fam, out_dir=out_dir,
                                                        overrides_path=overrides_path)
    rid = next(iter(coll["research_questions"].keys()))
    eneed = {"type": "EVIDENCE_NEED", "evidence_type": "D1", "description_code": "D1",
             "related_research_question_ids": [rid]}
    mon = {"type": "MONITORING_INDICATOR", "indicator_name": "IND", "measurement_definition": "def"}
    _, _, m, coll2, assessments = run_isolated([pq_rec(), rq, eneed, mon], ti, cm, fam, out_dir=out_dir,
                                                overrides_path=overrides_path)
    a = next(iter(assessments.values()))
    assert pqid in a["policy_question_ids"] and rid in a["research_question_ids"]
    eid = next(iter(coll2["evidence_needs"].keys()))
    assert rid in coll2["evidence_needs"][eid]["related_research_question_ids"]
    print("test_43 OK")


def test_44_empty_state():
    ti, cm, fam = futures_context()  # 5F Futures Assessment 0건
    _, _, m, *_ = run_isolated([], ti, cm, fam)
    for name in ("policy_questions_total", "policy_options_total", "policy_tradeoffs_total",
                 "stakeholder_impacts_total", "policy_constraints_total", "policy_uncertainties_total",
                 "research_questions_total", "research_gaps_total", "evidence_needs_total",
                 "monitoring_indicators_total", "policy_research_assessments_total"):
        assert m[name] == 0, name
    print("test_44 OK")


def run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
    print(f"\n{len(fns)}/{len(fns)} PASSED")


if __name__ == "__main__":
    run_all()
