# M.5F SECTIONS 7-10 -- Query Planner, Query/Entity Expansion, Source Router.
#
# Te's core diagnosis: the collection infrastructure already works; the problem is HOW evidence
# is searched for. A single keyword set reused for every Evidence Type collapses the required
# TOPIC -> QUESTION -> EVIDENCE REQUIREMENT -> SOURCE CLASS -> SEARCH STRATEGY pipeline into
# "KEYWORD -> SEARCH RESULTS", which this module exists to stop doing.
#
# This module is PLANNING ONLY: it returns query plans (strings + source-class routing) for a
# caller (an acquisition connector) to execute. It fetches nothing itself, admits nothing, and
# never writes documents.json. It reuses, rather than reinvents, two already-built vocabularies:
#   - SOURCE_TYPES from intel/evidence_supply/source_registry.py (the only Source Class taxonomy
#     this codebase already has, built and tested in Production Evidence Supply v1.0).
#   - production_events.json's own real `entities` field, for Entity Expansion (Section 9) --
#     this module NEVER invents an entity; it only surfaces entities already observed in this
#     corpus's real events for a given topic's documents, with their observed frequency.
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
DOCUMENTS_PATH = INTEL_DIR / "documents.json"
PRODUCTION_EVENTS_PATH = INTEL_DIR / "event_production" / "production_events.json"

sys.path.insert(0, str(INTEL_DIR / "evidence_supply"))
import source_registry as _source_registry  # noqa: E402

SOURCE_TYPES = _source_registry.SOURCE_TYPES

# The 8 Evidence Types Te's spec names (Section 7) -- a search-strategy vocabulary, deliberately
# separate from intel/evidence_pipeline/schema.py's EVIDENCE_TYPES (FACTUAL/MEASUREMENT/...),
# which classifies an already-extracted claim rather than planning how to search for one.
EVIDENCE_TYPES = (
    "CURRENT_EVENT", "TRANSITION", "STATISTICS", "HISTORICAL", "COUNTEREVIDENCE",
    "ALTERNATIVE_EXPLANATION", "RESEARCH", "POLICY",
)

# --- SECTION 10: SOURCE ROUTER -- Evidence Type -> preferred Source Class(es), most-preferred
# first. Routing is a documented judgment call (what kind of institution is actually likely to
# hold this kind of evidence), not derived from data -- same discipline as source_registry.py's
# own SOURCE_TYPES assignment.
_EVIDENCE_TYPE_TO_SOURCE_TYPES = {
    "CURRENT_EVENT": ("WIRE", "MEDIA", "COMPANY"),
    "TRANSITION": ("GOVERNMENT", "REGULATOR", "RESEARCH_INSTITUTE", "MEDIA"),
    "STATISTICS": ("GOVERNMENT", "INTERNATIONAL_ORGANIZATION", "RESEARCH_INSTITUTE"),
    "HISTORICAL": ("JOURNAL", "RESEARCH_INSTITUTE", "UNIVERSITY", "MEDIA"),
    "COUNTEREVIDENCE": ("JOURNAL", "RESEARCH_INSTITUTE", "SPECIALIST_MEDIA", "MEDIA"),
    "ALTERNATIVE_EXPLANATION": ("JOURNAL", "RESEARCH_INSTITUTE", "UNIVERSITY"),
    "RESEARCH": ("JOURNAL", "UNIVERSITY", "RESEARCH_INSTITUTE"),
    "POLICY": ("GOVERNMENT", "LEGISLATURE", "COURT", "REGULATOR"),
}


def route_evidence_type_to_source_classes(evidence_type):
    """SECTION 10: never defaults to a generic news/DISCOVERY_PLATFORM search -- every Evidence
    Type gets an explicit, ranked list of the SOURCE_TYPES most likely to hold that kind of
    evidence. Raises on an unknown evidence_type rather than silently falling back."""
    if evidence_type not in _EVIDENCE_TYPE_TO_SOURCE_TYPES:
        raise ValueError(f"unknown evidence_type: {evidence_type!r} (must be one of {EVIDENCE_TYPES})")
    return _EVIDENCE_TYPE_TO_SOURCE_TYPES[evidence_type]


