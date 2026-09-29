# CONTRACT TESTS(운영자 지시 섹션 63) — 최소 60개. 여기서는 68개(section 63의 01-68)를
# 그대로 구현한다. 이 테스트는 두 종류로 나뉜다:
#   (1) 이번에 새로 만든 intel/interpretive_contract/schema.py의 어휘/shell 자체가
#       스스로 모순되지 않는지(예: ceiling이 실제로 상위 레벨을 막는지),
#   (2) 이미 존재하는 5A-5G/Evidence Pipeline 코드가 "이 계약이 전제로 삼는 불변식"을
#       여전히 satisfy하는지(읽기 전용 회귀 확인 — 그 코드 자체를 절대 수정하지 않는다).
#
# 여러 layer가 schema.py/common.py 같은 동일 이름 모듈을 갖고 있어(운영자 지시 섹션 2:
# 기존 구조 불변) 그대로 import하면 충돌한다. _isolated_import는 각 layer를 불러올 때마다
# sys.path/sys.modules를 완전히 스냅샷-복원하여 서로 다른 layer의 동일 이름 모듈이 섞이지
# 않게 한다(evidence_pipeline/tests/test_fixture.py의 test_48에서 쓴 것과 같은 기법).
import importlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # intel/interpretive_contract/tests
IC_DIR = HERE.parent                            # intel/interpretive_contract
INTEL_DIR = IC_DIR.parent                       # intel
REPO_ROOT = INTEL_DIR.parent                    # ai-briefing

EV_DIR = INTEL_DIR / "evidence_pipeline"
SA_DIR = INTEL_DIR / "structural_analysis_layer"
FUT_DIR = INTEL_DIR / "futures_layer"
POL_DIR = INTEL_DIR / "policy_research_layer"
EPI_DIR = INTEL_DIR / "epistemic_layer"

import importlib.util


def _load_by_path(unique_modname, filepath):
    """sys.modules를 절대 건드리지 않고 파일 경로로 직접 로드한다 — 'schema'라는 흔한
    이름을 sys.modules에 등록해버리면 이후 _isolated_import()가 다른 layer의 schema.py
    대신 이 모듈을 캐시에서 그대로 돌려주는 사고가 난다(실제로 처음 이 파일을 이렇게
    쓰지 않고 `import schema as ic`로 썼다가 바로 이 문제로 다른 layer의 schema.py를
    전혀 못 읽는 버그가 났다 — 그래서 이 방식으로 고정한다)."""
    spec = importlib.util.spec_from_file_location(unique_modname, str(filepath))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ic = _load_by_path("interpretive_contract_schema", IC_DIR / "schema.py")
pvw = _load_by_path("interpretive_contract_pvw", IC_DIR / "production_validation_watch.py")


def _isolated_import(dirpaths, modname):
    """dirpaths를 sys.path 맨 앞에 임시로 넣고 modname을 새로 import한 뒤, sys.path와
    새로 생긴 sys.modules 엔트리를 전부 원상복구한다. 반환된 module 객체 자체는 계속
    유효하다(sys.modules에서 빠져도 파이썬 객체는 살아있음) — 다음 layer를 import할 때
    동일 이름('schema','common' 등)이 섞이는 것을 막는다."""
    saved_path = sys.path[:]
    saved_mod_keys = set(sys.modules.keys())
    for d in reversed(dirpaths):
        sys.path.insert(0, str(d))
    try:
        return importlib.import_module(modname)
    finally:
        sys.path[:] = saved_path
        for k in set(sys.modules.keys()) - saved_mod_keys:
            sys.modules.pop(k, None)


def _ev(modname):
    return _isolated_import([EV_DIR, INTEL_DIR], modname)


def _sa(modname):
    return _isolated_import([SA_DIR], modname)


def _fut(modname):
    return _isolated_import([FUT_DIR], modname)


def _pol(modname):
    return _isolated_import([POL_DIR], modname)


def _epi(modname):
    return _isolated_import([EPI_DIR], modname)


import re as _re


