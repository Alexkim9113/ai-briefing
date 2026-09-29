# STAGE 7 PHASE C — Evidence Sufficiency. 섹션 19: 단일 Truth Score 금지 - 분리 평가 후
# 가능한 state 중 하나를 반환한다. 섹션 20/21: Claim Ceiling / Interpretation Distance도
# 여기서 함께 매긴다(Evidence가 허용하는 것보다 강하게 만들지 않는다).
from schema import CLAIM_LADDER, EVIDENCE_SUFFICIENCY_STATES

# FACT/EVENT는 Stage 6 atomizer가 이미 claim_ceiling=0(OBSERVED_FACT)로 만들어 둔 것과
# 같은 원칙 - 이 Phase는 그 원칙을 retrieval 결과 레벨에서도 지킨다: 최소 지지 개수 미만이면
# 절대 CEILING을 올리지 않는다.
_MIN_SUPPORTING_FOR_DESCRIPTIVE = 1
_MIN_SUPPORTING_FOR_HYPOTHESIS_TEST = 1  # + counter_evidence 존재 여부로 더 세분화


def assess(retrieval_results, intent, counter_evidence_results=None):
    counter_evidence_results = counter_evidence_results or []
    n = len(retrieval_results)
    n_counter = len(counter_evidence_results)

    # 각 차원을 분리 평가 (섹션 19) - 아직 이 corpus엔 independence/scope-match 계산에
    # 필요한 원본 필드(source_independence 등)가 없으므로 UNKNOWN으로 정직하게 둔다.
    dimensions = {
        "source_quality": "UNKNOWN",
        "primary_source_coverage": "UNKNOWN",
        "directness": "HIGH" if n > 0 else "NONE",
        "source_independence": "UNKNOWN",
        "temporal_coverage": "UNKNOWN",
        "scope_match": "UNKNOWN",
        "domain_diversity": "UNKNOWN",
        "measurement_quality": "UNKNOWN",
        "supporting_evidence_count": n,
        "counter_evidence_count": n_counter,
        "contradictions": [],
        "alternative_explanations": [],
        "evidence_gaps": [],
    }

    if n == 0:
        state = "INSUFFICIENT_EVIDENCE"
        claim_ceiling = None
    elif intent == "FACT_LOOKUP" or intent == "EVENT_LOOKUP":
        state = "SUFFICIENT_FOR_FACT_LOOKUP"
        claim_ceiling = "OBSERVED_FACT"
    elif intent == "HYPOTHESIS_TEST":
        if n >= _MIN_SUPPORTING_FOR_HYPOTHESIS_TEST and n_counter > 0:
            state = "SUFFICIENT_FOR_HYPOTHESIS_TEST"
        elif n >= _MIN_SUPPORTING_FOR_HYPOTHESIS_TEST and n_counter == 0:
            # 반증 후보를 못 찾았다고 해서 SUFFICIENT로 격상하지 않는다 - 섹션 3
            # "COUNTER-EVIDENCE BEFORE CONCLUSION".
            state = "SUFFICIENT_FOR_LIMITED_INTERPRETATION"
        else:
            state = "INSUFFICIENT_EVIDENCE"
        claim_ceiling = "HYPOTHESIS_FUTURES"
    elif n >= _MIN_SUPPORTING_FOR_DESCRIPTIVE:
        state = "SUFFICIENT_FOR_DESCRIPTIVE_ANALYSIS"
        claim_ceiling = "OBSERVED_CHANGE"
    else:
        state = "INSUFFICIENT_EVIDENCE"
        claim_ceiling = None

    assert state in EVIDENCE_SUFFICIENCY_STATES
    if claim_ceiling is not None:
        assert claim_ceiling in CLAIM_LADDER

    return {
        "state": state,
        "claim_ceiling": claim_ceiling,
        "dimensions": dimensions,
    }