# --- SECTION 7: QUERY PLANNER -- distinct query template per Evidence Type, parameterized by
# the caller's own topic terms. Templates return QUERY STRINGS the caller executes against
# whatever connector serves the routed Source Class above -- this module does not call a search
# API itself.
def _fmt(terms):
    return " ".join(terms) if isinstance(terms, (list, tuple)) else str(terms)


def build_query_plan(evidence_type, topic_terms, entities=None, date_range=None):
    """Returns {"evidence_type", "source_classes", "queries": [str, ...], "note"}. `topic_terms`
    is the caller's own subject-matter terms (e.g. ["AI", "energy demand"]); this function adds
    the Evidence-Type-specific structure around them -- it never substitutes its own guessed
    subject matter."""
    if evidence_type not in EVIDENCE_TYPES:
        raise ValueError(f"unknown evidence_type: {evidence_type!r}")
    terms = _fmt(topic_terms)
    entity_terms = _fmt(entities) if entities else ""
    source_classes = route_evidence_type_to_source_classes(evidence_type)

    if evidence_type == "CURRENT_EVENT":
        queries = [f"{terms} {entity_terms} announcement".strip(), f"{terms} {entity_terms} latest".strip()]
    elif evidence_type == "TRANSITION":
        # Section 16: explicit temporal conditions, not just a bare topic keyword -- a
        # TRANSITION claim needs a BEFORE state and an AFTER state, not just "recent".
        start, end = (date_range or (None, None))
        queries = [
            f"{terms} before {start}" if start else f"{terms} previous state baseline",
            f"{terms} after {end}" if end else f"{terms} current state change",
            f"{terms} shift OR transition OR change over time",
        ]
    elif evidence_type == "STATISTICS":
        queries = [f"{terms} statistics official data", f"{terms} time series annual",
                   f"{terms} dataset table"]
    elif evidence_type == "HISTORICAL":
        # Section 16: temporal condition is about what PERIOD the document analyzes, not when it
        # was published -- a 2026 retrospective on a 1980s event is still HISTORICAL evidence.
        queries = [f"{terms} history retrospective analysis", f"{terms} precedent historical case",
                   f"{terms} decades ago OR previous era"]
    elif evidence_type == "COUNTEREVIDENCE":
        # Section 18: hypothesis-first. The caller must supply the actual hypothesis as
        # topic_terms; this only adds the counter-proposition search structure around it.
        queries = [f"{terms} contrary evidence", f"{terms} fails OR disputed OR contested",
                   f"{terms} criticism OR rebuttal"]
    elif evidence_type == "ALTERNATIVE_EXPLANATION":
        # Section 19: outcome-first. topic_terms should be the OUTCOME being explained.
        queries = [f"{terms} alternative explanation", f"{terms} other cause OR driver",
                   f"{terms} not caused by"]
    elif evidence_type == "RESEARCH":
        queries = [f"{terms} peer-reviewed study", f"{terms} research paper findings"]
    else:  # POLICY
        queries = [f"{terms} official policy document", f"{terms} regulation OR bill OR ruling",
                   f"{terms} government statement"]

    return {
        "evidence_type": evidence_type,
        "source_classes": list(source_classes),
        "queries": [q.strip() for q in queries if q.strip()],
        "note": "Planning output only -- caller executes these against a connector for the "
                "routed source_classes; this function performs no network access.",
    }


# --- SECTION 8: QUERY EXPANSION -- mechanism decomposition. Expansion terms are SEARCH AIDS
# ONLY, never themselves evidence (Te's explicit instruction) -- a document matching an expansion
# term still has to pass the same admission gate as any other candidate. Registered per topic as
# real worked examples (not a generic NLP expander, which risks exactly the baseless-tagging
# failure mode Section 47 prohibits) -- AI_ENERGY_INFRA is Te's own worked example from the M.5F
# spec; AI_LABOR is this phase's newly co-equal pilot, decomposed the same way.
_QUERY_EXPANSION_REGISTRY = {
    "AI_ENERGY_INFRA": (
        "data center electricity demand", "computing power demand", "grid interconnection",
        "transmission capacity", "power purchase agreement", "generation capacity",
        "load forecasting", "server efficiency", "chip energy efficiency", "cooling demand",
        "renewable procurement",
    ),
    "AI_LABOR": (
        "employment statistics", "occupational change", "productivity growth",
        "job displacement", "job creation", "wage effects", "task automation",
        "labor policy", "worker retraining", "sector employment difference",
    ),
}


