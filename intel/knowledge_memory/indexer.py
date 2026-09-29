# STAGE 6 — SUBSTEP K: Retrieval Index(섹션 44). Stage 7(Ask METAXIS, 이번 범위 밖)이
# 나중에 쓸 수 있는 최소 검색 인덱스만 만든다 — 답변 Agent는 만들지 않는다(섹션 45).
def build_index(notes_by_id):
    index = []
    for nid, note in notes_by_id.items():
        if note.get("status") == "REJECTED":
            continue  # 섹션 68: rejected가 active insight처럼 노출되면 안 된다
        index.append({
            "note_id": nid,
            "note_type": note.get("note_type"),
            "title": note.get("title"),
            "concepts": note.get("concepts", []),
            "entities": note.get("entities", []),
            "topics": note.get("topics", []),
            "domains": note.get("domains", []),
            "status": note.get("status"),
            "updated_at": note.get("updated_at"),
        })
    index.sort(key=lambda r: r["note_id"])
    return index