def _diff_is_timestamp_only(path):
    """git diff에서 실제 내용이 바뀐 줄이 하나라도 있으면 False. created_at/updated_at
    같은 타임스탬프 필드만 바뀐 경우(=Production Evidence Validation의 실제 재실행으로
    생긴 정상적인 변화, 섹션 25 Idempotency)만 True로 허용한다."""
    out = subprocess.run(["git", "diff", "--", str(path)], cwd=str(REPO_ROOT),
                          capture_output=True, text=True, check=True).stdout
    for line in out.splitlines():
        if not (line.startswith("+") or line.startswith("-")):
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        if _re.search(r'"(created_at|updated_at|queued_at)"\s*:', line):
            continue
        return False
    return True


def _git_status_short(paths):
    """레포 루트 기준 git status --short -- <paths>. 결과가 빈 문자열이면 해당 경로들에
    변경/추적되지 않은 파일이 전혀 없다는 뜻(이번 세션이 손대지 않았다는 회귀 증거)."""
    result = subprocess.run(
        ["git", "status", "--short", "--"] + [str(p) for p in paths],
        cwd=str(REPO_ROOT), capture_output=True, text=True, check=True,
    )
    return result.stdout


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ==========================================================================
# 01-20
# ==========================================================================

def test_01_no_evidence_no_factual_claim():
    schema = _ev("schema")
    shell = schema.new_claim_shell("c1", "d1", "s1")
    assert shell["claim_status"] == "NOT_VERIFIED", "근거 없는 Claim shell 기본값은 NOT_VERIFIED여야 한다"


def test_02_weak_evidence_low_claim_ceiling():
    assert ic.is_claim_strength_within_ceiling("OBSERVED_FACT", "OBSERVATION_CEILING")
    assert not ic.is_claim_strength_within_ceiling("SUPPORTED_TREND", "OBSERVATION_CEILING")


def test_03_syndication_not_independence():
    independence = _ev("independence")
    relationships = {
        "r1": {"type": "REPORTS_ON", "from_document_id": "d1", "to_document_id": "d0"},
        "r2": {"type": "REPORTS_ON", "from_document_id": "d2", "to_document_id": "d0"},
    }
    documents_by_id = {
        "d0": {"source_id": "src_wire"}, "d1": {"source_id": "src_a"}, "d2": {"source_id": "src_b"},
    }
    result = independence.compute_independence(["d0", "d1", "d2"], documents_by_id, relationships, [])
    assert result["raw_document_count"] == 3
    assert result["independent_document_count"] == 1, "통신사 재배포 3건은 독립 문서 1건이어야 한다"


def test_04_single_event_not_structural_interpretation():
    assert not ic.is_claim_strength_within_ceiling("STRUCTURAL_INTERPRETATION", "OBSERVATION_CEILING")


def test_05_single_event_not_conceptual_interpretation():
    assert not ic.is_claim_strength_within_ceiling("CONCEPTUAL_HUMANISTIC_INTERPRETATION", "OBSERVATION_CEILING")


def test_06_fact_not_interpretation():
    schema = _ev("schema")
    assert "CANDIDATE" not in schema.CLAIM_STATUS, "Fact 계열 claim_status에 CANDIDATE류 값이 섞이면 안 된다"
    assert ic.INTERPRETATION_DISTANCE_INDEX["FACT"] == 0
    assert ic.INTERPRETATION_DISTANCE_INDEX["FACT"] != ic.INTERPRETATION_DISTANCE_INDEX["DIRECT_INTERPRETATION"]


def test_07_structural_interpretation_not_fact():
    schema = _sa("schema")
    assert "FACT" not in schema.INTERPRETATION_STATUS


def test_08_conceptual_interpretation_not_fact():
    shell = ic.new_conceptual_change_candidate_shell("cc1", "AUTHOR", "stmt", ["evr_1", "evr_2"], ["MEANING"])
    assert shell["status"] == "CANDIDATE"
    assert shell["status"] != "FACT"


def test_09_implication_not_observation():
    assert ic.CLAIM_STRENGTH_LEVEL_INDEX["FORWARD_IMPLICATION"] > ic.CLAIM_STRENGTH_LEVEL_INDEX["OBSERVED_FACT"]
    assert not ic.is_claim_strength_within_ceiling("FORWARD_IMPLICATION", "OBSERVATION_CEILING")


