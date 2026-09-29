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


def _frontmatter(note):
    lines = ["---",
             f"id: {note['note_id']}",
             f"type: {note['note_type']}",
             f"status: {note['status']}",
             f"created_at: {note['created_at']}",
             f"updated_at: {note['updated_at']}"]
    if note.get("concepts"):
        lines.append("concepts:")
        lines += [f"  - {c}" for c in note["concepts"]]
    lines.append("---")
    return "\n".join(lines)


def note_to_markdown(note):
    body = [_frontmatter(note), "", f"# {note.get('title') or note['note_id']}", "",
            note.get("statement") or ""]
    if note.get("supporting_evidence_ids"):
        body += ["", "## Supporting Evidence"]
        body += [f"- [[{eid}]]" for eid in note["supporting_evidence_ids"]]
    if note.get("counter_evidence_ids"):
        body += ["", "## Counter Evidence"]
        body += [f"- [[{eid}]]" for eid in note["counter_evidence_ids"]]
    body += ["", "## Provenance"]
    for key in ("document_ids", "fact_ids", "event_ids", "change_ids"):
        for oid in note.get(key, []):
            body.append(f"- {key[:-1]}: {oid}")
    for url in note.get("source_urls", []):
        body.append(f"- source_url: {url}")
    return "\n".join(body) + "\n"


def export_vault(notes_by_id, vault_dir):
    """notes_by_id -> vault_dir 아래 타입별 폴더에 Markdown 파일. 파일명은 note_id로
    고정한다(섹션 70: stable filename). 기존 사람이 vault_dir에 직접 만든 파일은 건드리지
    않는다 — note_id 파일명과 겹치지 않는 한 삭제/덮어쓰기 없음."""
    vault_dir = Path(vault_dir)
    written = []
    for nid, note in notes_by_id.items():
        folder = _FOLDER_BY_TYPE.get(note["note_type"], "90_ARCHIVE")
        out_dir = vault_dir / folder
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{nid}.md"
        out_path.write_text(note_to_markdown(note), encoding="utf-8")
        written.append(str(out_path.relative_to(vault_dir)))
    return written
