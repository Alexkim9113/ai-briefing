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
