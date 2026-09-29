# PHASE 4B — Event Fact Pack 스켈레톤(운영자 지시 13, 14번). Claude가 글을 쓰지 않고,
# 데이터가 없으면 빈 배열로 둔다. LLM으로 빈칸을 상상해서 채우지 않는다.
def build_fact_pack(event_id, event_name, event_type, event_date, primary_document_id,
                     related_document_ids, key_entities, fact_records_by_document):
    """fact_records_by_document: {document_id: fact_service.make_fact_candidate() 결과}.
    SOURCE_VERIFIED만 verified_facts, 그 외(SUMMARY_DERIVED 등)는 reported_claims(운영자 14번)."""
    verified_facts, reported_claims = [], []
    for did in related_document_ids:
        fact = fact_records_by_document.get(did)
        if not fact:
            continue
        entry = {"document_id": did, "status": fact.get("status"), "claim_type": fact.get("claim_type")}
        if fact.get("status") == "SOURCE_VERIFIED":
            verified_facts.append(entry)
        else:
            reported_claims.append(entry)
    return {
        "event_id": event_id, "event_name": event_name, "event_type": event_type, "event_date": event_date,
        "verified_facts": verified_facts,       # 현재 SOURCE_VERIFIED가 거의 없으면 []가 정상(14번)
        "reported_claims": reported_claims,
        "key_entities": key_entities,
        "key_numbers": [],       # 이번 Phase는 숫자 추출 로직을 만들지 않음 — 빈 배열
        "primary_document": primary_document_id,
        "related_documents": related_document_ids,
        "primary_sources": [primary_document_id] if primary_document_id else [],
        "secondary_sources": [d for d in related_document_ids if d != primary_document_id],
        "related_research": [],
        "related_policy": [],
        "uncertainties": [],
        "contradictions": [],
    }