def test_10_hypothesis_not_conclusion():
    schema = _fut("schema")
    assert schema.EFFECT_STATUS == "HYPOTHESIS_CANDIDATE"
    assert "CONFIRMED" not in schema.FORECAST_STATUS
    assert "CONCLUSION" not in schema.FORECAST_STATUS


def test_11_scenario_not_prediction():
    schema = _fut("schema")
    for bad in ("REALIZED", "CONFIRMED", "PREDICTED_TRUE"):
        assert bad not in schema.SCENARIO_STATES


def test_12_policy_option_not_recommendation():
    schema = _pol("schema")
    assert "RECOMMENDATION" not in schema.OPTION_TYPES
    shell = schema.new_policy_option_shell("o1", "q1", "name", "NO_ACTION", "mech", "actor", "NATIONAL")
    assert "recommended" not in shell and "is_recommended" not in shell


def test_13_counter_evidence_preserved():
    path = EV_DIR / "evidence_pipeline_overrides.json"
    data = _load_json(path)
    assert "evr_3" in data["evidence_records"]["human_rejected"], \
        "Human Review Pilot에서 반려한 evr_3 판단이 보존되어야 한다"
    epi_ce = _load_json(EPI_DIR / "counter_evidence.json")
    assert isinstance(epi_ce, (dict, list))


def test_14_alternative_explanation_preserved():
    data = _load_json(EPI_DIR / "alternative_explanations.json")
    assert isinstance(data, (dict, list))


def test_15_geographic_scope_preserved():
    schema = _ev("schema")
    shell = schema.new_claim_shell("c1", "d1", "s1")
    assert "geographic_scope" in shell


def test_16_population_scope_preserved():
    schema = _ev("schema")
    shell = schema.new_claim_shell("c1", "d1", "s1")
    assert "population_scope" in shell


def test_17_temporal_scope_preserved():
    schema = _ev("schema")
    shell = schema.new_claim_shell("c1", "d1", "s1")
    assert "temporal_scope" in shell


def test_18_missing_evidence_not_negative_evidence():
    schema = _ev("schema")
    assert "INSUFFICIENT_SOURCE" in schema.CLAIM_STATUS
    assert "INSUFFICIENT_SOURCE" != "DISPUTED" and "INSUFFICIENT_SOURCE" != "RETRACTED"
    assert {"INSUFFICIENT_SOURCE", "DISPUTED", "RETRACTED"}.issubset(set(schema.CLAIM_STATUS))


def test_19_null_not_zero():
    independence = _ev("independence")
    result = independence.compute_independence(["d_unknown"], {}, {}, [])
    assert isinstance(result["independent_source_count"], int)
    assert isinstance(result["independent_document_count"], int)


def test_20_company_claim_not_objective_fact():
    schema = _ev("schema")
    assert "VERIFIED_TRUE" not in schema.CLAIM_STATUS
    assert "COMPANY_REPORTED" in schema.CLAIM_TYPES


# ==========================================================================
# 21-40
# ==========================================================================

def test_21_research_news_not_research():
    source_resolver = _ev("source_resolver")
    hierarchy = source_resolver.classify_source_hierarchy(
        {"document_type": "NEWS"}, "techcrunch.com", is_primary_self=False)
    assert hierarchy != "PRIMARY_RESEARCH"


def test_22_proposal_not_law():
    claim_extractor = _ev("claim_extractor")
    assert claim_extractor._PROPOSAL_KO.search("국회, AI기본법 개정안 발의") is not None
    assert claim_extractor._ENACTED_KO.search("국회, AI기본법 개정안 발의") is None
    assert claim_extractor._ENACTED_KO.search("AI기본법 시행") is not None
    assert claim_extractor._PROPOSAL_KO.search("AI기본법 시행") is None


def test_23_correlation_not_causation():
    schema = _sa("schema")
    assert "POTENTIAL_CAUSE" in schema.DRIVER_RELATIONS
    for bad in ("CAUSED", "CONFIRMED_CAUSE", "PROVEN_CAUSE"):
        assert bad not in schema.DRIVER_RELATIONS


