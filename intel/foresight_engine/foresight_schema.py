# STAGE 7 PHASE M — Foresight Engine shared vocabulary.
# NO FABRICATION: every object below defaults to a GAP/UNKNOWN status until real evidence is
# found by the deterministic builders in this package. Nothing here calls an LLM.
#
# Historical Analogy (Te spec section 19-22): every analogy MUST explicitly answer "what is
# different?" (differences must be a non-empty list) or it is downgraded to
# HISTORICAL_EVIDENCE_GAP / ANALOGY_REJECTED_INCOMPLETE - this is enforced in validate_analogy()
# below, not left as a comment.
HISTORICAL_ANALOGY_STATUS = (
    "CANDIDATE", "SUPPORTED", "REJECTED", "HISTORICAL_EVIDENCE_GAP",
    "ANALOGY_REJECTED_INCOMPLETE",
)

# Cross-Domain Connection (section 7, 23, 60): causal humility - never CAUSES.
CROSS_DOMAIN_RELATION_TYPES = (
    "ASSOCIATED_WITH", "PRECEDES", "POSSIBLE_DRIVER", "CONTRIBUTING_FACTOR",
)

# Knowledge gap / coverage (section 39-43).
COVERAGE_DIMENSIONS = ("CATEGORY", "FIELD", "SOURCE", "TEMPORAL", "GEOGRAPHIC")
GAP_STATUS = ("OPEN", "PARTIALLY_FILLED", "FILLED")
# GEOGRAPHIC coverage is honestly UNKNOWN for every document: intel/documents.json carries no
# geography field anywhere in this corpus (verified by inspection), so we never infer/guess one.
GEOGRAPHIC_UNKNOWN = "UNKNOWN"


def new_historical_analogy_shell(analogy_id, topic, historical_case=None, similarities=None,
                                  differences=None, evidence_document_ids=None):
    return {
        "analogy_id": analogy_id,
        "topic": topic,
        "historical_case": historical_case,
        "similarities": similarities or [],
        "differences": differences or [],
        "evidence_document_ids": evidence_document_ids or [],
        "status": "CANDIDATE",
        "generated_by": "CODE_DETERMINISTIC",
    }


def validate_analogy(analogy):
    """Section 20: an analogy with no stated differences is not a valid analogy - it is
    downgraded, never silently accepted. Returns the (possibly downgraded) analogy."""
    if analogy["status"] == "HISTORICAL_EVIDENCE_GAP":
        return analogy
    if not analogy.get("historical_case") or not analogy.get("differences"):
        analogy["status"] = "ANALOGY_REJECTED_INCOMPLETE"
    return analogy


def new_cross_domain_connection_shell(connection_id, domain_a, domain_b, relation_type,
                                       shared_entities, evidence_note_ids, evidence_document_ids):
    assert relation_type in CROSS_DOMAIN_RELATION_TYPES, relation_type
    return {
        "connection_id": connection_id,
        "domain_a": domain_a,
        "domain_b": domain_b,
        "relation_type": relation_type,
        "shared_entities": shared_entities,
        "evidence_note_ids": evidence_note_ids,
        "evidence_document_ids": evidence_document_ids,
        "status": "CANDIDATE",
        "generated_by": "CODE_DETERMINISTIC",
    }


# =============================================================================
# PHASE M.2 — Historical Context & Analogy Infrastructure. Extends (never replaces) the
# Phase M vocabulary above. Same no-fabrication discipline: UNKNOWN is a legitimate, permanent
# value for geography/date/provenance - never inferred from language/publisher/TLD/guessing.
# =============================================================================

# The 8 required history areas (Te spec Phase M.2 step 2). Cross-links to the existing
# current-domain vocabulary (evidence_pipeline/schema.py REAL_DOMAINS) via a separate field
# on HistoricalEvidence, not by merging the two enums - a history area and a present-day
# domain are different kinds of things and must stay distinguishable.
HISTORY_DOMAINS = (
    "HISTORY_OF_TECHNOLOGY", "HISTORY_OF_INDUSTRY_ECONOMY", "HISTORY_OF_POLITICS_INSTITUTIONS",
    "HISTORY_OF_LABOR_SOCIETY", "HISTORY_OF_IDEAS", "HISTORY_OF_SCIENCE",
    "HISTORY_OF_MEDIA", "HISTORY_OF_CULTURE_ART",
)

GEOGRAPHY_VALUES = ("KOREA", "EAST_ASIA", "CHINA", "JAPAN", "US", "EUROPE", "GLOBAL",
                    "OTHER", "UNKNOWN")

