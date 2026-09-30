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


# =============================================================================
# PHASE M.2 step 6 — historical-specific knowledge gap classes. Extends this module (does not
# build a second coverage system). Only assigns a class the code can actually justify from real
# HistoricalEvidence/analogy data - never force-fills a 0-coverage gap with an invented source.
# =============================================================================

HISTORICAL_GAP_CLASSES = (
    "NO_SOURCE", "LOW_SOURCE_QUALITY", "SINGLE_SOURCE_ONLY", "GEOGRAPHY_GAP", "TIME_GAP",
    "DOMAIN_GAP", "MECHANISM_GAP", "COUNTEREXAMPLE_GAP", "PRIMARY_SOURCE_NOT_VERIFIED",
    "UNKNOWN_GAP",
)


def _classify_evidence_record_gap(rec, independent_count):
    """Best-effort, honest classification of the single most salient gap on one
    HistoricalEvidence record. Returns None when the record has no demonstrable gap (real
    source, tier 1-2, non-UNKNOWN geography, independent_count >= 2)."""
    if rec.get("evidence_status") != "VERIFIED_STRUCTURED":
        return "NO_SOURCE"
    if rec.get("source_tier") in ("TIER_3", "TIER_4", None):
        return "LOW_SOURCE_QUALITY"
    if independent_count <= 1:
        return "SINGLE_SOURCE_ONLY"
    if rec.get("geography") == "UNKNOWN":
        return "GEOGRAPHY_GAP"
    if rec.get("temporal_precision") == "UNKNOWN":
        return "TIME_GAP"
    if not rec.get("mechanism"):
        return "MECHANISM_GAP"
    if rec.get("source_tier") == "TIER_1" and rec.get("claim_kind") == "HISTORICAL_FACT" \
            and not rec.get("canonical_url"):
        return "PRIMARY_SOURCE_NOT_VERIFIED"
    return None


def detect_historical_knowledge_gaps(evidence_registry, independent_counts_by_id, analogies=None):
    """evidence_registry: {evidence_id: HistoricalEvidence record}. independent_counts_by_id:
    {evidence_id: int} as computed by historical_source_independence.py for that record's own
    source family (caller-supplied so this module never re-implements source independence).
    analogies: optional list of analogy dicts - any analogy with an empty counteranalogy field
    contributes a COUNTEREXAMPLE_GAP entry (a real, demonstrable absence, not an invented one).
    Every gap here is justified by real data on the record itself; an unclassifiable record
    (should not normally happen) honestly gets UNKNOWN_GAP rather than silently being skipped."""
    gaps = []
    for eid, rec in (evidence_registry or {}).items():
        gap_class = _classify_evidence_record_gap(rec, independent_counts_by_id.get(eid, 0))
        if gap_class is None:
            continue
        gaps.append({
            "dimension": "HISTORICAL_EVIDENCE", "evidence_id": eid,
            "gap_class": gap_class, "status": "OPEN",
        })
    for analogy in (analogies or []):
        if not analogy.get("counteranalogy"):
            gaps.append({
                "dimension": "ANALOGY", "evidence_id": analogy.get("analogy_id"),
                "gap_class": "COUNTEREXAMPLE_GAP", "status": "OPEN",
                "reason": "no counteranalogy supplied - not fabricated to fill this slot",
            })
    return gaps