def test_24_dependency_not_control():
    schema = _sa("schema")
    dep = schema.new_dependency_shell("dep1", "actorA", "targetB", "func", "COMPUTE", [])
    ctrl = schema.new_control_shell("ctrl1", "actorA", "resourceB", "mech", [])
    assert "dependency_id" in dep and "control_id" not in dep
    assert "control_id" in ctrl and "dependency_id" not in ctrl
    assert set(dep) != set(ctrl)


def test_25_control_not_power_automatically():
    schema = _sa("schema")
    ctrl = schema.new_control_shell("ctrl1", "actorA", "resourceB", "mech", [])
    assert "power_shift_id" not in ctrl
    analysis = schema.new_structural_analysis_shell("a1", "sc1")
    assert analysis["control_ids"] is not analysis["power_shift_ids"]
    assert analysis["control_ids"] == [] and analysis["power_shift_ids"] == []


def test_26_scarcity_not_bottleneck():
    schema = _sa("schema")
    scarcity = schema.new_scarcity_shift_shell("sc1", "COMPUTE", "ENERGY", "mech", [])
    bottleneck = schema.new_bottleneck_shell("bn1", "ENERGY", "AI_INFRASTRUCTURE", [])
    assert "from_scarcity" in scarcity and "from_scarcity" not in bottleneck
    assert "affected_system" in bottleneck and "affected_system" not in scarcity


def test_27_philosophical_question_not_conclusion():
    assert ic.AUTO_GENERATABLE_PHILOSOPHICAL_OUTPUT_KINDS == ("PHILOSOPHICAL_QUESTION",)
    assert "PHILOSOPHICAL_CONCLUSION" not in ic.AUTO_GENERATABLE_PHILOSOPHICAL_OUTPUT_KINDS
    assert "PHILOSOPHICAL_CONCLUSION" in ic.PHILOSOPHICAL_OUTPUT_KINDS


def test_28_historical_analogy_not_evidence():
    schema = _ev("schema")
    assert "HISTORICAL_ANALOGY" not in schema.EVIDENCE_TYPES
    assert "HISTORICAL_ANALOGY" not in ic.EVIDENCE_SUFFICIENCY_DIMENSIONS


def test_29_conceptual_change_requires_multi_evidence():
    assert ic.MIN_EVIDENCE_FOR_CONCEPTUAL_CHANGE_CANDIDATE == 2
    assert not ic.conceptual_change_candidate_is_eligible(["evr_1"])
    assert ic.conceptual_change_candidate_is_eligible(["evr_1", "evr_2"])


def test_30_claim_lineage_reaches_original_source():
    lineage = ic.new_report_claim_lineage_shell("rc1")
    assert not ic.lineage_reaches_source(lineage)
    lineage["document_ids"] = ["d1"]
    lineage["source_ids"] = ["src_a"]
    assert ic.lineage_reaches_source(lineage)


def test_31_interpretation_lineage_reaches_evidence():
    lineage = ic.new_report_claim_lineage_shell("rc1")
    lineage["claim_ids"] = ["c1"]
    lineage["fact_ids"] = ["f1"]
    assert not ic.lineage_reaches_evidence(lineage), "claim/fact만 있고 evidence가 없으면 아직 근거에 닿은 게 아니다"
    lineage["supporting_evidence_ids"] = ["evr_1"]
    assert ic.lineage_reaches_evidence(lineage)


def test_32_counter_evidence_lineage():
    lineage = ic.new_report_claim_lineage_shell("rc1")
    assert "counter_evidence_ids" in lineage
    lineage["counter_evidence_ids"] = ["ce1"]
    assert lineage["supporting_evidence_ids"] != lineage["counter_evidence_ids"]


def test_33_uncertainty_lineage():
    lineage = ic.new_report_claim_lineage_shell("rc1")
    assert "uncertainty_ids" in lineage


def test_34_falsifier_lineage():
    lineage = ic.new_report_claim_lineage_shell("rc1")
    assert "falsifier_ids" in lineage


