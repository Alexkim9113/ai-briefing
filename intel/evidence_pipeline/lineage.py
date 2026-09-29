# LINEAGE(운영자 지시 섹션 36, 44). ORIGINAL SOURCE -> DOCUMENT -> CLAIM -> EVIDENCE RECORD ->
# EVENT -> CHANGE -> ... 를 실제로 추적 가능한 만큼만 채운다. 상위 Layer가 비어 있으면
# 거기서 정직하게 멈춘다("chain이 중간에서 멈추는 것은 정상 동작" — 운영자 서문).
def build_lineage_for_claim(claim, document, evidence_records_by_claim, doc_to_events, event_to_changes):
    chain = {
        "source_url": document.get("canonical_url"), "document_id": claim["document_id"],
        "claim_id": claim["claim_id"], "claim_status": claim["claim_status"],
        "evidence_record_ids": [r["evidence_record_id"] for r in evidence_records_by_claim.get(claim["claim_id"], [])],
    }
    event_ids = doc_to_events.get(claim["document_id"], [])
    chain["event_ids"] = event_ids
    change_ids = sorted({cid for eid in event_ids for cid in event_to_changes.get(eid, [])})
    chain["change_ids"] = change_ids
    if not chain["evidence_record_ids"]:
        chain["stopped_at"] = "CLAIM"
        chain["stop_reason"] = "이 Claim에서 명시적 Interpretation 트리거(제약/의존/통제/가치/관계 언어)가 발견되지 않음"
    elif not event_ids:
        chain["stopped_at"] = "EVIDENCE_RECORD"
        chain["stop_reason"] = "이 문서가 어떤 Production Event에도 속하지 않음(단독 문서, 이벤트 미형성)"
    elif not change_ids:
        chain["stopped_at"] = "EVENT"
        chain["stop_reason"] = "이 Event를 지지 근거로 쓰는 활성 Change 없음(반려되었거나 아직 Change 미형성)"
    else:
        chain["stopped_at"] = "CHANGE_OR_ABOVE"
        chain["stop_reason"] = None
    return chain
