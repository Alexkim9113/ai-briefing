# PHASE M.5E-3 -- item 3: deterministic mapping from a Deep Pilot evidence-chain node's original
# per-node status (REAL_EVIDENCE / NOTED / one of deep_pilot.GAP_STATUSES) to the M.5E-3 spec's
# node-support vocabulary: SUPPORTED / PARTIALLY_SUPPORTED / INSUFFICIENT_EVIDENCE / NOT_FOUND /
# NOT_APPLICABLE / UNKNOWN.
#
# This is a SEPARATE, NEWER vocabulary from deep_pilot.py's original per-node "status" field
# (M.5E-2). It does not replace or discard that original detail -- evaluate_node_support() reads
# a node result and returns one of the six labels; the caller keeps the original node dict
# (status/document_id/title/reason) alongside it.
#
# Zero LLM. Deterministic Python, stdlib only.
#
# MAPPING RULES (documented, in priority order -- first rule that matches wins):
#
# 1. REAL_EVIDENCE with a non-null document_id  -> SUPPORTED
#    A real document was found and directly resolves this node's evidentiary role.
#
# 2. NOTED (deep_pilot's UNCERTAINTY node type -- there IS real evidence behind the chain, but
#    the node itself flags a known structural limitation, e.g. "sample rests on one document")
#    -> PARTIALLY_SUPPORTED
#    The node is not a gap (something real informs it), but it is explicitly weaker than a
#    clean SUPPORTED result -- exactly the distinction PARTIALLY_SUPPORTED exists for.
#
# 3. status == "UNKNOWN" (deep_pilot.GAP_STATUSES includes a literal "UNKNOWN" catch-all)
#    -> UNKNOWN
#    Preserves deep_pilot's own "we do not know" signal rather than forcing it into NOT_FOUND.
#
# 4. status in {"SOURCE_GAP", "TEMPORAL_GAP", "RESEARCH_GAP", "HISTORY_GAP",
#    "COUNTEREVIDENCE_GAP", "GEOGRAPHIC_GAP"} -> a real, deliberate search was run (a real
#    keyword/field/date-window check) and it came back empty -> NOT_FOUND.
#    These are all "we looked for a specific real document/type and none exists in the corpus"
#    gaps, which is the definition of NOT_FOUND, not INSUFFICIENT_EVIDENCE (that label is
#    reserved for cases 5/6 below, where the *search itself* is structurally limited, not just
#    its result).
#
# 5. status == "STATISTICAL_GAP" -> INSUFFICIENT_EVIDENCE.
#    This is not a per-topic search that came back empty -- it is a corpus-wide, structural
#    absence (statistical_source_ratio() == 0/597 for the ENTIRE corpus, not just this topic),
#    so no search specific to this topic could ever have found something. The evidentiary base
#    itself is insufficient, which is exactly what INSUFFICIENT_EVIDENCE means here.
#
# 6. Any node explicitly marked as out of scope for a given topic (a caller may pass
#    applicable=False on a node dict to say "this node's methodology does not apply to this
#    topic", e.g. a topic with no defined cross-domain phrase list) -> NOT_APPLICABLE. deep_pilot
#    chains never currently produce this on their own -- it exists so a future topic that
#    legitimately has no CROSS_DOMAIN_EFFECT methodology (rather than a searched-and-empty one)
#    is not miscoded as NOT_FOUND. Included for completeness and tested at the boundary.
#
# 7. Anything else unrecognized -> UNKNOWN (safe default, never silently guessed into SUPPORTED).
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import deep_pilot as dp  # noqa: E402

SUPPORTED = "SUPPORTED"
PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
NOT_FOUND = "NOT_FOUND"
NOT_APPLICABLE = "NOT_APPLICABLE"
UNKNOWN = "UNKNOWN"

SUPPORT_VOCABULARY = (SUPPORTED, PARTIALLY_SUPPORTED, INSUFFICIENT_EVIDENCE, NOT_FOUND,
                      NOT_APPLICABLE, UNKNOWN)

# "Searched a specific real slice of the corpus (topic-scoped keywords/fields/dates) and found
# nothing" -> NOT_FOUND.
_NOT_FOUND_STATUSES = frozenset({
    "SOURCE_GAP", "TEMPORAL_GAP", "RESEARCH_GAP", "HISTORY_GAP", "COUNTEREVIDENCE_GAP",
    "GEOGRAPHIC_GAP",
})

# "The evidentiary base itself is corpus-wide insufficient, not just this topic's slice of it"
# -> INSUFFICIENT_EVIDENCE.
_INSUFFICIENT_EVIDENCE_STATUSES = frozenset({"STATISTICAL_GAP"})


def evaluate_node_support(node_result):
    """Map one evidence-chain node dict (as produced by deep_pilot.py / multi_topic_pilot.py's
    build_evidence_chain()) to the SUPPORTED/PARTIALLY_SUPPORTED/INSUFFICIENT_EVIDENCE/NOT_FOUND/
    NOT_APPLICABLE/UNKNOWN vocabulary. Never mutates node_result. See module docstring for the
    documented rule order."""
    if not isinstance(node_result, dict):
        return UNKNOWN

    if node_result.get("applicable") is False:
        return NOT_APPLICABLE

    status = node_result.get("status")

    if status == "REAL_EVIDENCE" and node_result.get("document_id"):
        return SUPPORTED

    if status == "NOTED":
        return PARTIALLY_SUPPORTED

    if status == "UNKNOWN":
        return UNKNOWN

    if status in _NOT_FOUND_STATUSES:
        return NOT_FOUND

    if status in _INSUFFICIENT_EVIDENCE_STATUSES:
        return INSUFFICIENT_EVIDENCE

    return UNKNOWN


def evaluate_chain(chain):
    """Apply evaluate_node_support() to every node in a 10-node evidence chain dict, returning
    {node_name: support_label}. Does not alter or drop the original chain."""
    return {name: evaluate_node_support(node) for name, node in chain.items()}


def support_distribution(chain):
    """Count how many nodes fall into each of the 6 support labels for one chain."""
    counts = {label: 0 for label in SUPPORT_VOCABULARY}
    for label in evaluate_chain(chain).values():
        counts[label] += 1
    return counts