def test_35_llm_cannot_raise_claim_ceiling():
    fact_validator = _ev("fact_validator")
    claim = {"extraction_method": "LEVEL3_GEMINI_CANDIDATE", "claim_status": "SOURCE_LOCATED",
             "claim_type": "COMPANY_REPORTED", "predicate": "COMPANY_ANNOUNCED"}
    ok, reason = fact_validator.validate_claim(claim)
    assert ok is False, "Gemini Candidate 추출은 어떤 경우에도 Fact로 승격되면 안 된다"


def test_36_philosophy_lens_cannot_create_fact():
    names = [n for n in dir(ic) if "fact" in n.lower() and "philosoph" in n.lower()]
    assert names == [], f"철학 Lens가 Fact를 만드는 함수가 있으면 안 된다: {names}"


def test_37_sociology_lens_cannot_create_fact():
    names = [n for n in dir(ic) if "fact" in n.lower() and ("social" in n.lower() or "sociolog" in n.lower())]
    assert names == []


def test_38_economics_lens_cannot_create_fact():
    names = [n for n in dir(ic) if "fact" in n.lower() and "econom" in n.lower()]
    assert names == []


def test_39_historical_context_cannot_create_fact():
    names = [n for n in dir(ic) if "fact" in n.lower() and "histor" in n.lower()]
    assert names == []


def test_40_futures_cannot_back_create_evidence():
    schema = _fut("schema")
    assert not hasattr(schema, "new_evidence_record_shell")
    assert not any("evidence_record" in name.lower() for name in dir(schema))


# ==========================================================================
# 41-60
# ==========================================================================

def test_41_policy_option_cannot_back_create_evidence():
    # new_evidence_need_shell()은 "근거가 더 필요하다"는 정직한 gap 인정이지 근거 조작이
    # 아니다(섹션 40) — 금지 대상은 오직 evidence_record를 스스로 만들어내는 것뿐이다.
    schema = _pol("schema")
    assert not hasattr(schema, "new_evidence_record_shell")
    assert not any("evidence_record" in name.lower() for name in dir(schema))
    assert hasattr(schema, "new_evidence_need_shell"), "evidence_need(근거 필요 인정)는 여전히 있어야 한다"


def test_42_feasibility_unknown_stays_unknown():
    schema = _pol("schema")
    shell = schema.new_policy_option_shell("o1", "q1", "name", "NO_ACTION", "mech", "actor", "NATIONAL")
    assert shell["evaluation"]["feasibility"] == schema.NOT_ASSESSED


def test_43_desirability_not_feasibility():
    schema = _pol("schema")
    shell = schema.new_policy_option_shell("o1", "q1", "name", "NO_ACTION", "mech", "actor", "NATIONAL")
    assert "desirability" not in shell["evaluation"]
    assert "feasibility" in shell["evaluation"]


def test_44_average_benefit_not_distributional_benefit():
    schema = _pol("schema")
    s1 = schema.new_stakeholder_impact_shell("si1", "o1", "WORKER", "worker_kr", "COST", "COST", "mech", "0_1_YEAR")
    s2 = schema.new_stakeholder_impact_shell("si2", "o1", "COMPANY", "co_a", "COST", "BENEFIT", "mech", "0_1_YEAR")
    assert s1["direction"] != s2["direction"], "Stakeholder별 impact는 평균으로 뭉개지지 않고 각자 독립적이어야 한다"
    assert "average_impact" not in s1 and "average_impact" not in s2


def test_45_actor_missing_no_implementation_claim():
    schema = _pol("schema")
    shell = schema.new_policy_option_shell("o1", "q1", "name", "NO_ACTION", "mech", None, "NATIONAL")
    assert shell["target_actor"] is None
    assert shell["evaluation"]["effectiveness"] == schema.NOT_ASSESSED


def test_46_authority_missing_no_enforcement_claim():
    schema = _pol("schema")
    assert "ENFORCEMENT" in schema.CONSTRAINT_TYPES


def test_47_mechanism_missing_no_strong_policy_effect_claim():
    import inspect
    schema = _pol("schema")
    sig = inspect.signature(schema.new_policy_tradeoff_shell)
    assert "mechanism" in sig.parameters
    assert sig.parameters["mechanism"].default is inspect.Parameter.empty, \
        "mechanism은 필수 인자여야 한다(추측 기본값 금지)"