# Temporal precision - never forced to a fake exact date. A record with only decade-level
# confidence stays DECADE-precision, permanently.
TEMPORAL_PRECISION = ("EXACT_DATE", "YEAR", "DECADE", "PERIOD", "APPROXIMATE", "UNKNOWN")

# Source hierarchy (Te spec "TIER_1..TIER_4"). TIER_1 = primary/archival/peer-reviewed
# scholarship; TIER_4 = unverified/secondary popular retelling. This module never assigns a
# tier the caller did not explicitly provide - no guessing a tier from domain name or style.
SOURCE_TIERS = ("TIER_1", "TIER_2", "TIER_3", "TIER_4")

SOURCE_TYPES = ("PEER_REVIEWED_SCHOLARSHIP", "ARCHIVAL_PRIMARY_DOCUMENT", "GOVERNMENT_RECORD",
                "ESTABLISHED_REFERENCE_WORK", "JOURNALISM_CONTEMPORANEOUS", "JOURNALISM_RETROSPECTIVE",
                "BOOK_SECONDARY", "OTHER", "UNKNOWN")

# Confidence: reuses structural_analysis_layer's existing qualitative vocabulary
# (CONFIDENCE_LEVELS = LOW/MEDIUM/HIGH in intel/structural_analysis_layer/schema.py) rather
# than inventing a new numeric score, per operator directive #25 (no fake probabilities).
HISTORICAL_CONFIDENCE_LEVELS = ("LOW", "MEDIUM", "HIGH", "UNKNOWN")

# HISTORICAL_FACT vs SCHOLARLY_INTERPRETATION vs METAXIS_INTERPRETATION must never collapse
# into one field/value (Te spec test 6). This is the claim-kind vocabulary for a
# HistoricalEvidence record's `documented_outcome`/`notes` characterization.
HISTORICAL_CLAIM_KIND = ("HISTORICAL_FACT", "SCHOLARLY_INTERPRETATION", "METAXIS_INTERPRETATION")

EVIDENCE_STATUS_VALUES = ("CANDIDATE", "VERIFIED_STRUCTURED", "REJECTED_NO_SOURCE",
                           "REJECTED_UNVERIFIABLE")

# Mechanism vocabulary for mechanism-FIRST analogy matching (Te spec step 3). Audited first:
# structural_analysis_layer/schema.py's DRIVER_RELATIONS (ASSOCIATED_WITH/ENABLES/CONSTRAINS/
# AMPLIFIES/ACCELERATES/...) describes a RELATION between a driver and a change, not a
# reusable named economic/social mechanism a historical and a current process can share - so
# none of that vocabulary fits this purpose and a small, explicit mechanism vocabulary is
# defined here instead (kept minimal, not open-ended).
MECHANISM_TYPES = ("COST_DECLINE", "SCALE_EXPANSION", "DISINTERMEDIATION",
                    "SCARCITY_MIGRATION", "POWER_SHIFT", "SKILL_DEVALUATION",
                    "GATEKEEPER_BYPASS", "OTHER")

# Historical-analogy status vocabulary, extended (never replaced). ANALOGY_REJECTED_NO_SOURCE
# is new: an analogy with similarities+differences but zero traceable HistoricalEvidence is
# rejected on sourcing grounds specifically, distinct from ANALOGY_REJECTED_INCOMPLETE
# (missing differences) so the two failure modes stay diagnosable.
HISTORICAL_ANALOGY_STATUS_V2 = (
    "CANDIDATE", "ANALOGY_REJECTED_INCOMPLETE", "ANALOGY_REJECTED_NO_SOURCE",
    "INSUFFICIENT_EVIDENCE", "SUPPORTED", "HISTORICAL_EVIDENCE_GAP",
)

# The ONLY vocabulary an analogy may ever use to characterize its relevance to the present.
# This is a closed, weak set - a bare "predicts X" / "PAST A -> THEREFORE FUTURE B" claim is
# never a valid value here (Te spec absolute rule + test 5).
PRESENT_RELEVANCE_VALUES = (
    "SUPPORTING_CONTEXT", "WEAK_SUPPORT", "CONDITIONAL_SUPPORT",
    "COUNTEREVIDENCE", "INSUFFICIENT_COMPARABILITY",
)

MIN_EVIDENCE_IDS_FOR_SOURCED_ANALOGY = 1


