# STAGE 6 — SUBSTEP L: Obsidian-ready Export(섹션 29-32, 70). Obsidian은 Source of Truth가
# 아니다 — 이 파일은 notes.json(DB)에서 Markdown을 "내보내기"만 한다. 반대 방향(Obsidian
# 파일을 읽어 DB를 바꾸는 것)은 이번 Foundation에서 절대 구현하지 않는다(섹션 71).
from pathlib import Path

_FOLDER_BY_TYPE = {
    "CONCEPT": "01_CONCEPTS", "FACT": "02_FACTS", "CLAIM": "03_CLAIMS",
    "EVENT": "04_EVENTS", "CHANGE": "05_CHANGES", "RELATION": "06_RELATIONS",
    "QUESTION": "07_QUESTIONS", "HYPOTHESIS": "08_HYPOTHESES", "INSIGHT": "09_INSIGHTS",
    "POLICY_IDEA": "10_POLICY_IDEAS", "RESEARCH_IDEA": "11_RESEARCH_IDEAS",
}


_TEMPORAL_FIELDS = ("first_seen", "last_seen", "valid_from", "valid_to", "observed_at",
                     "event_date", "evidence_date", "source_published_at", "temporal_scope",
                     "time_window_start", "time_window_end")
_SCOPE_FIELDS = ("geographic_scope", "jurisdiction", "population_scope", "industry_scope",
                 "institution_scope", "domain_scope", "measurement_scope")


def _frontmatter(note):
    lines = ["---",
             f"id: {note['note_id']}",
             f"type: {note['note_type']}",
             f"status: {note['status']}",
             f"version: {note.get('version', 1)}",
             f"human_review_status: {note.get('human_review_status') or 'NONE'}",
             f"created_at: {note['created_at']}",
             f"updated_at: {note['updated_at']}"]
    if note.get("concepts"):
        lines.append("concepts:")
        lines += [f"  - {c}" for c in note["concepts"]]
    for field in _TEMPORAL_FIELDS:
        if note.get(field):
            lines.append(f"{field}: {note[field]}")
    for field in _SCOPE_FIELDS:
        if note.get(field):
            lines.append(f"{field}: {note[field]}")
    if note.get("supersedes"):
        lines.append(f"supersedes: {note['supersedes']}")
    if note.get("superseded_by"):
        lines.append(f"superseded_by: {note['superseded_by']}")
    lines.append("---")
    return "\n".join(lines)


def note_to_markdown(note, related_notes=None):
    """related_notes: 이 note가 주체/객체인 실제 Stage 6 Relation에서 온 상대 note_id
    목록만 받는다(섹션 47: 같은 keyword를 공유한다고 링크하지 않는다 — 실제 relation만)."""
    body = [_frontmatter(note), "", f"# {note.get('title') or note['note_id']}", "",
            note.get("statement") or ""]
    if note.get("supporting_evidence_ids"):
        body += ["", "## Supporting Evidence"]
        body += [f"- [[{eid}]]" for eid in note["supporting_evidence_ids"]]
    if note.get("counter_evidence_ids"):
        body += ["", "## Counter Evidence"]
        body += [f"- [[{eid}]]" for eid in note["counter_evidence_ids"]]
    if note.get("version", 1) > 1 and note.get("history"):
        body += ["", "## Revision History"]
        for h in note["history"]:
            body.append(f"- v{h.get('version')}: {h.get('revision_reason') or h.get('changed_at')}")
    body += ["", "## Provenance"]
    for key in ("document_ids", "fact_ids", "event_ids", "change_ids"):
        for oid in note.get(key, []):
            body.append(f"- {key[:-1]}: {oid}")
    for url in note.get("source_urls", []):
        body.append(f"- source_url: {url}")
    if related_notes:
        body += ["", "## Related (Stage 6 Relations)"]
        for rel_type, other_id in related_notes:
            body.append(f"- {rel_type}: [[{other_id}]]")
    return "\n".join(body) + "\n"


def _related_by_note(relations_by_id):
    """섹션 47: 실제 relation edge에서만 [[link]]를 만든다 — 키워드/Concept 공유로는
    절대 링크하지 않는다. relations_by_id는 memory.upsert_relations()가 반환한 dict."""
    related = {}
    for rel in relations_by_id.values():
        if rel.get("status") == "REJECTED":
            continue
        subj, obj, rtype = rel["subject_id"], rel["object_id"], rel["relation_type"]
        related.setdefault(subj, []).append((rtype, obj))
        related.setdefault(obj, []).append((rtype, subj))
    return related


def export_vault(notes_by_id, vault_dir, relations_by_id=None):
    """notes_by_id -> vault_dir 아래 타입별 폴더에 Markdown 파일. 파일명은 note_id로
    고정한다(섹션 70: stable filename). 기존 사람이 vault_dir에 직접 만든 파일은 건드리지
    않는다 — note_id 파일명과 겹치지 않는 한 삭제/덮어쓰기 없음."""
    vault_dir = Path(vault_dir)
    related_by_note = _related_by_note(relations_by_id) if relations_by_id else {}
    written = []
    for nid, note in notes_by_id.items():
        folder = _FOLDER_BY_TYPE.get(note["note_type"], "90_ARCHIVE")
        out_dir = vault_dir / folder
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{nid}.md"
        out_path.write_text(note_to_markdown(note, related_by_note.get(nid)), encoding="utf-8")
        written.append(str(out_path.relative_to(vault_dir)))
    return written


def check_broken_internal_links(notes_by_id, vault_dir):
    """섹션 48: [[link]]가 가리키는 note_id가 실제로 export된 파일에 존재하는지 검사한다.
    반환값 0이 목표(섹션 48)."""
    import re
    vault_dir = Path(vault_dir)
    existing_ids = {p.stem for p in vault_dir.rglob("*.md")}
    broken = []
    for nid, note in notes_by_id.items():
        folder = _FOLDER_BY_TYPE.get(note["note_type"], "90_ARCHIVE")
        md_path = vault_dir / folder / f"{nid}.md"
        if not md_path.exists():
            continue
        text = md_path.read_text(encoding="utf-8")
        for m in re.findall(r"\[\[([^\]]+)\]\]", text):
            if m not in existing_ids:
                broken.append((nid, m))
    return broken
