# Reader Summary -- a one-time, carefully-grounded Korean synthesis layer for the PUBLIC-facing
# pages. This is the single explicit exception, for this project, to the "no LLM-authored
# narrative text" rule: it is Intelligence-product synthesis (reading across a report's own
# KEY_CLAIMS/STATISTICAL_CONTEXT/COUNTEREVIDENCE/ALTERNATIVE_EXPLANATIONS/UNCERTAINTIES/
# WHAT_WE_DO_NOT_KNOW/GEOGRAPHIC_CONTEXT sections AND hypotheses.json's statement/status/
# status_change_rationale fields -- H1-H7 for AI_ENERGY_INFRA, HL1-HL4 for AI_LABOR), not routine
# news summarization, and every sentence below was independently re-verified against the real
# canonical JSON (report_intel_87210a61730c22b9_v4.json, report_intel_dbab7b01963396b5_v3.json,
# hypotheses.json) before being wired in here.
#
# This module is NOT canonical data. It lives in report_engine/ (a presentation-layer artifact,
# exactly like presentation_model.TOPIC_DISPLAY_TITLES), never under intel/claims/,
# intel/hypothesis/, intel/intelligence_objects/, or intel/report_engine/reports/. It must never be
# imported from intel/operator_workspace/ -- the Operator Inspector continues to show full
# canonical hypothesis/claim data, unaffected by this module's existence.
#
# `source_basis` on each entry is Operator-only traceability metadata (real claim_id/hypothesis_id
# strings this summary draws from) -- it is read by tests and may be surfaced in Operator tooling,
# but product_html.py/public_delivery.py never render it on a Public page.

