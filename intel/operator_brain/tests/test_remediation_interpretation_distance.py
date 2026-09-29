# PHASE G-K CHECKPOINT REMEDIATION — item 2/3: Interpretation Distance. Te 지시의 7개
# 케이스(A-G): 기존 interpretive_contract 정의 재사용, keyword 감지가 아닌 구조적 계산,
# 단일 event ceiling, Claim Ceiling과 별개의 AND-gate.
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import interpretation_distance as idist  # noqa: E402


def test_case_a_reuses_interpretive_contract_levels_not_reinvented():
    # 새 6단계를 재정의한 게 아니라 interpretive_contract/schema.py의 실제 객체를 그대로 쓴다.
    import importlib.util
    ic_path = PKG_DIR.parent / "interpretive_contract" / "schema.py"
    spec = importlib.util.spec_from_file_location("_verify_ic", ic_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert idist.DISTANCE_LEVELS == mod.INTERPRETATION_DISTANCE_LEVELS


def test_case_b_fact_lookup_is_distance_zero():
    result = idist.compute_interpretation_distance("FACT_LOOKUP", evidence_family_count=1)
    assert result["level_name"] == "FACT"
    assert result["level_index"] == 0


def test_case_c_structural_intent_with_enough_independent_evidence_reaches_level_2():
    result = idist.compute_interpretation_distance("CONNECTION_DISCOVERY", evidence_family_count=1)
    assert result["level_name"] == "STRUCTURAL_INTERPRETATION"
    assert result["level_index"] == 2


def test_case_d_single_event_family_blocks_distance_3_and_above():
    # FUTURES_EXPLORATION의 baseline은 5(HYPOTHESIS_SCENARIO)지만 evidence_family_count=1
    # (단일 event)이면 3 이상으로 못 올라간다 - interpretive_contract의
    # MIN_INDEPENDENT_EVIDENCE_FOR_DISTANCE[3..5]=2를 그대로 적용.
    result = idist.compute_interpretation_distance("FUTURES_EXPLORATION", evidence_family_count=1)
    assert result["level_index"] < 3
    assert result["downgraded_for_single_event"] is True


def test_case_e_two_independent_families_allow_higher_distance():
    result = idist.compute_interpretation_distance("FUTURES_EXPLORATION", evidence_family_count=2)
    assert result["level_name"] == "HYPOTHESIS_SCENARIO"
    assert result["downgraded_for_single_event"] is False


def test_case_f_interpretation_ceiling_is_separate_and_gate_from_claim_ceiling():
    # claim_ceiling이 OBSERVED_FACT(레벨 0)로 낮게 잡혔으면, evidence family가 충분해도
    # interpretation distance는 그 ceiling 위로 못 올라간다 - Claim Ceiling 검사와는
    # 별개의 함수(enforce_interpretation_ceiling)가 독립적으로 이를 강제한다.
    computed = idist.compute_interpretation_distance("FUTURES_EXPLORATION", evidence_family_count=2)
    ceiling_index = idist.interpretation_ceiling_index_for_claim_ceiling("OBSERVED_FACT")
    final_index, was_capped = idist.enforce_interpretation_ceiling(computed["level_index"], ceiling_index)
    assert final_index == 0
    assert was_capped is True


def test_case_g_high_claim_ceiling_does_not_raise_distance_beyond_what_evidence_computed():
    # Ceiling이 관대해도(HYPOTHESIS_FUTURES) 그 자체로 distance를 끌어올리지 않는다 -
    # ceiling은 상한선일 뿐, computed distance보다 낮을 때만 실제로 영향을 준다.
    computed = idist.compute_interpretation_distance("FACT_LOOKUP", evidence_family_count=1)
    ceiling_index = idist.interpretation_ceiling_index_for_claim_ceiling("HYPOTHESIS_FUTURES")
    final_index, was_capped = idist.enforce_interpretation_ceiling(computed["level_index"], ceiling_index)
    assert final_index == 0
    assert was_capped is False


def test_never_computed_from_keyword_matching_in_response_text():
    # compute_interpretation_distance의 시그니처 자체에 응답 텍스트 인자가 없다 - 텍스트를
    # 파싱해서 판단하지 않는다는 것을 구조적으로 보증한다.
    import inspect
    sig = inspect.signature(idist.compute_interpretation_distance)
    assert "text" not in sig.parameters and "response_text" not in sig.parameters