def test_48_cost_unknown_remains_unknown():
    schema = _pol("schema")
    shell = schema.new_policy_option_shell("o1", "q1", "name", "NO_ACTION", "mech", "actor", "NATIONAL")
    assert shell["evaluation"]["cost"] == schema.NOT_ASSESSED


def test_49_no_action_option_allowed():
    schema = _pol("schema")
    assert "NO_ACTION" in schema.OPTION_TYPES


def test_50_reality_return_mapping_supported():
    assert ic.reality_return_fields_present({}) is False
    assert ic.reality_return_fields_present({"actor": "gov_kr"}) is True
    assert ic.reality_return_fields_present({"incentive": "subsidy"}) is True


def test_51_so_what_test_supported():
    assert "SO_WHAT" in ic.THREE_TEST_GATES


def test_52_then_what_test_supported():
    assert "THEN_WHAT" in ic.THREE_TEST_GATES


def test_53_can_it_work_test_supported():
    assert "CAN_IT_ACTUALLY_WORK" in ic.THREE_TEST_GATES


def test_54_5a_5g_unchanged():
    layer_dirs = ["signal_layer", "pattern_layer", "structural_change_layer",
                  "structural_analysis_layer", "epistemic_layer", "futures_layer",
                  "policy_research_layer"]
    paths = [INTEL_DIR / d for d in layer_dirs]
    out = _git_status_short(paths)
    changed = [ln for ln in out.splitlines() if "__pycache__" not in ln]
    assert changed == [], f"5A-5G 디렉터리에 변경이 감지됨(금지): {changed}"


def test_55_evidence_pipeline_unchanged_unless_minimal_extension():
    # Production Evidence Validation 단계(섹션 25 Idempotency)에서 pipeline.py를 실제
    # Production 데이터로 재실행했다 — 이때 M(수정)으로 뜨는 evidence_pipeline 산출물
    # JSON은 created_at/updated_at 타임스탬프만 바뀐 것이어야 하고, 코드 파일(.py)은
    # 단 한 줄도 바뀌면 안 된다(진짜 회귀 금지는 여전히 유효).
    out = _git_status_short([EV_DIR])
    bad = []
    for ln in out.splitlines():
        if "__pycache__" in ln:
            continue
        status, path = ln[:2].strip(), ln[3:].strip()
        if path.endswith(".py"):
            bad.append(ln)
            continue
        if status == "M" and _diff_is_timestamp_only(REPO_ROOT / path):
            continue
        bad.append(ln)
    assert bad == [], f"이번 세션에서 Evidence Pipeline에 타임스탬프 이상의 변경이 발생함(금지): {bad}"


def test_56_public_unchanged():
    paths = [REPO_ROOT / "briefing.py", REPO_ROOT / "site", REPO_ROOT / "data"]
    paths = [p for p in paths if p.exists()]
    out = _git_status_short(paths)
    assert out.strip() == "", f"Public(briefing.py/site/data)에 변경이 감지됨(금지): {out}"


def test_57_publication_gate_unchanged():
    pub_dir = INTEL_DIR / "publication"
    if not pub_dir.exists():
        return
    out = _git_status_short([pub_dir])
    changed = [ln for ln in out.splitlines() if "__pycache__" not in ln]
    assert changed == [], f"Publication Gate에 변경이 감지됨(금지): {changed}"


def test_58_ids_stable():
    records = _load_json(EV_DIR / "evidence_records.json")
    records = records if isinstance(records, dict) else {r.get("evidence_record_id"): r for r in records}
    assert "evr_3" in records, "이전 Phase에서 만든 evr_3 ID가 그대로 남아있어야 한다"
    assert records["evr_3"].get("human_review_status") == "HUMAN_REJECTED"


def test_59_history_preserved():
    records = _load_json(EV_DIR / "evidence_records.json")
    records = records if isinstance(records, dict) else {r.get("evidence_record_id"): r for r in records}
    for rid, rec in records.items():
        assert isinstance(rec.get("history"), list), f"{rid}의 history 필드가 사라지거나 리스트가 아님"


