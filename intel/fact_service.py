# FACT: "이 기사가 무슨 일을 보도했는가"의 최소 단위. 이번 Pilot에서 지키는 원칙(운영자 지시, 2번):
#   ORIGINAL SOURCE → DOCUMENT → FACT 여야 하고, GEMINI QUICK BRIEF(mx.b)를 최종 근거로 쓰면 안 된다.
# 그래서 이 서비스는 절대 SOURCE_VERIFIED를 만들지 않는다(원문 전체를 확보·대조하지 않았으므로).
# mx.b에서 만든 건 반드시 status=SUMMARY_DERIVED, derived_from="mx.b", confidence 낮게, 검증된 사실로 취급 안 함.
# 발행사 RSS 소개글(추출 요약)에서 만든 건 derived_from="summary"(Gemini보다는 원문에 가깝지만
# 그래도 전체 원문 대조가 없으므로 SOURCE_VERIFIED는 아님).
import hashlib

FACT_STATUS = ("SOURCE_VERIFIED", "SUMMARY_DERIVED", "INSUFFICIENT_SOURCE", "NOT_EXTRACTED")
CLAIM_TYPES = ("MEASURED", "RESEARCH_FINDING", "GOVERNMENT_REPORTED", "COMPANY_REPORTED", "COURT_FINDING",
               "ESTIMATED", "FORECAST", "ALLEGATION", "MEDIA_REPORTED")


def _text_hash(text):
    return hashlib.sha1((text or "").encode("utf-8", "ignore")).hexdigest()[:16]


def _claim_type_guess(category):
    return {"papers": "RESEARCH_FINDING", "policy": "GOVERNMENT_REPORTED"}.get(category, "MEDIA_REPORTED")


def make_fact_candidate(item, document_id, actor, now_iso):
    """규칙 기반 Fact Candidate 하나(또는 근거 부족이면 None에 가까운 상태 레코드)를 만든다.
    fact_id는 document_id에 종속(:f1)이라 나중에 같은 문서에서 fact가 여러 개 나와도 안정적이다."""
    evidence_text = item.get("summary") or ""
    derived_from, status, confidence = None, "NOT_EXTRACTED", 0.0
    if evidence_text and evidence_text != (item.get("mx") or {}).get("b"):
        derived_from, status, confidence = "summary", "SUMMARY_DERIVED", 0.35   # 발행사 RSS 추출 요약: mx.b보다 원문에 가까움
    elif (item.get("mx") or {}).get("b"):
        evidence_text = item["mx"]["b"]
        derived_from, status, confidence = "mx.b", "SUMMARY_DERIVED", 0.2       # Gemini 요약: 최종 근거 아님, 낮은 확신도만
    else:
        status = "INSUFFICIENT_SOURCE" if not item.get("title") else "NOT_EXTRACTED"

    fact = {
        "fact_id": f"{document_id}:f1",
        "document_id": document_id,
        "subject": actor or item.get("source") or None,
        "predicate": "REPORTED" if status != "NOT_EXTRACTED" else None,
        "object": (item.get("title") or "")[:160] or None,
        "value": None, "unit": None,
        "claim_type": _claim_type_guess(item.get("category")) if status != "NOT_EXTRACTED" else None,
        "confidence": confidence,
        "status": status,
        "derived_from": derived_from,
        "evidence_text_hash": _text_hash(evidence_text) if evidence_text else None,
        "created_at": now_iso, "updated_at": now_iso,
    }
    return fact
