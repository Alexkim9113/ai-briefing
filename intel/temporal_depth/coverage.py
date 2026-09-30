# PHASE M.5A Part 2 — Priority 4: real, deterministic temporal-depth engine. Zero LLM.
#
# Reuses (does not reinvent):
#  - intel/foresight_engine/coverage.py's pattern of reading documents.json/notes.json directly
#    and returning plain dict metrics, no LLM, tests can inject fixtures.
#  - intel/change_layer/source_independence_gate.py's independent_evidence_count() for
#    independent_source_family_count, so "independent sources" always means the SAME thing here
#    as it does in the change layer (Priority 2/8 discipline: never invent a second
#    independence system, and never let raw document_count stand in for it).
#
# Priority 8 discipline (hard-enforced here): temporal_depth_status reflects CALENDAR SPAN ONLY
# (first_seen/last_seen/span_days of REAL dated documents/events for that entity). It is NOT a
# change-evidence verdict. A single old + single new document about an entity is never elevated
# past SHORT_WINDOW/MULTI_PERIOD by this module -- LONGITUDINAL additionally requires a real
# document/event count floor (>=1 events in >=2 distinct calendar quarters), never span alone.
# Whether that entity ALSO clears the change-layer gates (entity diversity, source independence,
# MIN_SUPPORTING_EVENTS) is a completely separate question this module does not answer.
import importlib.util
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DOCUMENTS_PATH = ROOT / "intel" / "documents.json"
EVENTS_PATH = ROOT / "intel" / "event_production" / "production_events.json"

NO_DATA = "NO_DATA"
POINT_IN_TIME = "POINT_IN_TIME"
SHORT_WINDOW = "SHORT_WINDOW"
MULTI_PERIOD = "MULTI_PERIOD"
LONGITUDINAL = "LONGITUDINAL"
UNKNOWN = "UNKNOWN"


def _load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _load_isolated(path, unique_name):
    key = f"_temporal_depth_isolated__{unique_name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_independence_gate():
    return _load_isolated(ROOT / "intel" / "change_layer" / "source_independence_gate.py",
                           "source_independence_gate")


def _parse_date(value):
    """Real published/event_date strings only -- never estimates or invents a date. Returns
    a date() or None. Handles 'YYYY-MM-DD' and full ISO timestamps with offsets."""
    if not value or not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _quarter(d):
    return (d.year, (d.month - 1) // 3 + 1)


def load_documents():
    documents = _load_json(DOCUMENTS_PATH, {})
    return documents if isinstance(documents, dict) else {}


def load_events():
    events = _load_json(EVENTS_PATH, {})
    return events if isinstance(events, dict) else {}


def corpus_temporal_summary(documents=None, events=None):
    """Corpus-wide real temporal metrics. No estimation: undated documents/events are counted,
    never dropped or backdated."""
    documents = documents if documents is not None else load_documents()
    events = events if events is not None else load_events()

    dated_docs = []
    undated = 0
    by_year = Counter()
    by_quarter = Counter()
    by_month = Counter()
    for doc in documents.values():
        d = _parse_date(doc.get("published"))
        if d is None:
            undated += 1
            continue
        dated_docs.append(d)
        by_year[d.year] += 1
        by_quarter[f"{d.year}-Q{_quarter(d)[1]}"] += 1
        by_month[d.isoformat()[:7]] += 1

    events_by_year = Counter()
    events_by_quarter = Counter()
    events_by_month = Counter()
    for ev in events.values():
        d = _parse_date(ev.get("event_date"))
        if d is None:
            continue
        events_by_year[d.year] += 1
        events_by_quarter[f"{d.year}-Q{_quarter(d)[1]}"] += 1
        events_by_month[d.isoformat()[:7]] += 1

    oldest = min(dated_docs) if dated_docs else None
    latest = max(dated_docs) if dated_docs else None
    span_days = (latest - oldest).days if (oldest and latest) else None

    return {
        "total_documents": len(documents),
        "dated_documents": len(dated_docs),
        "undated_documents": undated,
        "oldest_document_date": oldest.isoformat() if oldest else None,
        "latest_document_date": latest.isoformat() if latest else None,
        "total_span_days": span_days,
        "documents_by_year": dict(by_year),
        "documents_by_quarter": dict(sorted(by_quarter.items())),
        "documents_by_month": dict(sorted(by_month.items())),
        "events_by_year": dict(events_by_year),
        "events_by_quarter": dict(sorted(events_by_quarter.items())),
        "events_by_month": dict(sorted(events_by_month.items())),
    }


def _entity_documents(entity, documents):
    """Real, literal (case-insensitive) substring match on document title only -- the same,
    already-real signal M.5's entity counts used. No fuzzy matching, no invented mentions."""
    needle = entity.lower()
    return {doc_id: doc for doc_id, doc in documents.items()
            if needle in (doc.get("title") or "").lower()}


def _entity_events(entity, events):
    return {eid: ev for eid, ev in events.items() if entity in (ev.get("entities") or [])}


def entity_temporal_profile(entity, documents=None, events=None, min_independent_for_longitudinal=2):
    """Real per-entity temporal profile. independent_source_family_count reuses the change-layer
    independence gate over this entity's events (NOT a separate independence system -- Priority 2
    discipline). has_before_state/has_after_state are placeholders that stay False unless a real
    caller supplies genuinely comparable before/after evidence elsewhere (Priority 8: this module
    never infers before/after from calendar span alone)."""
    documents = documents if documents is not None else load_documents()
    events = events if events is not None else load_events()

    ent_docs = _entity_documents(entity, documents)
    ent_events = _entity_events(entity, events)

    dated = [d for doc in ent_docs.values() if (d := _parse_date(doc.get("published"))) is not None]
    first_seen = min(dated) if dated else None
    last_seen = max(dated) if dated else None
    span_days = (last_seen - first_seen).days if (first_seen and last_seen) else None
    distinct_quarters = {_quarter(d) for d in dated}

    independent_source_family_count = None
    if ent_events:
        gate = _load_independence_gate()
        documents_by_id = gate.load_documents() if documents is None else documents
        try:
            independent_source_family_count = gate.independent_evidence_count(
                list(ent_events.keys()), ent_events, documents_by_id)
        except Exception:
            independent_source_family_count = UNKNOWN

    if not ent_docs:
        status = NO_DATA
    elif span_days is None:
        status = UNKNOWN
    elif span_days == 0:
        status = POINT_IN_TIME
    elif len(distinct_quarters) >= 2 and len(ent_events) >= 1:
        # Real comparable-period spread (>=2 distinct calendar quarters) AND at least one
        # confirmed production event -- calendar span alone (e.g. one Sept doc + one Oct doc
        # with zero events) is deliberately NOT enough; see Priority 8 discipline above.
        status = MULTI_PERIOD if span_days < 365 else LONGITUDINAL
    else:
        status = SHORT_WINDOW

    return {
        "entity": entity,
        "document_count": len(ent_docs),
        "event_count": len(ent_events),
        "first_seen": first_seen.isoformat() if first_seen else None,
        "last_seen": last_seen.isoformat() if last_seen else None,
        "span_days": span_days,
        "independent_source_family_count": independent_source_family_count,
        "has_before_state": False,
        "has_after_state": False,
        "temporal_depth_status": status,
    }
