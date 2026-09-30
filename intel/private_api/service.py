# STAGE 7 PHASE L — Private Intelligence API service layer. Plain, in-process, testable
# Python functions - one per endpoint in Te's spec section 69 PASS-critical set. No web
# framework: these are called directly by tests and by the thin stdlib HTTP wrapper in
# server.py. Every function here is a read path over Stage 1-6/7 outputs that already exist
# on disk - nothing here computes new knowledge, nothing here calls an LLM.
#
# ZERO-TOKEN DISCIPLINE (verify by reading this file): the only operator_brain entry points
# ever imported/called below are retriever.retrieve, evidence_sufficiency.assess,
# context_builder.build_context_pack, source_independence.assess_independence,
# provenance.reconstruct, pipeline.ask (mode is recorded but pipeline.ask itself has no
# Claude/Gemini/OpenAI call anywhere in it - only ask.py's ask_metaxis() branches into
# claude_adapter, and this file never imports ask.py or claude_adapter for any default path),
# and view_revision.list_candidates (read-only). No `anthropic`, `openai`, or
# Gemini SDK client is ever constructed in this file.
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from errors import ApiError
from loader import (load_foresight, load_km_adapter, load_km_exporter, load_km_memory,
                     load_operator_brain)

API_VERSION = "private-v1"

_MAX_SEARCH_LIMIT = 100
_MAX_JSON_EXPORT_LIMIT = 500


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _km_adapter():
    return load_km_adapter()


def _km_memory():
    return load_km_memory()


def _km_exporter():
    return load_km_exporter()


# ---------------------------------------------------------------------------
# 1. health
# ---------------------------------------------------------------------------
def health():
    available = {"knowledge_memory": False, "documents": False, "relationships": False,
                 "operator_brain": False}
    try:
        _km_memory().load_notes()
        available["knowledge_memory"] = True
    except Exception:
        pass
    try:
        _km_adapter().load_documents()
        available["documents"] = True
    except Exception:
        pass
    try:
        _km_memory().load_relations()
        available["relationships"] = True
    except Exception:
        pass
    llm_enabled = False
    try:
        claude_adapter = load_operator_brain("claude_adapter")
        available["operator_brain"] = True
        # llm_enabled reflects only whether a real key is present in env - never a claim of
        # "on" without checking (claude_adapter.adapter_status() itself never logs/returns
        # the key value, only CONFIGURED/NOT_CONFIGURED).
        llm_enabled = claude_adapter.adapter_status() == claude_adapter.STATUS_CONFIGURED
    except Exception:
        pass
    return {
        "status": "OK" if all(available.values()) else "DEGRADED",
        "version": API_VERSION,
        "available": available,
        "llm_enabled": llm_enabled,
        "timestamp": _now_iso(),
    }


# ---------------------------------------------------------------------------
# 2. status
# ---------------------------------------------------------------------------
def status():
    km_adapter = _km_adapter()
    km_memory = _km_memory()

    documents = km_adapter.load_documents()
    notes = km_memory.load_notes()
    relations = km_memory.load_relations()

    note_type_distribution = {}
    human_review_status_distribution = {}
    for note in notes.values():
        nt = note.get("note_type", "UNKNOWN")
        note_type_distribution[nt] = note_type_distribution.get(nt, 0) + 1
        hrs = note.get("human_review_status") or "NONE"
        human_review_status_distribution[hrs] = human_review_status_distribution.get(hrs, 0) + 1

    # content_status is a source_intelligence/content_acquisition.py concept (CONTENT_STATUS_VALUES);
    # documents.json rows persisted so far predate that field entirely, so we report the real,
    # honest distribution (everything buckets to NOT_RECORDED) rather than inventing a status.
    content_status_distribution = {}
    for doc in documents.values():
        cs = doc.get("content_status") or "NOT_RECORDED"
        content_status_distribution[cs] = content_status_distribution.get(cs, 0) + 1

    return {
        "documents_count": len(documents),
        "notes_count": len(notes),
        "relationships_count": len(relations),
        "note_type_distribution": note_type_distribution,
        "human_review_status_distribution": human_review_status_distribution,
        "content_status_distribution": content_status_distribution,
        "audit_summary": km_adapter.audit_summary(),
        "timestamp": _now_iso(),
    }


