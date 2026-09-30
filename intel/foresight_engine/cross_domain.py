# STAGE 7 PHASE M — Cross-Domain Connection (Te spec section 7, 23, 60). Deterministic linker:
# only connects two domains where real shared evidence already exists (a shared entity that
# appears in notes tagged with different `domains` values). Never invents causality - relation
# type defaults to the weakest honest label, ASSOCIATED_WITH, unless the caller explicitly
# supplies a stronger one from CROSS_DOMAIN_RELATION_TYPES.
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from foresight_schema import new_cross_domain_connection_shell, HISTORY_DOMAINS

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
NOTES_PATH = ROOT / "intel" / "knowledge_memory" / "notes.json"


def _load_notes(notes=None):
    if notes is not None:
        return notes
    if not NOTES_PATH.exists():
        return {}
    return json.loads(NOTES_PATH.read_text(encoding="utf-8"))


def _connection_id(domain_a, domain_b, entity):
    key = "|".join(sorted([domain_a, domain_b]) + [entity])
    return "xdc_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def find_cross_domain_connections(notes=None):
    """For each entity, find every (domain, note_id, document_ids) it appears under. Any
    entity that shows up under 2+ distinct domains yields one CANDIDATE connection per domain
    pair, evidenced by the actual notes/documents that produced it. Zero real overlap ->
    zero connections - never padded."""
    notes = _load_notes(notes)
    entity_domain_notes = defaultdict(lambda: defaultdict(list))
    for note_id, note in notes.items():
        domains = note.get("domains") or []
        entities = note.get("entities") or []
        for domain in domains:
            for entity in entities:
                entity_domain_notes[entity][domain].append(note_id)

    connections = []
    for entity, domain_map in entity_domain_notes.items():
        domains = sorted(domain_map.keys())
        if len(domains) < 2:
            continue
        for i in range(len(domains)):
            for j in range(i + 1, len(domains)):
                domain_a, domain_b = domains[i], domains[j]
                note_ids = sorted(set(domain_map[domain_a] + domain_map[domain_b]))
                doc_ids = sorted({doc_id for nid in note_ids
                                  for doc_id in notes.get(nid, {}).get("document_ids", [])})
                connections.append(new_cross_domain_connection_shell(
                    _connection_id(domain_a, domain_b, entity), domain_a, domain_b,
                    "ASSOCIATED_WITH", shared_entities=[entity],
                    evidence_note_ids=note_ids, evidence_document_ids=doc_ids,
                ))
    return connections


# =============================================================================
# PHASE M.2 step 5 — historical cross-domain linking. Reuses this module's own relation
# vocabulary (CROSS_DOMAIN_RELATION_TYPES, never CAUSES) and connection shell rather than
# building a second linker. Links a HISTORY_OF_* domain to a present-day domain ONLY when a
# real HistoricalEvidence record's own `current_domain_link` field ties it there - never a
# keyword-coincidence guess.
# =============================================================================


def find_historical_cross_domain_connections(evidence_registry, relation_type="ASSOCIATED_WITH"):
    """For each HistoricalEvidence record that explicitly names a current_domain_link, emits
    one CANDIDATE connection between its history_domain and that current domain, evidenced by
    the evidence record itself. A record with current_domain_link=None yields no connection -
    never padded, never guessed from event_or_process text."""
    connections = []
    for eid, rec in (evidence_registry or {}).items():
        history_domain = rec.get("history_domain")
        current_domain = rec.get("current_domain_link")
        if not current_domain or history_domain not in HISTORY_DOMAINS:
            continue
        connections.append(new_cross_domain_connection_shell(
            _connection_id(history_domain, current_domain, eid), history_domain, current_domain,
            relation_type, shared_entities=[rec.get("event_or_process") or eid],
            evidence_note_ids=[], evidence_document_ids=[],
        ))
        connections[-1]["evidence_historical_ids"] = [eid]
    return connections
