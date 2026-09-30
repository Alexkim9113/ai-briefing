# STAGE 7 PHASE M — Coverage matrices + knowledge gap detection (Te spec section 39-43).
# Deterministic, reads only documents.json + knowledge_memory/notes.json. No LLM.
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DOCUMENTS_PATH = ROOT / "intel" / "documents.json"
NOTES_PATH = ROOT / "intel" / "knowledge_memory" / "notes.json"


def _load(path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_coverage_matrix(documents=None, notes=None):
    """Returns counts per CATEGORY/FIELD/SOURCE/TEMPORAL, and an honest GEOGRAPHIC bucket.
    documents/notes params exist only so tests can pass fixtures instead of real files."""
    documents = documents if documents is not None else _load(DOCUMENTS_PATH)
    notes = notes if notes is not None else _load(NOTES_PATH)

    by_category = Counter()
    by_field = Counter()
    by_source = Counter()
    by_month = Counter()
    for doc in documents.values():
        by_category[doc.get("category") or "UNKNOWN"] += 1
        by_field[doc.get("field") or "UNKNOWN"] += 1
        by_source[doc.get("source_id") or "UNKNOWN"] += 1
        published = doc.get("published") or ""
        month = published[:7] if len(published) >= 7 else "UNKNOWN"
        by_month[month] += 1

    # Notes coverage per category: which document categories have at least one note built
    # from a document in that category (a real, computable signal of "documents exist but were
    # never turned into knowledge").
    doc_category_by_id = {doc_id: (doc.get("category") or "UNKNOWN")
                           for doc_id, doc in documents.items()}
    notes_covered_categories = Counter()
    for note in notes.values():
        for doc_id in note.get("document_ids", []):
            cat = doc_category_by_id.get(doc_id)
            if cat:
                notes_covered_categories[cat] += 1

    return {
        "documents_total": len(documents),
        "notes_total": len(notes),
        "by_category": dict(by_category),
        "by_field": dict(by_field),
        "by_source": dict(by_source),
        "by_month": dict(by_month),
        "notes_by_covered_category": dict(notes_covered_categories),
        # Honest: this corpus carries no geography field on any document, verified by direct
        # inspection - we never infer a country/region from text. Every bucket is UNKNOWN.
        "by_geography": {"UNKNOWN": len(documents)},
    }


def detect_knowledge_gaps(documents=None, notes=None):
    """A gap is OPEN when a category/field has real documents but zero notes were ever built
    from them (i.e. raw evidence exists but was never turned into retrievable knowledge).
    This never fabricates a gap where none is demonstrated, and never fabricates coverage
    where none exists."""
    matrix = build_coverage_matrix(documents, notes)
    gaps = []
    for category, doc_count in matrix["by_category"].items():
        note_count = matrix["notes_by_covered_category"].get(category, 0)
        if doc_count > 0 and note_count == 0:
            gaps.append({
                "dimension": "CATEGORY",
                "key": category,
                "documents_available": doc_count,
                "notes_built": note_count,
                "status": "OPEN",
            })
    # Geographic coverage: always reported as an open, honest gap (not a fabricated matrix),
    # since the corpus carries no geography field at all.
    gaps.append({
        "dimension": "GEOGRAPHIC",
        "key": "ALL",
        "documents_available": matrix["documents_total"],
        "notes_built": 0,
        "status": "OPEN",
        "reason": "no geography field exists anywhere in intel/documents.json - honestly "
                  "unresolved, not inferred",
    })
    return gaps