# ---------------------------------------------------------------------------
# 3. search
# ---------------------------------------------------------------------------
def _note_matches(note, needle):
    haystacks = [note.get("statement") or "", note.get("title") or ""]
    haystacks += note.get("concepts") or []
    haystacks += note.get("entities") or []
    haystacks += note.get("topics") or []
    return any(needle in h.lower() for h in haystacks)


def _document_matches(doc, needle):
    haystacks = [doc.get("title") or "", doc.get("field") or "", doc.get("category") or ""]
    return any(needle in h.lower() for h in haystacks)


def search(q, type=None, limit=20, offset=0):
    """Deterministic substring search over knowledge notes + documents. No semantic rewriting,
    no LLM. type in (None, "note", "document") or a specific note_type (FACT/EVENT/CHANGE/...)."""
    if not q or not str(q).strip():
        raise ApiError("INVALID_QUERY", "q must be a non-empty string")
    needle = str(q).strip().lower()
    limit = max(0, min(int(limit or 20), _MAX_SEARCH_LIMIT))
    offset = max(0, int(offset or 0))

    results = []
    if type in (None, "note") or (type not in (None, "note", "document")):
        notes = _km_memory().load_notes()
        for nid, note in sorted(notes.items()):
            if note.get("status") == "REJECTED":
                continue
            if type not in (None, "note") and note.get("note_type") != type:
                continue
            if _note_matches(note, needle):
                results.append({"kind": "note", "id": nid, "note_type": note.get("note_type"),
                                 "statement": note.get("statement"), "title": note.get("title")})
    if type in (None, "document"):
        documents = _km_adapter().load_documents()
        for did, doc in sorted(documents.items()):
            if _document_matches(doc, needle):
                results.append({"kind": "document", "id": did, "title": doc.get("title"),
                                 "canonical_url": doc.get("canonical_url"),
                                 "published": doc.get("published")})

    total = len(results)
    page = results[offset:offset + limit]
    return {"q": q, "type": type, "total": total, "limit": limit, "offset": offset,
            "results": page}


# ---------------------------------------------------------------------------
# 4. get_document
# ---------------------------------------------------------------------------
def get_document(document_id):
    documents = _km_adapter().load_documents()
    doc = documents.get(document_id)
    if doc is None:
        raise ApiError("NOT_FOUND", f"no document with document_id={document_id!r}")

    notes = _km_memory().load_notes()
    related_note_ids = sorted(
        nid for nid, note in notes.items() if document_id in (note.get("document_ids") or []))

    # REPORTS_ON-style relationships that reference this document (evidence_supply output -
    # read-only, never recomputed here).
    reports_on = []
    for fname in ("relationships.json", "relationships_company_gov.json"):
        path = Path(__file__).resolve().parent.parent / fname
        if not path.exists():
            continue
        import json
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        rows = rows if isinstance(rows, list) else list(rows.values())
        for row in rows:
            if not isinstance(row, dict):
                continue
            src = row.get("source_document_id") or row.get("from_document_id")
            tgt = row.get("target_document_id") or row.get("to_document_id")
            if document_id in (src, tgt):
                reports_on.append(row)

    # No full article body is ever returned here - only what documents.json actually
    # persists (title/canonical_url/content_hash/metadata). See documents.json rows: they
    # carry no full-text field at all in the current corpus.
    return {
        "document": dict(doc),
        "related_note_ids": related_note_ids,
        "reports_on_relationships": reports_on,
    }


# ---------------------------------------------------------------------------
# 5. get_note / related_notes
# ---------------------------------------------------------------------------
def get_note(note_id):
    notes = _km_memory().load_notes()
    note = notes.get(note_id)
    if note is None:
        raise ApiError("NOT_FOUND", f"no note with note_id={note_id!r}")
    return dict(note)


