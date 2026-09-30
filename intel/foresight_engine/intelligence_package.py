# STAGE 7 PHASE M — Intelligence Package assembly (Te spec section 44-45). Deterministic,
# structured (non-prose) assembly of everything the pipeline actually knows about a topic,
# pulled from real files on disk. No LLM. An empty section is reported as an empty list/0
# count, never omitted or backfilled - "honest 0/gap is a valid result" (Te's own words).
#
# This module reads each layer's own output JSON directly (plain json.load, no schema.py
# import) precisely BECAUSE several layers each ship their own schema.py that collide by
# module name - see intel/private_api/loader.py's comment for the exact same constraint this
# avoids by never importing those modules at all.
import json
from pathlib import Path

from coverage import build_coverage_matrix, detect_knowledge_gaps
from cross_domain import find_cross_domain_connections
from historical_analogy import audit_historical_evidence

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
INTEL = ROOT / "intel"

DOCUMENTS_PATH = INTEL / "documents.json"
NOTES_PATH = INTEL / "knowledge_memory" / "notes.json"

_LAYER_FILES = {
    "signals": INTEL / "signal_layer" / "signals.json",
    "patterns": INTEL / "pattern_layer" / "patterns.json",
    "structural_changes": INTEL / "structural_change_layer" / "structural_changes.json",
    "structural_analyses": INTEL / "structural_analysis_layer" / "structural_analyses.json",
    "contradictions": INTEL / "epistemic_layer" / "contradictions.json",
    "view_revisions": INTEL / "epistemic_layer" / "view_revisions.json",
    "scenarios": INTEL / "futures_layer" / "scenarios.json",
    "policy_questions": INTEL / "policy_research_layer" / "policy_questions.json",
}


def _load_json(path):
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _matches(text_fields, query_lower):
    for field in text_fields:
        if field and query_lower in str(field).lower():
            return True
    return False


def _matching_documents(query, documents):
    q = query.lower()
    out = []
    for doc_id, doc in documents.items():
        if _matches([doc.get("title"), doc.get("category"), doc.get("field")], q):
            out.append(doc_id)
    return out


def _matching_notes(query, notes):
    q = query.lower()
    out = []
    for note_id, note in notes.items():
        haystack = [note.get("statement")] + note.get("entities", []) + note.get("concepts", [])
        if _matches(haystack, q):
            out.append(note_id)
    return out


def _matching_layer_records(query, records):
    """Generic best-effort match over a layer's own JSON: looks at common name-ish fields plus
    any entities list. Layers are currently empty in the real corpus, so this returns []
    honestly for all of them - it is exercised for real once those layers produce output."""
    q = query.lower()
    out = []
    for rec_id, rec in records.items():
        if not isinstance(rec, dict):
            continue
        haystack = [rec.get("name"), rec.get("title"), rec.get("statement"),
                    rec.get("change_name")] + rec.get("entities", [])
        if _matches(haystack, q):
            out.append(rec_id)
    return out


def assemble_intelligence_package(topic, documents=None, notes=None):
    """The single Phase-M deliverable Te calls out as most important (section 45): given a
    topic/query string, pulls together everything the real pipeline currently holds about it
    into one structured dict. Every count below is real, not simulated."""
    documents = documents if documents is not None else _load_json(DOCUMENTS_PATH)
    notes = notes if notes is not None else _load_json(NOTES_PATH)

    matching_document_ids = _matching_documents(topic, documents)
    matching_note_ids = _matching_notes(topic, notes)

    layer_matches = {}
    for layer_name, path in _LAYER_FILES.items():
        records = _load_json(path)
        layer_matches[layer_name] = _matching_layer_records(topic, records)

    historical_audit = audit_historical_evidence(documents)
    connections = [c for c in find_cross_domain_connections(notes)
                   if topic.lower() in [e.lower() for e in c["shared_entities"]]]
    coverage = build_coverage_matrix(documents, notes)
    gaps = detect_knowledge_gaps(documents, notes)

    return {
        "topic": topic,
        "documents": {"count": len(matching_document_ids), "document_ids": matching_document_ids},
        "notes": {"count": len(matching_note_ids), "note_ids": matching_note_ids},
        "layers": {name: {"count": len(ids), "ids": ids} for name, ids in layer_matches.items()},
        "cross_domain_connections": connections,
        "historical_analogy_readiness": historical_audit,
        "coverage_summary": {
            "documents_total": coverage["documents_total"],
            "notes_total": coverage["notes_total"],
        },
        "knowledge_gaps_relevant": [g for g in gaps
                                    if g["key"] == "ALL"
                                    or topic.lower() in str(g["key"]).lower()],
        "evidence_sufficiency": (
            "NO_EVIDENCE" if not matching_document_ids and not matching_note_ids
            else "DOCUMENTS_ONLY" if matching_document_ids and not matching_note_ids
            else "NOTES_BUILT"
        ),
        "generated_by": "CODE_DETERMINISTIC",
    }
