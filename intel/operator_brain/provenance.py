# STAGE 7 PHASE B — Provenance reconstruction. 섹션 18: ANSWER CLAIM -> FACT -> DOCUMENT ->
# SOURCE. 여기서는 NOTE(FACT/EVENT)에 붙어있는 document_ids를 실제 documents.json까지
# 역추적한다 - 존재하지 않으면 조용히 숨기지 않고 missing으로 표시한다(섹션 26의
# "실패를 숨기지 않는다" 원칙과 동일 정신).
def reconstruct(note, documents_by_id):
    trail = []
    for did in note.get("document_ids", []):
        doc = documents_by_id.get(did)
        if doc is None:
            trail.append({"document_id": did, "found": False})
        else:
            trail.append({
                "document_id": did, "found": True,
                "title": doc.get("title"),
                "source_url": doc.get("source_url"),
                "canonical_url": doc.get("canonical_url"),
                "published_at": doc.get("published_at"),
            })
    return trail
