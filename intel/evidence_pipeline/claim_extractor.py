# CLAIM EXTRACTION (운영자 지시 섹션 7, 22). "원문이 실제로 뭐라고 썼는가"만 다룬다 —
# 구조적 의미 해석(Interpretation)은 여기서 절대 하지 않는다(interpretation.py가 분리 담당).
#
# LEVEL 1(구조화 데이터: 식별자·공식 도메인) → LEVEL 2(규칙 패턴) 순서로만 채운다. LEVEL 3
# (Gemini Candidate)은 이 모듈이 "규칙으로 부족하다"고 판정한 문서만 claim_extractor 밖에서
# (pipeline.py가) 호출 여부를 결정한다 — extractor 자신은 LLM을 호출하지 않는다.
import re

from schema import new_claim_shell, CLAIM_TYPES

_PCT = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*(%|percent|퍼센트|배)")
_COMPANY_VERB = re.compile(
    r"\b(announced?|claims?|says?|reported?)\b|발표했|밝혔|주장했|출시했다|공개했다", re.I)
_ENACTED_KO = re.compile(r"시행|제정|의결|통과|확정")
_PROPOSAL_KO = re.compile(r"발의|추진|검토|제안|계획 중|입법 예고")
_COURT_KO = re.compile(r"판결|선고|기각|각하|승소|패소")
# "bill"은 영어 인명(Bill Gates 등)과 충돌이 너무 흔해 영문 트리거에서 제외한다(정확도 우선) —
# 한글 "법안/법률안"만 쓰고, 영문 입법 문서는 PRIMARY_LEGISLATIVE 도메인 판정에 맡긴다.
_BILL_KO = re.compile(r"법안|법률안")

# 회사/기관으로 보이는 제목 선두 토큰(대문자 시작 영문 또는 한글 고유명사 패턴) — 매우 보수적:
# 못 찾으면 None(추측하지 않음). claiming_organization은 "누가 이 주장을 했다고 보도됐는가"만
# 기록하고, 그 주장 내용의 진위는 절대 판단하지 않는다(섹션 8: CLAIM EXISTENCE != CLAIM CONTENT).
_LEADING_ORG = re.compile(r"^([A-Z][A-Za-z0-9&.\-]{1,30}(?:\s[A-Z][A-Za-z0-9&.\-]{1,30}){0,2})\b")
_LEADING_ORG_KO = re.compile(r"^([가-힣]{2,6}(?:전자|반도체|그룹|증권|은행|바이오|모빌리티)?),?\s")


def _claiming_org(title):
    m = _LEADING_ORG_KO.match(title or "")
    if m:
        return m.group(1)
    m = _LEADING_ORG.match(title or "")
    if m:
        return m.group(1)
    return None


def _evidence_text(raw_item):
    """fact_service.py와 동일 원칙: 발행사 RSS 요약(summary)이 mx.b(Gemini 요약)보다 원문에
    가깝다. 원문 전체는 절대 저장하지 않는다 — text_hash만 남긴다(20개 금지 13번 관련)."""
    if not raw_item:
        return None, None
    summary = raw_item.get("summary") or ""
    mxb = (raw_item.get("mx") or {}).get("b") or ""
    if summary and summary != mxb:
        return summary, "summary"
    if mxb:
        return mxb, "mx.b"
    return None, None


def _level1_claims(document, source_resolution):
    """LEVEL 1: 식별자·공식 도메인만으로 확정할 수 있는 Claim. 원문 대조 없음 — SOURCE_LOCATED
    까지만(운영자 지시: SOURCE_VERIFIED는 원문 전체 대조 없이 절대 부여 안 함)."""
    out = []
    hierarchy = source_resolution["source_hierarchy"]
    self_identifier = source_resolution.get("self_identifier")
    if self_identifier and hierarchy == "PRIMARY_RESEARCH":
        ident_kind, ident_id = self_identifier
        out.append({
            "claim_type": "RESEARCH_FINDING",
            "subject": ident_id, "predicate": "IDENTIFIER_RESOLVED", "object": document.get("title"),
            "claim_status": "SOURCE_LOCATED",
            "extraction_method": "LEVEL1_STRUCTURED",
            "confidence": "HIGH",
            "note": f"{ident_kind} 식별자가 실제로 존재함을 코드로 확인 — 논문 내용(결론)은 검증하지 않음",
        })
    return out


