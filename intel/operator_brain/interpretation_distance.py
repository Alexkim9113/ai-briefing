# STAGE 7 PHASE G-K CHECKPOINT REMEDIATION (item 2/3) — Interpretation Distance.
# Te 지시: intel/interpretive_contract/schema.py에 이미 있는 0-5 정의를 재사용한다
# (새로 재정의 금지). 텍스트 keyword 감지가 아니라 질문의 구조(intent)와 실제 retrieval
# 구조(source_independence.assess_independence()가 계산한 evidence_family_count)로
# 계산한다 - 응답 문장을 파싱해서 판단하지 않는다. 단일 event/단일 evidence family로
# Distance 3 이상을 만들지 않는다(interpretive_contract의
# MIN_INDEPENDENT_EVIDENCE_FOR_DISTANCE를 그대로 재사용). Claim Ceiling과는 별개의
# AND-gate로 적용한다(섹션 11 마지막).
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
IC_DIR = HERE.parent / "interpretive_contract"


def _load_ic_schema():
    key = "_ic_for_operator_brain__schema"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, IC_DIR / "schema.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


_ic = _load_ic_schema()
DISTANCE_LEVELS = _ic.INTERPRETATION_DISTANCE_LEVELS
DISTANCE_INDEX = _ic.INTERPRETATION_DISTANCE_INDEX

# intent(질문의 구조) -> baseline distance level. 이것은 "질문 자체가 어떤 종류의
# 추론을 요구하는가"에 대한 표이지, 응답 텍스트에서 단어를 찾는 것이 아니다.
_INTENT_BASELINE_DISTANCE = {
    "FACT_LOOKUP": "FACT", "EVENT_LOOKUP": "FACT",
    "CHANGE_ANALYSIS": "DIRECT_INTERPRETATION", "TREND_ANALYSIS": "DIRECT_INTERPRETATION",
    "STRUCTURAL_ANALYSIS": "STRUCTURAL_INTERPRETATION",
    "CONNECTION_DISCOVERY": "STRUCTURAL_INTERPRETATION",
    "CONTRADICTION_SEARCH": "STRUCTURAL_INTERPRETATION",
    "QUESTION_EXPLORATION": "CONCEPTUAL_HUMANISTIC_INTERPRETATION",
    "POLICY_EXPLORATION": "CONCEPTUAL_HUMANISTIC_INTERPRETATION",
    "RESEARCH_GAP": "CONCEPTUAL_HUMANISTIC_INTERPRETATION",
    "HYPOTHESIS_TEST": "FORWARD_IMPLICATION",
    "UNCERTAINTY_ANALYSIS": "FORWARD_IMPLICATION",
    "VIEW_REVISION": "FORWARD_IMPLICATION",
    "TEMPORAL_COMPARISON": "FORWARD_IMPLICATION",
    "FUTURES_EXPLORATION": "HYPOTHESIS_SCENARIO",
    "GENERAL_SYNTHESIS": "FACT",
    "COUNTER_EVIDENCE_SEARCH": "FACT",
    "UNKNOWN": "FACT",
}


def compute_interpretation_distance(intent, evidence_family_count):
    baseline = _INTENT_BASELINE_DISTANCE.get(intent, "FACT")
    idx = DISTANCE_INDEX[baseline]
    while idx >= 3 and evidence_family_count < _ic.min_independent_evidence_required(DISTANCE_LEVELS[idx]):
        idx -= 1
    return {
        "level_name": DISTANCE_LEVELS[idx],
        "level_index": idx,
        "baseline_level_name": baseline,
        "downgraded_for_single_event": DISTANCE_LEVELS[idx] != baseline,
    }


def interpretation_ceiling_index_for_claim_ceiling(claim_ceiling_name):
    """CLAIM_LADDER(9단계)와 INTERPRETATION_DISTANCE(6단계)는 서로 다른 축이다(섹션 11:
    둘을 하나로 합치지 않는다) - 여기서는 새 매핑 표를 만들지 않고, Evidence
    Sufficiency가 이미 정한 claim_ceiling의 CLAIM_LADDER 내 위치를 6단계 범위로
    보수적으로 눌러(clip) ceiling으로만 쓴다. claim_ceiling이 없으면(증거 0건)
    가장 보수적인 0(FACT)."""
    from schema import CLAIM_LADDER
    if claim_ceiling_name not in CLAIM_LADDER:
        return 0
    return min(CLAIM_LADDER.index(claim_ceiling_name), len(DISTANCE_LEVELS) - 1)


def enforce_interpretation_ceiling(computed_index, ceiling_index):
    """Claim Ceiling 검사(epistemic_guard.check_claim_ceiling)와는 별개의 AND-gate.
    넘으면 실제로 낮춘다(플래그만 남기고 통과시키지 않는다)."""
    if ceiling_index is None:
        return computed_index, False
    if computed_index > ceiling_index:
        return ceiling_index, True
    return computed_index, False