def new_historical_evidence_shell(
    historical_evidence_id, event_or_process, history_domain, current_domain_link=None,
    subdomain=None, geography="UNKNOWN", start_period=None, end_period=None,
    temporal_precision="UNKNOWN", actors=None, institutions=None, technology=None,
    mechanism=None, documented_outcome=None, claim_kind="HISTORICAL_FACT",
    source_id=None, source_type="UNKNOWN", source_tier=None, source_title=None,
    source_organization=None, publication_date=None, original_date=None,
    retrieved_at=None, canonical_url=None, confidence="UNKNOWN", notes=None,
):
    """No full source text is ever stored here - structured metadata + short factual notes
    only (Publication Firewall principle). geography/temporal_precision default to UNKNOWN and
    are NEVER inferred by this constructor - the caller supplies them or they stay UNKNOWN."""
    assert history_domain in HISTORY_DOMAINS, history_domain
    assert geography in GEOGRAPHY_VALUES, geography
    assert temporal_precision in TEMPORAL_PRECISION, temporal_precision
    assert claim_kind in HISTORICAL_CLAIM_KIND, claim_kind
    assert confidence in HISTORICAL_CONFIDENCE_LEVELS, confidence
    if source_tier is not None:
        assert source_tier in SOURCE_TIERS, source_tier
    assert source_type in SOURCE_TYPES, source_type

    has_source = bool(source_id) or bool(canonical_url) or bool(source_title)
    status = "VERIFIED_STRUCTURED" if has_source else "REJECTED_NO_SOURCE"

    return {
        "historical_evidence_id": historical_evidence_id,
        "event_or_process": event_or_process,
        "history_domain": history_domain,
        "current_domain_link": current_domain_link,
        "subdomain": subdomain,
        "geography": geography,
        "start_period": start_period,
        "end_period": end_period,
        "temporal_precision": temporal_precision,
        "actors": actors or [],
        "institutions": institutions or [],
        "technology": technology,
        "mechanism": mechanism,
        "documented_outcome": documented_outcome,
        "claim_kind": claim_kind,
        "source_id": source_id,
        "source_type": source_type,
        "source_tier": source_tier,
        "source_title": source_title,
        "source_organization": source_organization,
        "publication_date": publication_date,
        "original_date": original_date,
        "retrieved_at": retrieved_at,
        "canonical_url": canonical_url,
        "evidence_status": status,
        "confidence": confidence,
        "notes": notes,
        "generated_by": "CODE_DETERMINISTIC",
    }


def new_historical_analogy_shell_v2(
    analogy_id, current_phenomenon, historical_process, similarities=None, differences=None,
    shared_mechanisms=None, different_mechanisms=None, boundary_conditions=None,
    historical_outcomes=None, present_conditions=None, present_relevance=None,
    limitations=None, counteranalogy=None, evidence_ids=None, confidence="UNKNOWN",
):
    """Phase M.2 companion analogy object (extends the Phase M shape without removing it -
    see new_historical_analogy_shell above, which is unchanged and still used by
    build_historical_analogy()). counteranalogy is optional/nullable and is NEVER fabricated
    to fill it - None is a valid, expected value. observable_implications/candidate_indicators
    are structure-only placeholders for Phase M.3 (no real indicator values populated here)."""
    if present_relevance is not None:
        assert present_relevance in PRESENT_RELEVANCE_VALUES, present_relevance
    assert confidence in HISTORICAL_CONFIDENCE_LEVELS, confidence
    return {
        "analogy_id": analogy_id,
        "current_phenomenon": current_phenomenon,
        "historical_process": historical_process,
        "similarities": similarities or [],
        "differences": differences or [],
        "shared_mechanisms": shared_mechanisms or [],
        "different_mechanisms": different_mechanisms or [],
        "boundary_conditions": boundary_conditions or [],
        "historical_outcomes": historical_outcomes or [],
        "present_conditions": present_conditions or [],
        "present_relevance": present_relevance,
        "limitations": limitations or [],
        "counteranalogy": counteranalogy,
        "evidence_ids": evidence_ids or [],
        "confidence": confidence,
        "status": "CANDIDATE",
        "observable_implications": [],
        "candidate_indicators": [],
        "generated_by": "CODE_DETERMINISTIC",
    }


def new_operator_view_shell(view_id, author, statement, linked_hypothesis_ids=None,
                             linked_evidence_ids=None):
    """Section 36-37: Operator View is HUMAN-AUTHORED ONLY. No pipeline in this repo may call
    this constructor automatically - it is invoked only from an explicit human-triggered call
    (e.g. a private_api write path added by a later phase, or a manual script run by Te)."""
    if not author:
        raise ValueError("operator_view requires an explicit human author - never auto-created")
    return {
        "view_id": view_id,
        "author": author,
        "statement": statement,
        "linked_hypothesis_ids": linked_hypothesis_ids or [],
        "linked_evidence_ids": linked_evidence_ids or [],
        "status": "ACTIVE",
        "history": [],
    }