def _level2_claims(document, raw_item, source_resolution):
    """LEVEL 2: 알려진 패턴(측정치·기업 발표·정부/법원/입법 문서)만 규칙으로 추출.
    패턴에 안 맞으면 무리해서 만들지 않는다(정확도 우선)."""
    out = []
    title = document.get("title") or ""
    text, derived_from = _evidence_text(raw_item)
    dtype = document.get("document_type")
    hierarchy = source_resolution["source_hierarchy"]
    domain = source_resolution["domain"]

    m = _PCT.search(text or "") or _PCT.search(title)
    if m:
        out.append({
            "claim_type": "MEASURED",
            "subject": _claiming_org(title), "predicate": "REPORTS_VALUE", "object": None,
            "value": m.group(1), "unit": m.group(2),
            "claim_status": "SECONDARY_ONLY" if hierarchy.startswith("SECONDARY") else "SOURCE_LOCATED",
            "extraction_method": "LEVEL2_RULE", "confidence": "MEDIUM",
        })

    if dtype == "COURT" or (domain and hierarchy == "PRIMARY_COURT") or _COURT_KO.search(title):
        out.append({
            "claim_type": "COURT_FINDING",
            "subject": _claiming_org(title), "predicate": "COURT_DECIDED", "object": title,
            "claim_status": "SOURCE_LOCATED" if hierarchy == "PRIMARY_COURT" else "SECONDARY_ONLY",
            "extraction_method": "LEVEL2_RULE", "confidence": "MEDIUM",
        })

    if hierarchy == "PRIMARY_LEGISLATIVE" or _BILL_KO.search(title):
        # 섹션 43: 발의/추진 중인 법안(PROPOSAL) != 제정된 법(ENACTED) — 절대 혼동 금지.
        status = "ENACTED" if _ENACTED_KO.search(title) else (
            "PROPOSAL" if _PROPOSAL_KO.search(title) else "UNKNOWN_STAGE")
        out.append({
            "claim_type": "LEGISLATIVE_TEXT",
            "subject": _claiming_org(title), "predicate": f"LEGISLATIVE_STATUS_{status}", "object": title,
            "claim_status": "SOURCE_LOCATED" if hierarchy == "PRIMARY_LEGISLATIVE" else "SECONDARY_ONLY",
            "extraction_method": "LEVEL2_RULE", "confidence": "MEDIUM" if status != "UNKNOWN_STAGE" else "LOW",
        })
    elif dtype == "POLICY":
        status = "ENACTED" if _ENACTED_KO.search(title) else (
            "PROPOSAL" if _PROPOSAL_KO.search(title) else "UNKNOWN_STAGE")
        out.append({
            "claim_type": "GOVERNMENT_REPORTED",
            "subject": _claiming_org(title), "predicate": f"POLICY_STATUS_{status}", "object": title,
            "claim_status": "SOURCE_LOCATED" if hierarchy in ("PRIMARY_OFFICIAL", "PRIMARY_REGULATORY") else "SECONDARY_ONLY",
            "extraction_method": "LEVEL2_RULE", "confidence": "MEDIUM" if status != "UNKNOWN_STAGE" else "LOW",
        })

    if hierarchy == "PRIMARY_COMPANY" or _COMPANY_VERB.search(title) or _COMPANY_VERB.search(text or ""):
        org = _claiming_org(title)
        # 섹션 8 핵심: "회사가 X라고 발표했다"는 사실(claim existence)이지, X가 참이라는 뜻이 아니다.
        out.append({
            "claim_type": "COMPANY_REPORTED",
            "subject": org, "predicate": "COMPANY_ANNOUNCED", "object": title,
            "claiming_organization": org,
            "claim_status": "SOURCE_LOCATED" if hierarchy == "PRIMARY_COMPANY" else "SECONDARY_ONLY",
            "extraction_method": "LEVEL2_RULE", "confidence": "MEDIUM" if org else "LOW",
        })

    if not out:
        # 어떤 규칙에도 안 걸리면 최소 MEDIA_REPORTED "존재" 레코드만(기존 fact_service와 동일 원칙) —
        # object 내용의 진위 판단은 전혀 하지 않는다.
        if text or title:
            out.append({
                "claim_type": "MEDIA_REPORTED",
                "subject": document.get("source_id"), "predicate": "REPORTED", "object": title,
                "claim_status": "SUMMARY_DERIVED" if derived_from == "summary" else (
                    "SECONDARY_ONLY" if derived_from == "mx.b" else "INSUFFICIENT_SOURCE"),
                "extraction_method": "LEVEL2_RULE",
                "confidence": "LOW",
            })
    for c in out:
        c.setdefault("derived_from", derived_from)
    return out


def needs_level3(document, level1, level2, raw_item):
    """LEVEL 3(Gemini Candidate) 후보 여부만 판정 — 실제 호출은 pipeline.py의 비용 규칙(섹션 23)이
    결정한다. '애매하고 가치있는 문서'만: 구조화/규칙 추출이 전혀 없었고(claim_type 다양성 0),
    본문 텍스트는 존재하는 경우."""
    text, _ = _evidence_text(raw_item)
    if level1:
        return False
    only_media_reported = all(c["claim_type"] == "MEDIA_REPORTED" for c in level2)
    return bool(text) and only_media_reported


def extract_claims(document, raw_item, source_resolution, now_iso):
    level1 = _level1_claims(document, source_resolution)
    level2 = _level2_claims(document, raw_item, source_resolution)
    claims = []
    for i, spec in enumerate(level1 + level2):
        cid = f"{document['document_id']}:c{i + 1}"
        shell = new_claim_shell(cid, document["document_id"], document.get("source_id"))
        spec = dict(spec)
        note = spec.pop("note", None)
        shell.update(spec)
        if spec.get("claim_type") not in CLAIM_TYPES:
            shell["claim_type"] = "OTHER"
        shell["reported_by"] = document.get("source_id")
        shell["evidence_locator"] = "title" if not raw_item else "title_or_summary"
        text, _ = _evidence_text(raw_item)
        shell["evidence_text_hash"] = None
        from common import text_hash
        shell["evidence_text_hash"] = text_hash(text or document.get("title"))
        shell["created_at"] = now_iso
        shell["updated_at"] = now_iso
        if note:
            shell["extraction_note"] = note
        claims.append(shell)
    flag_level3 = needs_level3(document, level1, level2, raw_item)
    return claims, flag_level3