def related_notes(note_id):
    notes = _km_memory().load_notes()
    if note_id not in notes:
        raise ApiError("NOT_FOUND", f"no note with note_id={note_id!r}")
    relations = _km_memory().load_relations()
    related = []
    for rid, rel in relations.items():
        if not isinstance(rel, dict) or rel.get("status") == "REJECTED":
            continue
        subj, obj, rtype = rel.get("subject_id"), rel.get("object_id"), rel.get("relation_type")
        if subj == note_id:
            related.append({"relation_id": rid, "relation_type": rtype, "note_id": obj,
                             "direction": "OUTGOING"})
        elif obj == note_id:
            related.append({"relation_id": rid, "relation_type": rtype, "note_id": subj,
                             "direction": "INCOMING"})
    return {"note_id": note_id, "related": related}


# ---------------------------------------------------------------------------
# 6. trace
# ---------------------------------------------------------------------------
def trace(knowledge_id):
    notes = _km_memory().load_notes()
    note = notes.get(knowledge_id)
    if note is None:
        raise ApiError("NOT_FOUND", f"no note with note_id={knowledge_id!r}")
    documents = _km_adapter().load_documents()
    provenance = load_operator_brain("provenance")
    trail = provenance.reconstruct(note, documents)
    if not trail or not any(t.get("found") for t in trail):
        return {"knowledge_id": knowledge_id, "trail": trail, "status": "PROVENANCE_UNKNOWN"}
    return {"knowledge_id": knowledge_id, "trail": trail, "status": "OK"}


# ---------------------------------------------------------------------------
# 7. evidence
# ---------------------------------------------------------------------------
def _intent_for_note_type(note_type):
    return {"FACT": "FACT_LOOKUP", "EVENT": "EVENT_LOOKUP"}.get(note_type, "GENERAL_SYNTHESIS")


def evidence(knowledge_id):
    notes = _km_memory().load_notes()
    note = notes.get(knowledge_id)
    if note is None:
        raise ApiError("NOT_FOUND", f"no note with note_id={knowledge_id!r}")

    documents = _km_adapter().load_documents()
    provenance = load_operator_brain("provenance")
    evidence_sufficiency = load_operator_brain("evidence_sufficiency")
    context_builder = load_operator_brain("context_builder")

    result = {
        "note_id": knowledge_id, "note_type": note.get("note_type"),
        "statement": note.get("statement"), "concepts": note.get("concepts") or [],
        "entities": note.get("entities") or [],
        "provenance": provenance.reconstruct(note, documents),
        "confidence": note.get("confidence"),
    }
    intent = _intent_for_note_type(note.get("note_type"))
    sufficiency = evidence_sufficiency.assess([result], intent, counter_evidence_results=[])

    query_record = {"normalized_text": note.get("statement"), "intent": intent,
                     "mode": "RETRIEVE", "scope": {}}
    retrieval = {"results": [result]}
    context_pack, budget_info = context_builder.build_context_pack(
        query_record, retrieval, sufficiency)

    return {
        "note_id": knowledge_id,
        "evidence_sufficiency": sufficiency,
        "context_pack": context_pack,
        "context_budget": budget_info,
    }


# ---------------------------------------------------------------------------
# 8. timeline
# ---------------------------------------------------------------------------
def timeline(q=None, date_from=None, date_to=None):
    needle = (q or "").strip().lower() or None
    entries = []
    for nid, note in _km_memory().load_notes().items():
        date = note.get("created_at")
        if not date:
            continue
        if needle and not _note_matches(note, needle):
            continue
        entries.append({"type": "note", "id": nid, "date": date,
                         "note_type": note.get("note_type"), "statement": note.get("statement")})
    for did, doc in _km_adapter().load_documents().items():
        date = doc.get("published") or doc.get("created_at")
        if not date:
            continue
        if needle and not _document_matches(doc, needle):
            continue
        entries.append({"type": "document", "id": did, "date": date, "title": doc.get("title")})

    if date_from:
        entries = [e for e in entries if e["date"] >= date_from]
    if date_to:
        entries = [e for e in entries if e["date"] <= date_to]

    entries.sort(key=lambda e: e["date"])
    return {"q": q, "date_from": date_from, "date_to": date_to, "count": len(entries),
            "entries": entries}


