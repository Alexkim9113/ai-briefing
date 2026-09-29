# EVENT/CHANGE 연결(운영자 지시 섹션 26). 기존 production_events.json/changes.json은 절대
# 수정하지 않는다 — 별도 산출물(evidence_lineage.json 일부)로 verified_claim_ids/
# evidence_record_ids 링크만 만든다. Event 병합 기준은 전혀 건드리지 않는다(정확도 유지).
def link_claims_to_events(claims, events):
    """document_id가 Event의 document_ids/related_document_ids에 포함되면 링크.
    Event 생성 로직 자체는 전혀 바꾸지 않는다 — 사후 주석(annotation)일 뿐이다."""
    doc_to_events = {}
    for eid, ev in (events or {}).items():
        for did in ev.get("document_ids", ev.get("related_document_ids", [])):
            doc_to_events.setdefault(did, []).append(eid)

    links = {}
    for c in claims:
        eids = doc_to_events.get(c["document_id"], [])
        for eid in eids:
            links.setdefault(eid, {"verified_claim_ids": [], "evidence_record_ids": []})
            if c["claim_id"] not in links[eid]["verified_claim_ids"] and c["claim_status"] in (
                    "SOURCE_LOCATED", "SOURCE_VERIFIED"):
                links[eid]["verified_claim_ids"].append(c["claim_id"])
    return links


def link_evidence_records_to_changes(evidence_records, changes, events):
    """document_id -> event_id(들) -> (해당 event가 change.supporting_event_ids에 있으면) change_id
    경로로 evidence_record_ids를 Change에 연결한다. Change 생성 로직은 전혀 바꾸지 않는다."""
    doc_to_events = {}
    for eid, ev in (events or {}).items():
        for did in ev.get("document_ids", []):
            doc_to_events.setdefault(did, []).append(eid)

    event_to_changes = {}
    for cid, ch in (changes or {}).items():
        for eid in ch.get("supporting_event_ids", []):
            event_to_changes.setdefault(eid, []).append(cid)

    links = {}
    for rec in evidence_records:
        for eid in doc_to_events.get(rec["document_id"], []):
            for cid in event_to_changes.get(eid, []):
                links.setdefault(cid, {"evidence_record_ids": []})
                if rec["evidence_record_id"] not in links[cid]["evidence_record_ids"]:
                    links[cid]["evidence_record_ids"].append(rec["evidence_record_id"])
    return links
