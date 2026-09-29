# STAGE 7 PHASE C — Evidence Sufficiency. 섹션 19: 단일 Truth Score 금지 - 분리 평가 후
# 가능한 state 중 하나를 반환한다. 섹션 20/21: Claim Ceiling / Interpretation Distance도
# 여기서 함께 매긴다(Evidence가 허용하는 것보다 강하게 만들지 않는다).
#
# PHASE G-K CHECKPOINT REMEDIATION: source_independence/interpretation_distance는 더 이상
# 고정 "UNKNOWN" placeholder가 아니다 - 실제로 계산되고, 계산 결과가 state 판정에도
# 영향을 준다(Te 지시: metadata로만 두지 말 것). intent도 못 알아낸 UNKNOWN이나 evidence
# 0건일 때는 여전히 정직하게 UNKNOWN/INSUFFICIENT를 유지한다.
import interpretation_distance as interp_mod
import source_independence as indep_mod
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

    # 실제 provenance 신호로 Source Independence 계산(섹션 4 Te 지시: 새 source-truth
    # 시스템을 만들지 않고 기존 provenance만 재사용). retrieval_results 각 항목의
    # "provenance"는 retriever.py가 provenance.reconstruct()로 이미 채운 trail이다.
    independence = indep_mod.assess_independence(
        [(r["note_id"], r.get("provenance", [])) for r in retrieval_results], reports_on_pairs=None
    )
    evidence_family_count = independence["evidence_family_count"]

    dimensions = {
        "source_quality": "UNKNOWN",
        "primary_source_coverage": "UNKNOWN",
        "directness": "HIGH" if n > 0 else "NONE",
        "source_independence": independence["overall_status"],
        "evidence_family_count": evidence_family_count,
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

        # 섹션 4(Te 지시): Source Independence가 실제로 sufficiency에 영향을 줘야 한다 -
        # 단순 metadata가 아니다. supporting evidence 전체가 하나의 evidence_family
        # (SHARED_ORIGIN - 같은 문서/같은 URL)에서 나왔다면, counter evidence가 있어도
        # "독립적으로 검증됐다"고 말할 수 없다 - HYPOTHESIS_TEST 격상을 보류한다.
        if state == "SUFFICIENT_FOR_HYPOTHESIS_TEST" and n >= 2 and independence["overall_status"] == "SHARED_ORIGIN":
            state = "SUFFICIENT_FOR_LIMITED_INTERPRETATION"
    elif n >= _MIN_SUPPORTING_FOR_DESCRIPTIVE:
        state = "SUFFICIENT_FOR_DESCRIPTIVE_ANALYSIS"
        claim_ceiling = "OBSERVED_CHANGE"
    else:
        state = "INSUFFICIENT_EVIDENCE"
        claim_ceiling = None

    assert state in EVIDENCE_SUFFICIENCY_STATES
    if claim_ceiling is not None:
        assert claim_ceiling in CLAIM_LADDER

    # 섹션 6-11(Te 지시): Interpretation Distance는 실제로 per-response 계산되고,
    # interpretation_ceiling에 대해 검증된다 - Claim Ceiling과는 별개의 AND-gate.
    computed = interp_mod.compute_interpretation_distance(intent, evidence_family_count)
    ceiling_index = interp_mod.interpretation_ceiling_index_for_claim_ceiling(claim_ceiling)
    final_index, was_capped = interp_mod.enforce_interpretation_ceiling(
        computed["level_index"], ceiling_index
    )
    interpretation_distance = {
        "level_name": interp_mod.DISTANCE_LEVELS[final_index],
        "level_index": final_index,
        "computed_level_name": computed["level_name"],
        "computed_level_index": computed["level_index"],
        "downgraded_for_single_event": computed["downgraded_for_single_event"],
        "capped_by_interpretation_ceiling": was_capped,
    }
    interpretation_ceiling_name = interp_mod.DISTANCE_LEVELS[ceiling_index]

    return {
        "state": state,
        "claim_ceiling": claim_ceiling,
        "interpretation_distance": interpretation_distance,
        "interpretation_ceiling": interpretation_ceiling_name,
        "dimensions": dimensions,
    }