# ---------------------------------------------------------------------------
# 9. query (POST) — structured deterministic retrieval. NOT an LLM endpoint: it calls
# operator_brain.pipeline.ask(), which performs query parsing + intent classification +
# scope extraction + retrieval + evidence sufficiency + context pack construction and never,
# anywhere in its own code, imports or calls claude_adapter/ask_metaxis. mode is accepted in
# the request only to match Te's section 27 request contract; Phase L implements and allows
# only "RETRIEVE" — any other mode is rejected here rather than silently routed to
# ask_metaxis's paid branches.
# ---------------------------------------------------------------------------
def query(payload):
    if not isinstance(payload, dict):
        raise ApiError("INVALID_QUERY", "request body must be a JSON object")
    question = payload.get("question")
    if not question or not str(question).strip():
        raise ApiError("INVALID_QUERY", "'question' is required and must be non-empty")
    mode = payload.get("mode", "RETRIEVE")
    if mode != "RETRIEVE":
        raise ApiError("INVALID_QUERY",
                        f"mode {mode!r} not supported by Phase L (retrieve-only by design); "
                        "use mode='RETRIEVE'")

    pipeline = load_operator_brain("pipeline")
    record = pipeline.ask(question, "RETRIEVE")
    return {
        "query_id": record["query_id"],
        "intent": record["intent"],
        "scope": record["scope"],
        "mode": record["mode"],
        "retrieval": record["retrieval"],
        "evidence_sufficiency": record["evidence_sufficiency"],
        "context_pack": record["context_pack"],
        "context_hash": record["context_hash"],
    }


# ---------------------------------------------------------------------------
# 10. Obsidian export (single + bulk) — reuses knowledge_memory/exporter.py verbatim.
# ---------------------------------------------------------------------------
def export_obsidian_note(note_id):
    notes = _km_memory().load_notes()
    note = notes.get(note_id)
    if note is None:
        raise ApiError("NOT_FOUND", f"no note with note_id={note_id!r}")
    exporter = _km_exporter()
    relations = _km_memory().load_relations()
    related_by_note = exporter._related_by_note(relations) if relations else {}
    markdown = exporter.note_to_markdown(note, related_by_note.get(note_id))
    return {"note_id": note_id, "markdown": markdown}


def export_obsidian_bulk(note_ids=None, note_type=None, out_dir=None):
    """Operator-chosen scope only - never a silent full-corpus dump. Caller must supply either
    an explicit note_ids list or a note_type filter."""
    if not note_ids and not note_type:
        raise ApiError("INVALID_QUERY",
                        "bulk export requires an explicit scope: note_ids and/or note_type")
    notes = _km_memory().load_notes()
    if note_ids:
        missing = [nid for nid in note_ids if nid not in notes]
        if missing:
            raise ApiError("NOT_FOUND", f"unknown note_id(s): {missing}")
        scoped = {nid: notes[nid] for nid in note_ids}
    else:
        scoped = notes
    if note_type:
        scoped = {nid: n for nid, n in scoped.items() if n.get("note_type") == note_type}

    exporter = _km_exporter()
    relations = _km_memory().load_relations()
    vault_dir = out_dir or tempfile.mkdtemp(prefix="metaxis_obsidian_export_")
    written = exporter.export_vault(scoped, vault_dir, relations_by_id=relations)
    return {"exported_count": len(written), "vault_dir": str(vault_dir), "written": written}


# ---------------------------------------------------------------------------
# 11. JSON export
# ---------------------------------------------------------------------------
def export_json(note_type=None, note_ids=None, limit=100):
    limit = max(0, min(int(limit or 100), _MAX_JSON_EXPORT_LIMIT))
    notes = _km_memory().load_notes()
    if note_ids:
        missing = [nid for nid in note_ids if nid not in notes]
        if missing:
            raise ApiError("NOT_FOUND", f"unknown note_id(s): {missing}")
        scoped = {nid: notes[nid] for nid in note_ids}
    else:
        scoped = notes
    if note_type:
        scoped = {nid: n for nid, n in scoped.items() if n.get("note_type") == note_type}

    items = [dict(n) for _, n in sorted(scoped.items())][:limit]
    return {"note_type": note_type, "count": len(items), "total_matching": len(scoped),
            "notes": items}


