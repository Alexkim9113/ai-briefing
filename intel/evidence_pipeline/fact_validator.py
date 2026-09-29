# FACT VALIDATION(운영자 지시 섹션 8). 매우 보수적: CLAIM CONTENT(주장 내용)와
# CLAIM EXISTENCE(그런 주장이 있었다는 사실)를 철저히 구분한다. 이 Pipeline은 원문 전체를
# 절대 확보하지 않으므로(제목+발행사 요약만), CONTENT_VERIFIED는 만들지 않는다 — 오직
# EXISTENCE_VERIFIED만(20개 금지 2,3,16,18번 방지). SOURCE_VERIFIED claim_status는 이
# Pipeline이 절대 만들지 않으므로(claim_extractor.py 참고), Fact 승격도 SOURCE_LOCATED
# 이상만 대상으로 한다.
FACT_KIND = ("EXISTENCE_VERIFIED",)  # CONTENT_VERIFIED는 이번 Phase에서 만들지 않음(운영자 지시)

# 어떤 claim_type + claim_status 조합만 Fact로 승격 가능한지(섹션 8 허용 목록에 대응).
_PROMOTABLE_STATUS = ("SOURCE_LOCATED",)
_PROMOTABLE_TYPES = ("COMPANY_REPORTED", "GOVERNMENT_REPORTED", "LEGISLATIVE_TEXT",
                     "COURT_FINDING", "RESEARCH_FINDING", "REGULATORY_TEXT")


def validate_claim(claim):
    """Fact로 승격 가능하면 (True, statement) 반환, 아니면 (False, reason)."""
    if claim.get("extraction_method") == "LEVEL3_GEMINI_CANDIDATE":
        return False, "LLM(Gemini Candidate) 추출 — LLM은 Fact Authority가 아니므로 승격 절대 금지(운영자 지시 섹션 1)"
    if claim["claim_status"] not in _PROMOTABLE_STATUS:
        return False, f"claim_status={claim['claim_status']} — 원문 소재만 확인, 승격 불가"
    if claim["claim_type"] not in _PROMOTABLE_TYPES:
        return False, f"claim_type={claim['claim_type']} — 측정/추정/보도 주장은 독립 검증 없이 승격 안 함"
    predicate = claim.get("predicate") or ""
    if "PROPOSAL" in predicate or "UNKNOWN_STAGE" in predicate:
        return False, "제안/미확정 단계 — 제정된 법·확정 정책이 아니므로 승격 안 함(섹션 43)"

    if claim["claim_type"] == "COMPANY_REPORTED":
        statement = f"{claim.get('claiming_organization') or claim.get('subject') or '해당 주체'}가 다음을 발표했다는 사실: {claim.get('object')}"
    elif claim["claim_type"] in ("GOVERNMENT_REPORTED", "LEGISLATIVE_TEXT", "REGULATORY_TEXT"):
        statement = f"공식 소스에서 다음 정책/법령 문서의 존재·상태가 확인됨: {claim.get('object')}"
    elif claim["claim_type"] == "COURT_FINDING":
        statement = f"공식 소스에서 다음 판결의 존재가 확인됨: {claim.get('object')}"
    elif claim["claim_type"] == "RESEARCH_FINDING":
        statement = f"식별자로 다음 논문의 존재가 확인됨(연구 결과 내용은 미검증): {claim.get('object')}"
    else:
        statement = f"존재가 확인된 보고: {claim.get('object')}"
    return True, statement


def build_fact(claim, now_iso):
    ok, statement_or_reason = validate_claim(claim)
    if not ok:
        return None
    return {
        "fact_id": f"{claim['claim_id']}:fact",
        "claim_id": claim["claim_id"], "document_id": claim["document_id"],
        "fact_kind": "EXISTENCE_VERIFIED",
        "statement": statement_or_reason,
        "based_on_claim_status": claim["claim_status"],
        "based_on_claim_type": claim["claim_type"],
        "created_at": now_iso, "updated_at": now_iso,
    }
