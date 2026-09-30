# PHASE M.2 — HistoricalEvidence storage. Deterministic, zero LLM calls, no live fetch
# required (this module never calls a network fetcher itself - if a future caller needs to
# live-verify a source page it must reuse intel/source_intelligence/scripts/fetch_pilot.py's
# hardened real_fetcher rather than building a second one, per the Phase M.2 spec's security
# rule; this pilot round cites well-established public facts with a real source reference
# instead, which the spec explicitly allows).
#
# Publication Firewall: only structured metadata + a short factual `notes` string is ever
# stored - never full source article/book text. build_historical_evidence_registry_export()
# below is the one function any public/export path may call, and it strips even `notes` down
# to a length-capped summary as a defense-in-depth measure against accidental over-storage.
import json
from pathlib import Path

from foresight_schema import new_historical_evidence_shell

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
HISTORICAL_EVIDENCE_PATH = HERE / "historical_evidence.json"

MAX_NOTES_CHARS = 600  # short factual note only - never a full article/book excerpt


def load_historical_evidence(path=None):
    path = path or HISTORICAL_EVIDENCE_PATH
    if not Path(path).exists():
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_historical_evidence(registry, path=None):
    path = path or HISTORICAL_EVIDENCE_PATH
    Path(path).write_text(json.dumps(registry, indent=2, ensure_ascii=False, sort_keys=True),
                           encoding="utf-8")


def create_historical_evidence(historical_evidence_id, **kwargs):
    """Thin wrapper over new_historical_evidence_shell() that additionally enforces the
    Publication Firewall length cap on `notes` at creation time (never store full source
    text) - this is a structural guard, not a stylistic default."""
    notes = kwargs.get("notes")
    if notes and len(notes) > MAX_NOTES_CHARS:
        raise ValueError(
            f"historical evidence notes exceed {MAX_NOTES_CHARS} chars "
            f"({len(notes)}) - only a short factual note is allowed, never full source text"
        )
    return new_historical_evidence_shell(historical_evidence_id, **kwargs)


def register_historical_evidence(record, registry=None, path=None):
    registry = registry if registry is not None else load_historical_evidence(path)
    registry[record["historical_evidence_id"]] = record
    save_historical_evidence(registry, path)
    return registry


PUBLIC_EXPORT_FIELDS = (
    "historical_evidence_id", "event_or_process", "history_domain", "current_domain_link",
    "subdomain", "geography", "start_period", "end_period", "temporal_precision",
    "actors", "institutions", "technology", "mechanism", "documented_outcome", "claim_kind",
    "source_type", "source_tier", "source_title", "source_organization", "publication_date",
    "original_date", "retrieved_at", "canonical_url", "evidence_status", "confidence",
)


def build_historical_evidence_registry_export(registry=None, path=None):
    """The ONLY function a public/export path may call for historical evidence. Emits
    citation-grade structured metadata only - never a body/full_text field, never the raw
    `source_id` (an internal identifier, not something to publish), and `notes` is capped and
    labeled as a summary. Same Publication Firewall principle the rest of METAXIS already
    applies (see intel/publication/ gate) - this module does not duplicate that gate, it just
    never emits anything that would need it."""
    registry = registry if registry is not None else load_historical_evidence(path)
    out = {}
    for eid, rec in registry.items():
        exported = {k: rec.get(k) for k in PUBLIC_EXPORT_FIELDS}
        notes = rec.get("notes")
        exported["notes_summary"] = (notes[:MAX_NOTES_CHARS] if notes else None)
        out[eid] = exported
    return out


def trace_evidence_to_source(evidence_id, registry=None, path=None):
    """evidence_id -> source_id -> canonical citation, walked end to end (Te spec step 9/AA).
    Returns None if the evidence_id is unknown or genuinely has no source (honest, never
    fabricated)."""
    registry = registry if registry is not None else load_historical_evidence(path)
    rec = registry.get(evidence_id)
    if not rec:
        return None
    if rec.get("evidence_status") != "VERIFIED_STRUCTURED":
        return None
    return {
        "evidence_id": evidence_id,
        "source_id": rec.get("source_id"),
        "canonical_url": rec.get("canonical_url"),
        "source_title": rec.get("source_title"),
        "source_organization": rec.get("source_organization"),
        "source_tier": rec.get("source_tier"),
    }