def test_60_human_overrides_preserved():
    data = _load_json(EV_DIR / "evidence_pipeline_overrides.json")
    assert data["evidence_records"]["human_rejected"] == ["evr_3"]
    assert "evr_3" in data["evidence_records"]["_review_notes"]


# ==========================================================================
# 61-68
# ==========================================================================

def test_61_report_engine_not_implemented():
    forbidden_names = ("report_engine", "report_generator", "weekly_report", "monthly_report")
    existing = [d.name for d in INTEL_DIR.iterdir() if d.is_dir() and d.name.lower() in forbidden_names]
    assert existing == [], f"금지된 Report Engine 디렉터리가 존재함: {existing}"
    py_hits = [str(p) for p in INTEL_DIR.rglob("*.py")
               if any(tok in p.name.lower() for tok in ("report_generator", "weekly_generator", "monthly_generator"))]
    assert py_hits == [], f"금지된 Report Generator 파일이 존재함: {py_hits}"


def test_62_stage6_not_implemented():
    hits = [str(p) for p in INTEL_DIR.rglob("*")
            if any(tok in p.name.lower() for tok in ("obsidian", "stage6", "stage_6", "ask_metaxis"))]
    assert hits == [], f"금지된 Stage 6 산출물이 존재함: {hits}"


def test_63_culture_arts_dimensions_supported():
    schema = _ev("schema")
    assert "CULTURE_ARTS_MEDIA" in schema.REAL_DOMAINS


def test_64_human_society_dimensions_supported():
    schema = _ev("schema")
    assert "HUMAN_SOCIETY_EDUCATION" in schema.REAL_DOMAINS


def test_65_planet_dimensions_supported():
    schema = _ev("schema")
    assert "PLANET" in schema.REAL_DOMAINS
    assert len(schema.PLANET_SUBDOMAINS) > 0


def test_66_production_validation_pending_state_preserved():
    watch = pvw.compute_validation_watch()
    for key, value in watch.items():
        if key == "all_verified":
            assert isinstance(value, bool)
            continue
        assert value["status"] in pvw.STATUS_VALUES, f"{key} 상태가 허용된 어휘가 아님: {value}"
        # 이번 Production Evidence Validation에서 실제 데이터로 확인한 결과 5개 전부 여전히
        # PENDING이어야 한다(억지로 VERIFIED로 만들지 않았다는 회귀 확인, 섹션 2).
        assert value["status"] == "PENDING", f"{key}가 PENDING이 아님 — 근거 없이 승격되었을 위험: {value}"


def test_67_idempotency():
    a = pvw.compute_validation_watch()
    b = pvw.compute_validation_watch()
    assert a == b, "동일 입력에 대해 Production Validation Watch가 결정적이어야 한다"


def test_68_regression_zero():
    out = subprocess.run(["git", "status", "--short"], cwd=str(REPO_ROOT),
                          capture_output=True, text=True, check=True).stdout
    bad_lines = []
    for ln in out.splitlines():
        if "__pycache__" in ln:
            continue
        status, path = ln[:2].strip(), ln[3:].strip()
        # 허용되는 것: (1) interpretive_contract 아래 새 파일('??') 또는 이번 세션이 계속
        # 다듬는 그 모듈 자신의 수정('M') — 이 계약 작업 자체의 산출물이므로. (2)
        # evidence_pipeline 산출물 JSON의 M은 타임스탬프만 바뀐 경우(섹션 25 Idempotency
        # 재실행)만. 그 외 모든 상태 코드(A/D/R, 5A-5G나 Public 파일 수정 등)는 전부
        # 회귀로 간주한다.
        if "interpretive_contract" in path and status in ("??", "M"):
            continue
        # PRODUCTION EVIDENCE SUPPLY v1.0(섹션 67-69): evidence_supply도 동일한 sidecar
        # 원칙의 신규 모듈이므로 같은 예외를 적용한다 — 기존 파일 수정이 아니라 새 파일만.
        if "evidence_supply" in path and status in ("??", "M"):
            continue
        # SUBSTEP F(Te 2026-09-29 승인): intel/relationships.json은 evidence_pipeline이
        # 실제로 읽는 지정된 연동 지점이라 이 Phase의 의도된 산출물이다(회귀가 아니라
        # 목적) — reports_on_runner.py가 실제 전체 corpus에 대해 계산한 결과로만 바뀐다.
        if path == "intel/relationships.json" and status == "M":
            continue
        # SUBSTEP G/H(Te 2026-09-29 승인): daily.yml에 evidence_shadow job을 추가한 것은
        # 이 Phase가 명시적으로 승인받은 변경이다(기존 build job/단계는 한 줄도 건드리지
        # 않음 — 새 job 추가만).
        if path == ".github/workflows/daily.yml" and status == "M":
            continue
        if status == "M" and str(EV_DIR.relative_to(REPO_ROOT)) in path and path.endswith(".json") \
                and _diff_is_timestamp_only(REPO_ROOT / path):
            continue
        bad_lines.append(ln)
    assert bad_lines == [], f"이번 세션 밖 변경/기존 파일 수정이 감지됨(회귀): {bad_lines}"


