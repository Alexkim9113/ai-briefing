# STAGE 6 — SUBSTEP K/PRODUCTIONIZATION 섹션 27-32, 56-58: Retrieval Index. Stage
# 7(Ask METAXIS, 범위 밖)이 나중에 쓸 최소 검색 인덱스만 만든다 — LLM Answer Generation은
# 하지 않는다(섹션 28).
def _row(nid, note):
    return {
        "note_id": nid,
        "note_type": note.get("note_type"),
        "title": note.get("title"),
        "statement": note.get("statement"),
        "status": note.get("status"),
        "concepts": note.get("concepts", []),
        "entities": note.get("entities", []),
        "topics": note.get("topics", []),
        "domains": note.get("domains", []),
        "first_seen": note.get("first_seen"),
        "last_seen": note.get("last_seen"),
        "jurisdiction": note.get("jurisdiction"),
        "human_review_status": note.get("human_review_status"),
        "updated_at": note.get("updated_at"),
    }


def build_index(notes_by_id, include_rejected=False):
    """섹션 31: 기본 검색은 REJECTED를 제외한다. include_rejected=True는 audit/history
    모드 전용(섹션 31: "audit/history 모드에서는 검색 가능해야 한다")."""
    index = []
    for nid, note in notes_by_id.items():
        if not include_rejected and note.get("status") == "REJECTED":
            continue
        index.append(_row(nid, note))
    index.sort(key=lambda r: r["note_id"])
    return index


def filter_index(index, note_type=None, status=None, concept=None, entity=None,
                  topic=None, domain=None, jurisdiction=None, updated_after=None, updated_before=None):
    """섹션 57: type/status/concept/entity/topic/domain/jurisdiction/date range 필터.
    UI는 만들지 않는다 — 순수 함수만 제공한다."""
    out = index
    if note_type is not None:
        out = [r for r in out if r["note_type"] == note_type]
    if status is not None:
        out = [r for r in out if r["status"] == status]
    if concept is not None:
        out = [r for r in out if concept in (r.get("concepts") or [])]
    if entity is not None:
        out = [r for r in out if entity in (r.get("entities") or [])]
    if topic is not None:
        out = [r for r in out if topic in (r.get("topics") or [])]
    if domain is not None:
        out = [r for r in out if domain in (r.get("domains") or [])]
    if jurisdiction is not None:
        out = [r for r in out if r.get("jurisdiction") == jurisdiction]
    if updated_after is not None:
        out = [r for r in out if (r.get("updated_at") or "") >= updated_after]
    if updated_before is not None:
        out = [r for r in out if (r.get("updated_at") or "") <= updated_before]
    return out
