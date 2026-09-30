# STAGE 7 PHASE M — Historical Analogy (Te spec section 19-22). Deterministic only: this
# module never invents a historical case. It first audits whether the corpus contains any
# evidence old enough to plausibly ground a historical comparison; if not, the honest result
# is HISTORICAL_EVIDENCE_GAP, per Te's explicit instruction in the section 22 directive.
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from foresight_schema import (
    new_historical_analogy_shell, validate_analogy,
    new_historical_analogy_shell_v2, MECHANISM_TYPES, MIN_EVIDENCE_IDS_FOR_SOURCED_ANALOGY,
)
from historical_evidence import load_historical_evidence
from historical_source_independence import independent_evidence_count

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DOCUMENTS_PATH = ROOT / "intel" / "documents.json"

# A document must be at least this many days older than the newest document in the corpus to
# even count as "historical" background for an analogy. This is a conservative, documented
# threshold - not tuned to force a non-gap result.
HISTORICAL_AGE_DAYS = 365


def _load_documents(documents=None):
    if documents is not None:
        return documents
    if not DOCUMENTS_PATH.exists():
        return {}
    return json.loads(DOCUMENTS_PATH.read_text(encoding="utf-8"))


def _parse_date(s):
    try:
        parsed = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None
    # This corpus mixes naive (date-only, no offset) and timezone-aware `published` strings
    # across sources. Comparing them with max()/min() raises TypeError. Normalizing a naive
    # value to UTC is a safe, conservative assumption here -- it only affects this module's own
    # age-spread audit (never the stored document data), and misclassifying a date's timezone by
    # a few hours cannot flip whether a document clears the 365-day HISTORICAL_AGE_DAYS threshold.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def audit_historical_evidence(documents=None):
    """Returns whether the corpus has ANY document old enough to ground a real historical
    analogy, plus the concrete age spread found. This is the honest gap-detection Te's spec
    section 22 asks for, run BEFORE any analogy is ever built."""
    documents = _load_documents(documents)
    dates = [d for d in (_parse_date(doc.get("published", "")) for doc in documents.values())
             if d is not None]
    if not dates:
        return {"has_historical_evidence": False, "oldest_document_age_days": None,
                "documents_with_dates": 0}
    newest = max(dates)
    oldest = min(dates)
    age_days = (newest - oldest).days
    return {
        "has_historical_evidence": age_days >= HISTORICAL_AGE_DAYS,
        "oldest_document_age_days": age_days,
        "documents_with_dates": len(dates),
    }


def _analogy_id(topic):
    return "analogy_" + hashlib.sha1(topic.encode("utf-8")).hexdigest()[:16]


def build_historical_analogy(topic, historical_case=None, similarities=None, differences=None,
                              evidence_document_ids=None, documents=None):
    """Builds a historical analogy candidate for `topic`. If the corpus audit shows no real
    historical evidence, or the caller supplies no historical_case/differences, this returns a
    HISTORICAL_EVIDENCE_GAP / ANALOGY_REJECTED_INCOMPLETE record - never a fabricated analogy.
    This module supplies no historical_case data itself (that is a human/analyst input, per
    Te's no-fabrication rule); it only validates and gates."""
    audit = audit_historical_evidence(documents)
    shell = new_historical_analogy_shell(
        _analogy_id(topic), topic, historical_case=historical_case,
        similarities=similarities, differences=differences,
        evidence_document_ids=evidence_document_ids,
    )
    if not audit["has_historical_evidence"]:
        shell["status"] = "HISTORICAL_EVIDENCE_GAP"
        shell["gap_reason"] = (
            f"corpus spans only {audit['oldest_document_age_days']} days across "
            f"{audit['documents_with_dates']} dated documents - insufficient historical depth"
            if audit["documents_with_dates"] else "no dated documents found in corpus"
        )
        return shell
    return validate_analogy(shell)