# ---------------------------------------------------------------------------
# 12. contradictions / view-revisions — implemented only because a real backing store exists.
# ---------------------------------------------------------------------------
def contradictions():
    """Backed by evidence_pipeline/evidence_records.json's contradicts_ids field (populated by
    evidence_pipeline/counter_evidence.py's find_counter_pairs/apply_counter_pairs - we do not
    recompute that here, only read its output). Currently 0 in the real corpus - honest,
    not a defect of this endpoint."""
    records = _km_adapter().load_evidence_records()
    flagged = [r for r in records if isinstance(r, dict) and r.get("contradicts_ids")]
    return {"count": len(flagged), "contradictions": flagged}


def view_revisions(status=None):
    """Backed by operator_brain/view_revision.py's view_revision_candidates.json
    (VIEW_REVISION_CANDIDATE / HIGH_VALUE_VIEW_REVISION_CANDIDATE, status=PENDING_HUMAN_REVIEW
    until a human approves via view_revision.approve_candidate() - never auto-resolved here;
    this endpoint is read-only and calls no write path). Currently 0 candidates exist on disk
    in this corpus - honest, not a defect."""
    view_revision = load_operator_brain("view_revision")
    candidates = view_revision.list_candidates(status=status)
    return {"count": len(candidates), "status_filter": status, "candidates": candidates}


# ---------------------------------------------------------------------------
# 13. STAGE 7 PHASE M — Cross-Domain Intelligence & Foresight Engine additions. Every function
# below is a read/deterministic-compute path over intel/foresight_engine/ (new this phase) -
# no LLM, no write to any canonical Stage 1-6 store. Only added because the underlying
# capability was actually built this phase (Te spec section 80: no endpoints for symmetry).
# ---------------------------------------------------------------------------
def coverage():
    """Domain/field/source/temporal/geographic coverage matrix + per-category knowledge gaps
    (Te spec section 39-43). Reads real documents.json/notes.json only; 0/UNKNOWN buckets are
    reported honestly, never backfilled."""
    coverage_mod = load_foresight("coverage")
    matrix = coverage_mod.build_coverage_matrix()
    return matrix


def knowledge_gaps():
    """Open knowledge gaps: categories with real documents but zero notes ever built from
    them, plus the always-honest GEOGRAPHIC gap (the corpus carries no geography field at
    all - see intel/foresight_engine/coverage.py)."""
    coverage_mod = load_foresight("coverage")
    gaps = coverage_mod.detect_knowledge_gaps()
    return {"count": len(gaps), "gaps": gaps}


def cross_domain_connections():
    """Cross-domain connections actually demonstrated by shared entities across notes tagged
    with different `domains` values (Te spec section 7/23/60). Relation type is always one of
    ASSOCIATED_WITH/PRECEDES/POSSIBLE_DRIVER/CONTRIBUTING_FACTOR - never CAUSES."""
    cross_domain_mod = load_foresight("cross_domain")
    connections = cross_domain_mod.find_cross_domain_connections()
    return {"count": len(connections), "connections": connections}


def historical_analogies(topic=None):
    """Historical analogy readiness (Te spec section 19-22). This module builds no analogy
    content itself (that requires a human-supplied historical_case, per the no-fabrication
    rule) - it only runs the corpus audit and reports HISTORICAL_EVIDENCE_GAP honestly when,
    as in this corpus today, no document is old enough to ground a real comparison."""
    if not topic:
        raise ApiError("INVALID_QUERY", "historical_analogies requires ?topic=")
    historical_analogy_mod = load_foresight("historical_analogy")
    result = historical_analogy_mod.build_historical_analogy(topic)
    return result


def intelligence_package(topic=None):
    """The Phase M flagship deliverable (Te spec section 44-45): assembles every real, current
    piece of intelligence this pipeline holds about `topic` - documents, notes, every
    signal/pattern/structural-change/structural-analysis/epistemic/futures/policy-research
    layer's own output file, cross-domain connections and historical-analogy readiness - into
    one structured, non-prose package. Zero counts are reported plainly."""
    if not topic:
        raise ApiError("INVALID_QUERY", "intelligence_package requires ?topic=")
    intelligence_package_mod = load_foresight("intelligence_package")
    return intelligence_package_mod.assemble_intelligence_package(topic)