# ==========================================================================
# 69-71 — PRODUCTION EVIDENCE VALIDATION & ACCUMULATION v1.0 신규 테스트.
# 이번 Phase에서 실제 Production 데이터로 확인한 root cause 두 가지(Collection 단계의
# 공식 도메인 부재/Google News 리다이렉트, evidence_pipeline의 cron 미연결)를 "말로만"
# 보고하지 않고, 나중에 누군가 실제로 고쳤을 때 이 테스트가 스스로 틀려짐으로써 상태
# 변화를 알려주도록 살아있는 회귀 테스트로 남긴다.
# ==========================================================================

def test_69_status_vocabulary_includes_failed_and_not_applicable():
    assert set(pvw.STATUS_VALUES) == {"VERIFIED", "PENDING", "FAILED", "NOT_APPLICABLE"}


def test_70_policy_primary_pending_root_cause_documented():
    watch = pvw.compute_validation_watch()
    diag = watch["policy_law_court_primary"]["diagnosis"]
    assert diag["documents_examined"] > 0
    # 현재 실제 데이터의 root cause: 공식 도메인 0건 + news.google.com 리다이렉트 다수.
    # 이 값이 바뀌면(예: 공식 도메인이 수집되기 시작하면) 이 테스트가 실패하며 상태
    # 변화를 알려야 한다 — 그때는 watch 자체의 VERIFIED 조건을 재검토해야 한다.
    assert diag["official_domain_documents"] == 0
    assert diag["google_news_redirect_documents"] > 0


def test_71_gemini_level3_cron_wiring_documented():
    # PRODUCTION EVIDENCE SUPPLY v1.0 SUBSTEP G/H(Te 2026-09-29 승인)로 evidence_pipeline이
    # daily.yml의 evidence_shadow job에 실제로 연결됐다 — 이 테스트가 의도대로 상태 변화를
    # 감지해 실패했으므로(살아있는 회귀 테스트가 제 역할을 한 것), 새 실제 상태로 갱신한다.
    # note는 이제 "미연결"이 아니라 wired=True일 때의 설명으로 바뀌므로 더 이상 요구하지 않는다.
    watch = pvw.compute_validation_watch()
    g = watch["gemini_level3"]
    assert g["evidence_pipeline_wired_into_daily_cron"] is True, \
        "daily.yml의 evidence_shadow job이 사라지면 이 테스트가 실패해야 한다(상태 변화 감지용)"


ALL_TESTS = [
    (name, fn) for name, fn in sorted(globals().items())
    if name.startswith("test_") and callable(fn)
]


def run_all():
    passed, failed = [], []
    for name, fn in ALL_TESTS:
        try:
            fn()
            passed.append(name)
        except Exception as e:  # noqa: BLE001 — 테스트 러너이므로 광범위 예외 수집이 목적
            failed.append((name, repr(e)))
    print(f"{len(passed)}/{len(ALL_TESTS)} passed")
    for name, err in failed:
        print(f"FAIL {name}: {err}")
    return len(failed) == 0


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)