# =============================================================================
# PHASE M.2 — mechanism-first analogy pipeline (Te spec step 3). Extends this module rather
# than building a parallel system: reuses new_historical_analogy_shell_v2's richer shape and
# the existing ANALOGY_REJECTED_INCOMPLETE rule, adding EVIDENCE_IDS sufficiency,
# source-independence-aware confidence, and mandatory pipeline ordering as real function calls
# (not just a comment describing the order).
#
# Required order, each step a real function: CURRENT CHANGE -> MECHANISM EXTRACTION ->
# HISTORICAL MECHANISM RETRIEVAL -> SIMILARITY TEST -> DIFFERENCE TEST -> BOUNDARY CONDITION
# TEST -> EVIDENCE SUFFICIENCY -> ANALOGY STATUS. A bare keyword match can never by itself
# produce anything above CANDIDATE - only a MECHANISM overlap plus real evidence can.
# =============================================================================


def extract_mechanism(current_phenomenon_text, keyword_to_mechanism):
    """CURRENT CHANGE -> MECHANISM EXTRACTION. keyword_to_mechanism is an explicit, caller-
    supplied {keyword: MECHANISM_TYPE} map (never inferred by this function from free text
    alone) - this module does not do NLP/keyword-guessing of mechanisms on its own; it only
    applies a mapping the caller is responsible for justifying. Returns the set of
    MECHANISM_TYPES whose keyword appears in the text, or an empty set (honest, no match)."""
    text_lower = (current_phenomenon_text or "").lower()
    found = set()
    for keyword, mechanism in keyword_to_mechanism.items():
        assert mechanism in MECHANISM_TYPES, mechanism
        if keyword.lower() in text_lower:
            found.add(mechanism)
    return found


def retrieve_historical_mechanism_evidence(mechanisms, evidence_registry=None):
    """HISTORICAL MECHANISM RETRIEVAL: given a set of MECHANISM_TYPES, returns the
    HistoricalEvidence records that were tagged with one of those mechanisms - real records
    only, never synthesized. Retrieval is by MECHANISM field, never by bare keyword/string
    similarity on event_or_process text (Te spec's explicit prohibition)."""
    evidence_registry = evidence_registry if evidence_registry is not None else load_historical_evidence()
    return {
        eid: rec for eid, rec in evidence_registry.items()
        if rec.get("mechanism") in mechanisms
    }


def similarity_test(current_similarities, matched_evidence):
    """SIMILARITY TEST: an analogy can only claim similarity backed by at least one matched
    historical-mechanism evidence record; caller-asserted similarities with zero matched
    evidence are dropped rather than kept as unfounded claims."""
    return list(current_similarities) if matched_evidence else []


def difference_test(differences):
    """DIFFERENCE TEST: unchanged rule from Phase M (an analogy MUST state at least one real
    difference) - just named as its own pipeline stage here."""
    return list(differences or [])


def boundary_condition_test(boundary_conditions):
    """BOUNDARY CONDITION TEST: an analogy with zero stated boundary conditions is not
    rejected outright (boundary conditions can be genuinely unexplored), but it can never
    reach SUPPORTED status - only INSUFFICIENT_EVIDENCE/CANDIDATE at best. Returns the list
    unchanged; the enforcement happens in analogy_status()."""
    return list(boundary_conditions or [])


def evidence_sufficiency(evidence_ids, evidence_registry=None, reports_on_pairs=None):
    """EVIDENCE SUFFICIENCY: uses the source-independence adapter so that N evidence records
    citing the same underlying source never count as N independent confirmations. Returns a
    dict with raw_count, independent_count, and sufficient (bool, requires
    MIN_EVIDENCE_IDS_FOR_SOURCED_ANALOGY independent records with real source provenance -
    UNKNOWN-provenance records are counted at face value by the adapter but never inflate the
    independent count, per historical_source_independence.py's contract)."""
    evidence_registry = evidence_registry if evidence_registry is not None else load_historical_evidence()
    sourced_ids = [eid for eid in evidence_ids
                   if evidence_registry.get(eid, {}).get("evidence_status") == "VERIFIED_STRUCTURED"]
    independent_count = independent_evidence_count(sourced_ids, evidence_registry, reports_on_pairs)
    return {
        "raw_count": len(evidence_ids),
        "sourced_count": len(sourced_ids),
        "independent_count": independent_count,
        "sufficient": independent_count >= MIN_EVIDENCE_IDS_FOR_SOURCED_ANALOGY,
    }


