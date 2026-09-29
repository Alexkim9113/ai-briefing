# SOURCE INTELLIGENCE CORRECTION v1.0 (Te 승인, 2026-09-29) — Stage 1-3(Collection/
# Quality/Evidence Layer) 내부 보강. 새 Stage가 아니다(spec 섹션 2). 기존
# evidence_pipeline/schema.py의 CLAIM_STATUS·CLAIM_TYPES·EVIDENCE_SOURCE_HIERARCHY는
# 그대로 재사용한다(spec 섹션 34: "기존 어휘가 다르면 기존 canonical vocabulary를
# 재사용하라") - 여기서 다시 정의하지 않는다.
#
# 여기서만 새로 필요한 것: CONTENT STATUS(섹션 17) - "원문을 얼마나 확보했는가"라는,
# 기존 어디에도 없던 차원.
CONTENT_STATUS_VALUES = (
    "STRUCTURED_PRIMARY_DATA",  # arXiv/공식 API 등 구조화된 1차 데이터 자체
    "FULL_TEXT",                # 원문 본문 확보
    "PARTIAL_TEXT",             # 본문 일부(유료 장벽 앞부분 등)
    "ABSTRACT_ONLY",            # 논문 초록만
    "LEAD_ONLY",                # 기사 첫 문단만
    "SNIPPET_ONLY",             # RSS 소개글 수준(현재 METAXIS 기본값)
    "TITLE_ONLY",               # 제목만
    "FETCH_FAILED",             # 시도했으나 실패
    "BLOCKED",                  # robots/접근 제한으로 시도하지 않음
    "PAYWALLED",                # 유료 장벽 확인
    "UNKNOWN",                  # 판정 불가 - 추측 금지
)

# 섹션 18 EVIDENCE CEILING BY CONTENT STATUS: content_status가 factual extraction의
# 강도를 어디까지 허용하는지. "PRIMARY != TRUE, FULL_TEXT != TRUE" - 이건 신뢰도가
# 아니라 "얼마나 강하게 주장해도 되는가"의 상한선일 뿐이다. evidence_pipeline의
# CLAIM_STATUS 값 중 이 상한을 넘는 것은 허용하지 않는다(claim_status 자체를 여기서
# 대체하지 않고, 상한 검사만 추가한다).
_CLAIM_STATUS_ORDER = ("NOT_VERIFIED", "INSUFFICIENT_SOURCE", "SUMMARY_DERIVED",
                       "SECONDARY_ONLY", "PRIMARY_UNREAD", "SOURCE_LOCATED", "SOURCE_VERIFIED")
_CLAIM_STATUS_INDEX = {name: i for i, name in enumerate(_CLAIM_STATUS_ORDER)}

CONTENT_STATUS_CLAIM_CEILING = {
    "STRUCTURED_PRIMARY_DATA": "SOURCE_LOCATED",  # 구조화 데이터 자체 존재는 확인되나
                                                    # 원문 전체 대조 없인 SOURCE_VERIFIED 금지
    "FULL_TEXT": "SOURCE_VERIFIED",
    "PARTIAL_TEXT": "PRIMARY_UNREAD",
    "ABSTRACT_ONLY": "PRIMARY_UNREAD",
    "LEAD_ONLY": "SECONDARY_ONLY",
    "SNIPPET_ONLY": "SECONDARY_ONLY",
    "TITLE_ONLY": "INSUFFICIENT_SOURCE",
    "FETCH_FAILED": "INSUFFICIENT_SOURCE",
    "BLOCKED": "INSUFFICIENT_SOURCE",
    "PAYWALLED": "INSUFFICIENT_SOURCE",
    "UNKNOWN": "INSUFFICIENT_SOURCE",
}


def max_allowed_claim_status(content_status):
    """content_status가 없는 값이면(모르는 값) 가장 보수적으로 취급한다 - 관대해지지 않는다."""
    return CONTENT_STATUS_CLAIM_CEILING.get(content_status, "INSUFFICIENT_SOURCE")


def is_claim_status_within_content_ceiling(claim_status, content_status):
    idx = _CLAIM_STATUS_INDEX.get(claim_status)
    ceiling_idx = _CLAIM_STATUS_INDEX.get(max_allowed_claim_status(content_status))
    if idx is None or ceiling_idx is None:
        return False
    return idx <= ceiling_idx


def enforce_content_ceiling(claim_status, content_status):
    """실제로 낮춘다(플래그만 남기지 않는다) - evidence_sufficiency의 claim_ceiling
    enforcement와 동일한 원칙."""
    if is_claim_status_within_content_ceiling(claim_status, content_status):
        return claim_status, False
    return max_allowed_claim_status(content_status), True
