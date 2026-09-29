# HUMAN REVIEW(운영자 지시 섹션 25). 모든 Evidence가 검토 대상은 아니다 — 우선순위별로
# 큐를 만든다. 여기서 만드는 review_status는 5D 등 상위 Layer의 override_status(AUTO_CANDIDATE/
# HUMAN_CONFIRMED/HUMAN_REJECTED)와는 다른, Evidence Pipeline 자체의 검토 워크플로다.
from schema import FIVE_D_TARGET_TYPES

_HIGH_TYPES = set(FIVE_D_TARGET_TYPES) | {"COURT_FINDING", "LEGISLATIVE_TEXT", "GOVERNMENT_REPORTED"}
_HIGH_DRIVER_RELATIONS = {"ENABLES", "CONSTRAINS", "ACCELERATES", "SLOWS", "POTENTIAL_CAUSE"}


def classify_priority_for_evidence_record(rec):
    if rec.get("interpretation_method") == "GEMINI_CANDIDATE":
        return "HIGH"  # LLM이 만든 후보는 항상 사람 검토 우선순위 최고(운영자 지시: LLM은 Fact Authority 아님)
    if rec.get("support_type") == "CONTRADICTORY" or rec.get("contradicts_ids"):
        return "HIGH"
    if rec.get("evidence_type") in _HIGH_TYPES:
        if rec.get("evidence_type") == "DRIVER" and rec.get("relation") not in _HIGH_DRIVER_RELATIONS:
            return "MEDIUM"
        return "HIGH"
    if rec.get("evidence_type") == "DEPENDENCY" or rec.get("evidence_type") == "VALUE_SHIFT":
        return "MEDIUM"
    if len(rec.get("domains") or []) >= 2:
        return "MEDIUM"
    return "LOW"


def classify_priority_for_claim(claim):
    if claim.get("extraction_method") == "LEVEL3_GEMINI_CANDIDATE":
        return "HIGH"
    if claim.get("claim_type") in ("COURT_FINDING", "LEGISLATIVE_TEXT", "GOVERNMENT_REPORTED"):
        return "HIGH"
    if claim.get("claim_type") in ("RESEARCH_FINDING", "COMPANY_REPORTED"):
        return "MEDIUM"
    return "LOW"  # MEASURED, MEDIA_REPORTED 등 명시적 메타데이터성 — 기본 낮은 우선순위


def build_review_queue(claims, evidence_records, now_iso):
    """review_status=PENDING만 담는다 — human_review.py의 override 적용은 pipeline.py가
    overrides.py를 통해 별도로 수행(여기서는 순수 우선순위 산정만)."""
    queue = []
    for c in claims:
        queue.append({
            "target_type": "claim", "target_id": c["claim_id"], "document_id": c["document_id"],
            "priority": classify_priority_for_claim(c), "review_status": "PENDING",
            "queued_at": now_iso,
        })
    for r in evidence_records:
        queue.append({
            "target_type": "evidence_record", "target_id": r["evidence_record_id"], "document_id": r["document_id"],
            "priority": classify_priority_for_evidence_record(r), "review_status": "PENDING",
            "queued_at": now_iso,
        })
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    queue.sort(key=lambda q: (order[q["priority"]], q["target_id"]))
    return queue