def analogy_status(similarities, differences, boundary_conditions, sufficiency):
    """ANALOGY STATUS: the single place that decides the final status, applying every prior
    gate. A bare keyword/mechanism match with no sourced evidence can never produce anything
    stronger than ANALOGY_REJECTED_NO_SOURCE; missing differences always wins as
    ANALOGY_REJECTED_INCOMPLETE (Phase M's original, unmodified rule) regardless of evidence."""
    if not differences:
        return "ANALOGY_REJECTED_INCOMPLETE"
    if not sufficiency["sufficient"]:
        if sufficiency["sourced_count"] == 0:
            return "ANALOGY_REJECTED_NO_SOURCE"
        return "INSUFFICIENT_EVIDENCE"
    if not similarities:
        return "INSUFFICIENT_EVIDENCE"
    if not boundary_conditions:
        # Real similarity + difference + sourced/independent evidence, but boundary conditions
        # genuinely unexplored - still not strong enough for SUPPORTED (Te spec: keyword/
        # mechanism match alone never yields a strong status; boundary-condition analysis is
        # part of what "strong" requires here).
        return "INSUFFICIENT_EVIDENCE"
    return "SUPPORTED"


def build_analogy_v2(analogy_id, current_phenomenon, historical_process,
                      current_phenomenon_text, keyword_to_mechanism, candidate_similarities,
                      differences, boundary_conditions=None, historical_outcomes=None,
                      present_conditions=None, present_relevance=None, limitations=None,
                      counteranalogy=None, evidence_registry=None, reports_on_pairs=None):
    """The full required pipeline, run in order as real function calls (not a comment):
    CURRENT CHANGE -> MECHANISM EXTRACTION -> HISTORICAL MECHANISM RETRIEVAL ->
    SIMILARITY TEST -> DIFFERENCE TEST -> BOUNDARY CONDITION TEST -> EVIDENCE SUFFICIENCY ->
    ANALOGY STATUS. Never auto-converts the result into a future prediction: `present_relevance`
    (if supplied) must be one of PRESENT_RELEVANCE_VALUES, enforced in the schema constructor."""
    mechanisms = extract_mechanism(current_phenomenon_text, keyword_to_mechanism)               # MECHANISM EXTRACTION
    matched_evidence = retrieve_historical_mechanism_evidence(mechanisms, evidence_registry)     # HISTORICAL MECHANISM RETRIEVAL
    similarities = similarity_test(candidate_similarities, matched_evidence)                     # SIMILARITY TEST
    diffs = difference_test(differences)                                                         # DIFFERENCE TEST
    boundaries = boundary_condition_test(boundary_conditions)                                     # BOUNDARY CONDITION TEST
    evidence_ids = sorted(matched_evidence.keys())
    sufficiency = evidence_sufficiency(evidence_ids, evidence_registry, reports_on_pairs)         # EVIDENCE SUFFICIENCY
    status = analogy_status(similarities, diffs, boundaries, sufficiency)                         # ANALOGY STATUS

    confidence = "UNKNOWN"
    if status == "SUPPORTED":
        confidence = "MEDIUM" if sufficiency["independent_count"] < 2 else "HIGH"
    elif status == "INSUFFICIENT_EVIDENCE":
        confidence = "LOW"

    shell = new_historical_analogy_shell_v2(
        analogy_id, current_phenomenon, historical_process,
        similarities=similarities, differences=diffs,
        shared_mechanisms=sorted(mechanisms), different_mechanisms=[],
        boundary_conditions=boundaries, historical_outcomes=historical_outcomes,
        present_conditions=present_conditions, present_relevance=present_relevance,
        limitations=limitations, counteranalogy=counteranalogy,
        evidence_ids=evidence_ids, confidence=confidence,
    )
    shell["status"] = status
    shell["mechanisms_extracted"] = sorted(mechanisms)
    shell["evidence_sufficiency"] = sufficiency
    return shell
