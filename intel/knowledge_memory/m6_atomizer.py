# M.6 -- Obsidian-compatible atomic knowledge export for the new Intelligence layer. Separate
# from exporter.py's existing CONCEPT/FACT/.../RESEARCH_IDEA note vault (notes.json) -- that
# system stays untouched. This module atomizes the M.6 sidecars (claims.json,
# statistical_evidence.json, intelligence_objects.json) into the M.6 atom-type vocabulary Te
# specified. Read-only export, never the other direction (Obsidian -> DB).
import hashlib
from pathlib import Path

ATOM_TYPES = (
    "PAPER", "CLAIM", "EVIDENCE", "EVENT", "STATISTIC", "METHOD", "RESULT", "LIMITATION",
    "COUNTEREVIDENCE", "HYPOTHESIS", "POLICY_IMPLICATION", "HISTORICAL_ANALOGY",
)


def _atom_id(atom_type, title):
    return f"atom_{atom_type.lower()}_{hashlib.sha256(title.encode()).hexdigest()[:12]}"


def new_atom(atom_type, title, content, source_ids, related_atoms=None, visibility="PUBLIC",
             rights_status="LINK_ONLY", updated_at=None):
    assert atom_type in ATOM_TYPES, f"unknown atom type: {atom_type!r}"
    return {
        "atom_id": _atom_id(atom_type, title), "type": atom_type, "title": title,
        "content": content, "source_ids": list(source_ids), "related_atoms": related_atoms or [],
        "provenance": list(source_ids), "visibility": visibility, "rights_status": rights_status,
        "updated_at": updated_at,
    }


def atom_to_markdown(atom):
    lines = ["---", f"id: {atom['atom_id']}", f"type: {atom['type']}",
             f"visibility: {atom['visibility']}", f"rights_status: {atom['rights_status']}"]
    if atom.get("updated_at"):
        lines.append(f"updated_at: {atom['updated_at']}")
    lines.append("---")
    lines += ["", f"# {atom['title']}", "", atom["content"] or ""]
    if atom["related_atoms"]:
        lines += ["", "## Related"]
        lines += [f"- [[{a}]]" for a in atom["related_atoms"]]
    if atom["source_ids"]:
        lines += ["", "## Sources"]
        lines += [f"- {s}" for s in atom["source_ids"]]
    return "\n".join(lines) + "\n"


def atomize_statistical_series(series_record):
    title = f"{series_record['indicator_id']} ({series_record['geography']})"
    content = (f"Trend: {series_record['trend_status']}. "
               f"{len(series_record['observations'])} observations, "
               f"source: {series_record['source_url']}")
    return new_atom("STATISTIC", title, content, [series_record["source_url"]])


def atomize_claim(claim):
    return new_atom("CLAIM", claim["claim_text"][:80], claim["claim_text"], [claim.get("provenance") or ""])


def atomize_intelligence_object(obj):
    atom = new_atom("RESULT", obj["topic"] + ": " + obj["question"], obj["current_state"],
                     obj.get("provenance", []))
    atom["related_atoms"] = (
        [f"claim_{c}" if not c.startswith("claim_") else c for c in obj.get("key_claims", [])] +
        [s for s in obj.get("statistics", [])]
    )
    return atom


def write_vault_atoms(atoms, vault_root):
    """Writes each atom under vault_root/<TYPE>/<atom_id>.md. Does not delete pre-existing files
    for atom types outside this call's scope -- only ever adds/overwrites the atoms it is given."""
    vault_root = Path(vault_root)
    written = []
    for atom in atoms:
        folder = vault_root / atom["type"]
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{atom['atom_id']}.md"
        path.write_text(atom_to_markdown(atom), encoding="utf-8")
        written.append(str(path))
    return written