READER_SUMMARIES = {
    "intel_87210a61730c22b9": {
        "topic": "AI_ENERGY_INFRA",
        "current_judgment_ko": (
            "데이터센터의 전력 사용량 증가는 실제로 관측되고 있으며, IEA 등 주요 기관은 AI를 그 증가의 "
            "중요한 동인 중 하나로 지목합니다. 다만 현재 확보된 자료만으로는 전체 전력수요 증가분 중 "
            "AI만의 기여도를 수치로 분리해 확인하기는 어렵습니다. 제조업 회귀, 전기차 보급, 인구 증가 "
            "등 다른 요인도 함께 작용하고 있으며, 전력망 병목은 지역에 따라 다른 형태로 나타납니다."
        ),
        "what_we_know_ko": [
            "글로벌 데이터센터 전력소비는 2017년 이후 연 약 12%씩 증가했고, 2024년 약 415TWh로 세계 "
            "전력의 1.5% 수준으로 관측됩니다(IEA).",
            "IEA는 AI를 이 증가의 가장 중요한 동인으로 지목하지만, 다른 디지털 서비스 성장과의 수치 "
            "구분은 제시하지 않습니다.",
            "아일랜드는 데이터센터가 전체 전력의 22%(2024년, 2015년 5%에서 증가)를 차지한다고 공식 "
            "통계(CSO)가 확인합니다.",
            "미국은 2023년 데이터센터가 전체 전력의 4.4%(176TWh, 2014년 58TWh에서 증가)를 차지했다고 "
            "LBNL/DOE가 관측했습니다.",
            "미국 PJM 지역은 약 130GW가 접속 대기 중이며, 데이터센터와 전력화(전기차 등)가 공동 "
            "원인으로 지목됩니다.",
            "IEA는 2030년 약 945TWh, 2035년 약 1,200TWh를 전망하지만, 이는 실제 관측치가 아닌 "
            "예측값입니다(전망).",
        ],
        "what_we_dont_know_ko": [
            "AI만의 전력소비 기여분을 수치로 분리한 자료는 현재까지 어떤 출처(IEA, LBNL/DOE, 아일랜드 "
            "CSO, 중국·한국 관련 자료 포함)에도 없습니다.",
            "미국의 1인당 전력소비 지표는 2022년 이후 자료가 없어 2023년 이후 AI 데이터센터 확대를 "
            "반영하지 못합니다.",
            "한국 수도권 전력망 병목 관련 수치는 2차 보도에 근거하며, 국정감사 원자료는 독립적으로 "
            "확인되지 않았습니다.",
        ],
        "counterevidence_ko": [
            "전력수요 증가는 제조업 회귀, 기후에 따른 피크부하, 전기차 보급, 인구 증가와도 관련된다는 "
            "근거가 있습니다.",
            "병목의 본질이 발전 부족이 아니라 송배전 접속 지연이라는 근거가 있으나, 이번 라운드에서 "
            "이 근거는 다소 약화되었습니다(H5).",
            "하드웨어·효율 개선이 AI 워크로드 증가분의 일부를 상쇄할 수 있다는 근거가 있으나, 이 "
            "역시 다소 약화되었습니다(H6).",
        ],
        "watch_next_ko": [
            "AI만의 전력 소비 비중을 수치로 분리하는 1차 자료가 나오는지",
            "미국 세계은행 지표가 2023년 이후 자료로 갱신되는지",
            "한국 국정감사 원자료가 직접 확인되는지",
        ],
        "source_basis": [
            "hyp_b0a4bbbc9b601728",  # H1 SUPPORTED
            "hyp_o0_h2_ai_energy_infra",  # H2 SUPPORTED
            "hyp_o0_h3_ai_energy_infra",  # H3 SUPPORTED
            "hyp_o0_h4_ai_energy_infra",  # H4 SUPPORTED
            "hyp_o0_h5_ai_energy_infra",  # H5 WEAKENED
            "hyp_o0_h6_ai_energy_infra",  # H6 WEAKENED
            "claim_afe7cc7b19317ee0",  # ~415 TWh 2024 / ~945 TWh 2030 (IEA)
            "claim_5787125ab5f0110b",  # PJM ~130GW interconnection queue
        ],
    },
    "intel_dbab7b01963396b5": {
        "topic": "AI_LABOR",
        "current_judgment_ko": (
            "미국에서는 AI 도입이 실제로 늘어나고 있다는 근거가 있고, 특정 업무(생성형 AI를 활용한 "
            "고객지원)에서는 생산성 향상도 관측됩니다. 다만 AI 노출로 인한 고용 효과는 미국 22~25세 "
            "초기 경력층에 한정해 엇갈린 근거를 보이며, 경제 전체 수준의 대규모 일자리 대체를 뒷받침하는 "
            "근거는 약화된 상태입니다. 핀란드 등 다른 국가의 전수 자료에서는 뚜렷한 고용 영향이 나타나지 "
            "않아, 미국의 특정 집단 결과를 세계 노동시장 전체로 일반화할 수는 없습니다."
        ),
        "what_we_know_ko": [
            "미국 기업과 근로자의 AI 도입은 실제로 증가하고 있다는 근거가 있습니다(부분 지지, HL1).",
            "생성형 AI를 활용한 고객지원 업무에서는 생산성 효과가 관측됩니다(NBER 연구, 해당 업무에 "
            "한정, HL3).",
            "미국 22~25세 초기 경력층에서는 AI 노출과 관련된 고용 효과가 일부 관측되지만, 근거가 "
            "엇갈립니다(Stanford SIEPR, HL2 CONTESTED).",
        ],
        "what_we_dont_know_ko": [
            "AI 노출이 경제 전체 수준 또는 전체 연령대 고용에 미치는 영향은 아직 분리해 확인하기 "
            "어렵습니다.",
            "한국의 10년 전망치(KDI)는 예측일 뿐이며, 미국·핀란드의 실제 관측 자료와 합산되지 "
            "않습니다.",
        ],
        "counterevidence_ko": [
            "AI가 경제 전체 차원에서 대규모 일자리 대체를 일으키고 있다는 주장은 이번 라운드에서 "
            "근거가 약화되었습니다(HL4, WEAKENED).",
            "핀란드의 전체 임금근로자 대상 연구(챗GPT 등장 후 2년)에서는 뚜렷한 고용 영향이 나타나지 "
            "않았습니다(ETLA).",
            "미국 BLS 집계 자료에서도 전체 수준에서는 뚜렷한 변화가 확인되지 않았습니다.",
        ],
        "watch_next_ko": [
            "초기 경력층 고용 효과가 다른 연령대·국가로 확산되는지",
            "생산성 효과가 고객지원 외 다른 업무로 확대되는지",
            "한국 등 전망 지표가 실제 관측 자료로 전환되는지",
        ],
        "source_basis": [
            "hyp_b365b95148a3a372",  # HL1 PARTIALLY_SUPPORTED
            "hyp_c4b0429622eb6dd7",  # HL3 PARTIALLY_SUPPORTED
            "hyp_b3a8bfef91a47a45",  # HL2 CONTESTED
            "hyp_8691a1cb2d7c0d45",  # HL4 WEAKENED
            "claim_fe878b52922b46a4",  # NBER customer-support productivity
            "claim_8fd5da8f27c9fc2b",  # Stanford SIEPR early-career
            "claim_8e305d0c30d23514",  # ETLA/Finland null result
        ],
    },
}


def get_reader_summary(intelligence_id):
    """Looks up a report's Reader Summary by intelligence_id (report['intelligence_id']). Returns
    None if no hand-authored summary exists for this report -- callers must fall back to the
    existing auto-derived lede/index-card behavior rather than inventing one."""
    return READER_SUMMARIES.get(intelligence_id)
