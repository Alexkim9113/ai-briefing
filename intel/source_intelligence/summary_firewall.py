# SOURCE INTELLIGENCE CORRECTION v1.0 — Phase H(spec 섹션 32/33/63). QUICK_BRIEF(mx.b)/
# METAXIS_POINT(mx.p)는 PRESENTATION/EDITORIAL 객체이지 canonical factual evidence가
# 아니다. 이 모듈은 그 경계를 코드로 강제하는 단일 지점이다 - 여러 곳에 흩어진 "mx.b
# 쓰지 마라" 규칙을 한 곳에 모아, 앞으로 새 코드가 실수로 mx.b를 canonical evidence
# 입력으로 쓰는 것을 구조적으로 막는다.
GENERATED_SUMMARY_FIELDS = ("mx.b", "mx.p", "quick_brief", "metaxis_point",
                            "generated_interpretation", "generated_topic_explanation")

# 이 claim_status들은 이미 evidence_pipeline이 "canonical factual evidence"로 보는
# 최소 기준이다(SOURCE_LOCATED 이상) - 재정의하지 않고 그대로 가져와 쓴다.
_CANONICAL_MINIMUM = ("SOURCE_LOCATED", "SOURCE_VERIFIED")


def is_generated_summary_source(derived_from):
    return derived_from in GENERATED_SUMMARY_FIELDS


def gemini_eligible_text(raw_item):
    """섹션 33: Level 3 Gemini 의미 추출 입력은 반드시 source-grounded text여야 한다 -
    METAXIS 자신이 만든 mx.b를 Gemini에게 "원문"인 것처럼 다시 넣지 않는다(2차 생성물
    재입력 루프 차단). raw_item.get("summary")는 발행사 RSS가 제공한 소개글(원문에서
    유래) - 이것만 허용한다. 없으면 None(호출자는 INSUFFICIENT_SOURCE로 처리해야 한다)."""
    if not raw_item:
        return None
    summary = (raw_item.get("summary") or "").strip()
    return summary or None


def assert_not_summary_derived(candidate_claim_status, derived_from, target_use):
    """canonical factual evidence로 쓰려는 지점(target_use는 로그/에러메시지용 설명)에서
    mx.b/mx.p 기원 값이 SOURCE_LOCATED 이상으로 승격되어 들어오면 즉시 막는다 - 조용히
    통과시키지 않는다."""
    if is_generated_summary_source(derived_from) and candidate_claim_status in _CANONICAL_MINIMUM:
        raise ValueError(
            f"SUMMARY_FIREWALL: {target_use}에 generated summary({derived_from}) 기원 값이 "
            f"{candidate_claim_status}로 들어오려 했다 - 차단."
        )