def expand_query_terms(topic_key):
    """SECTION 8: returns the registered expansion terms for a topic, or an empty tuple if this
    topic has no registered decomposition yet (honest -- never auto-generates one). Expansion
    terms are search aids; the caller must still run them through build_query_plan() and the
    real admission gate, never treat a match as evidence by itself."""
    return _QUERY_EXPANSION_REGISTRY.get(topic_key, ())


# --- SECTION 9: ENTITY EXPANSION -- only entities already observed in this corpus's real
# production events for documents matching topic_terms. Never fabricates an entity; an empty
# result (no matching events) is reported as such, not padded with guessed names.
def _load_production_events():
    if not PRODUCTION_EVENTS_PATH.exists():
        return {}
    return json.loads(PRODUCTION_EVENTS_PATH.read_text(encoding="utf-8"))


def expand_entities_for_topic(topic_terms, events=None):
    """Returns a Counter of {entity_name: observed_event_count} for production events whose
    event_name contains any of topic_terms (case-insensitive substring match on the event's own
    real event_name -- never on a document's full text, and never inventing an entity not
    already present in some event's real `entities` list)."""
    events = events if events is not None else _load_production_events()
    terms_lower = [t.lower() for t in (topic_terms if isinstance(topic_terms, (list, tuple)) else [topic_terms])]
    counts = Counter()
    for ev in events.values():
        name = (ev.get("event_name") or "").lower()
        if any(t in name for t in terms_lower):
            for entity in ev.get("entities", []):
                counts[entity] += 1
    return counts


# --- SECTION 32: NOT_FOUND GAP CLASSIFICATION -- before any new code is written in response to
# a failed search, the caller must say WHY it failed. TRUE_NULL (searched appropriately, the
# evidence genuinely doesn't exist) is a valid, important, non-defect outcome -- never silently
# treated the same as a connector bug.
NOT_FOUND_GAP_CLASSES = (
    "SOURCE_GAP", "QUERY_GAP", "ACCESS_GAP", "CORPUS_GAP", "CLASSIFICATION_GAP",
    "TEMPORAL_GAP", "GEOGRAPHIC_GAP", "TRUE_NULL",
)


def classify_not_found(evidence_type, source_classes_attempted, queries_attempted,
                        source_reachable=True, within_corpus_date_range=True,
                        geography_covered=True, exhausted_query_expansion=False):
    """Classifies a NOT_FOUND search outcome into one of NOT_FOUND_GAP_CLASSES, given what the
    caller actually attempted (never guessed from the outside). The caller passes its own
    observations (did it even route to a real source class, was the source reachable, did the
    query cover the right date range/geography); this function only applies the decision logic,
    never fabricates what was tried."""
    if not source_classes_attempted:
        return "SOURCE_GAP"  # Section 10 routing was never consulted at all
    if not source_reachable:
        return "ACCESS_GAP"
    if not within_corpus_date_range:
        return "TEMPORAL_GAP"
    if not geography_covered:
        return "GEOGRAPHIC_GAP"
    if not queries_attempted:
        return "QUERY_GAP"
    if not exhausted_query_expansion:
        # Section 8: a caller that only tried the bare topic term, never the registered
        # expansion terms, has not actually exhausted the search space yet.
        return "QUERY_GAP"
    return "TRUE_NULL"


def main():
    print("Query Planner is a planning-only library -- see tests for worked examples.")
    for et in EVIDENCE_TYPES:
        plan = build_query_plan(et, ["AI energy demand"])
        print(et, "->", plan["source_classes"], plan["queries"][:1])


if __name__ == "__main__":
    main()
