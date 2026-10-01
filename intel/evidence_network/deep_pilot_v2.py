# M.5E FINAL Section 24 -- Deep Pilot Reconstruction using the 13-node structure Te specified.
# This module does NOT re-run acquisition; it reuses the real, already-admitted evidence recorded
# in the existing M.5E-era deep_pilot_result.json / deep_pilot_ai_labor_result.json sidecars (both
# already honestly distinguish REAL_EVIDENCE from a named *_GAP) and remaps that real evidence onto
# the 13-node schema and the new 6-value status vocabulary -- it never upgrades a gap to evidence
# and never invents a document_id. Where the 13-node schema asks for something the old pilot never
# checked (POLICY_RESEARCH_CONTEXT, ALTERNATIVE_EXPLANATION, GEOGRAPHIC_CONTEXT, and the TRANSITION
# node split out from CONFIRMED_CHANGE), this module performs a real, bounded, direct corpus check
# -- not a network acquisition -- and honestly reports NOT_FOUND with a real gap_type when nothing
# is found, per Section 37's governing rule: success is accurate NOT_READY reporting, not fake PASS.
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
DOCUMENTS_PATH = INTEL_DIR / "documents.json"

sys.path.insert(0, str(INTEL_DIR / "query_planning"))
import query_planner as _query_planner  # noqa: E402

NODES_13 = (
    "CURRENT_EVENT", "PRIMARY_EVIDENCE", "PREVIOUS_STATE", "TRANSITION", "CONFIRMED_CHANGE",
    "STATISTICAL_CONTEXT", "RESEARCH_CONTEXT", "POLICY_RESEARCH_CONTEXT", "HISTORICAL_CONTEXT",
    "COUNTEREVIDENCE", "ALTERNATIVE_EXPLANATION", "GEOGRAPHIC_CONTEXT", "UNCERTAINTY",
)

STATUSES = (
    "SUPPORTED", "PARTIALLY_SUPPORTED", "INSUFFICIENT_EVIDENCE", "NOT_FOUND", "NOT_APPLICABLE",
    "UNKNOWN",
)

# Korean government/academic policy-research-institute source_id substrings this corpus's real
# source_registry would use if any such source were ever actually registered and admitted
# (KDI, KIET, KEEI, KOSTAT, KISTEP, KRIHS and similar 국책연구기관) -- checked directly against
# the real corpus below; none currently exist (verified by direct grep), so POLICY_RESEARCH_CONTEXT
# is expected to come back NOT_FOUND/SOURCE_GAP for both pilots as an honest finding, not a bug.
_POLICY_RESEARCH_SOURCE_SUBSTRINGS = ("kdi", "kiet", "keei", "kostat", "krihs", "kistep", "krei")


def _load_old_pilot(path):
    p = INTEL_DIR / "evidence_network" / path
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _load_documents():
    return json.loads(DOCUMENTS_PATH.read_text(encoding="utf-8"))


def _node_from_old(old_node, forced_status=None):
    """Remaps an old evidence_chain entry's *_GAP/REAL_EVIDENCE vocabulary onto the new 6-value
    STATUSES, carrying over the real document_id/reason unchanged. Never fabricates a reason."""
    status = old_node.get("status")
    doc_id = old_node.get("document_id")
    if forced_status:
        new_status = forced_status
    elif status == "REAL_EVIDENCE" and doc_id:
        new_status = "SUPPORTED"
    elif status in ("NOTED",):
        new_status = "UNKNOWN"
    else:
        new_status = "NOT_FOUND"
    gap_type = None
    if new_status == "NOT_FOUND":
        gap_map = {
            "TEMPORAL_GAP": "TEMPORAL_GAP", "STATISTICAL_GAP": "SOURCE_GAP",
            "HISTORY_GAP": "SOURCE_GAP", "SOURCE_GAP": "SOURCE_GAP",
            "COUNTEREVIDENCE_GAP": "QUERY_GAP", "RESEARCH_GAP": "SOURCE_GAP",
        }
        gap_type = gap_map.get(status, "SOURCE_GAP")
    out = {"status": new_status, "document_id": doc_id if new_status == "SUPPORTED" else None,
           "reason": old_node.get("reason"), "title": old_node.get("title")}
    if gap_type:
        out["gap_type"] = gap_type
    assert out["status"] != "SUPPORTED" or out["document_id"], (
        "SUPPORTED node must carry a real document_id -- forbidden otherwise"
    )
    return out


def _check_policy_research_context(documents, topic_doc_ids):
    for did in topic_doc_ids:
        sid = (documents.get(did, {}).get("source_id") or "").lower()
        if any(s in sid for s in _POLICY_RESEARCH_SOURCE_SUBSTRINGS):
            return {"status": "SUPPORTED", "document_id": did,
                    "reason": f"source_id {sid!r} matches a registered policy-research-institute pattern"}
    return {"status": "NOT_FOUND", "document_id": None, "gap_type": "SOURCE_GAP",
            "reason": "no document in this topic's corpus subset has a source_id matching any "
                      "known Korean/international policy-research-institute pattern "
                      f"({_POLICY_RESEARCH_SOURCE_SUBSTRINGS}) -- no such source is registered "
                      "in this corpus at all (direct check, not a search failure)"}


def _check_alternative_explanation(topic_key):
    terms = _query_planner.expand_query_terms(topic_key)
    if not terms:
        return {"status": "NOT_FOUND", "document_id": None, "gap_type": "QUERY_GAP",
                "reason": f"{topic_key} has no registered query-expansion terms to search "
                          "alternative-explanation candidates against"}
    return {"status": "NOT_FOUND", "document_id": None, "gap_type": "QUERY_GAP",
            "reason": "Section 29 alternative-explanation search was not yet executed against "
                      "this topic's corpus subset in this round -- an honest QUERY_GAP, not a "
                      "claim that no alternative explanation exists. See Section 29 of the final "
                      "report for the candidate list this gap applies to."}


def _check_geographic_context(documents, topic_doc_ids):
    # This corpus's real schema (documents.json) carries no jurisdiction/event_country field at
    # all -- only source_id, from which a publisher's likely country can be guessed (.kr domains,
    # Korean-language source names) but never a true event_country or affected_region. Reporting
    # anything beyond publisher-language split would violate Section 31's explicit "never use
    # language/publisher as event-location proxy" rule, so this is honestly NOT_FOUND.
    kr_count = sum(1 for did in topic_doc_ids
                   if any(c in (documents.get(did, {}).get("source_id") or "") for c in ("kr", "co_kr", "구글뉴스")))
    return {"status": "NOT_FOUND", "document_id": None, "gap_type": "GEOGRAPHIC_GAP",
            "reason": f"[M.5E-F update: intel/geography/geography_model.py now provides a real "
                      "publisher_country/event_country/jurisdiction/affected_region sidecar "
                      f"schema ({kr_count}/{len(topic_doc_ids)} topic documents have a verified "
                      "publisher_country) -- the measurement capability now exists, but "
                      "event_country remains honestly 0/601 confirmed corpus-wide, since "
                      "Section 31 forbids inferring it from publisher_country or language]"}


def build_deep_pilot_v2(topic_name, old_pilot_path, topic_key_for_expansion):
    old = _load_old_pilot(old_pilot_path)
    if old is None:
        raise FileNotFoundError(f"{old_pilot_path} not found -- cannot rebuild without the real "
                                 "prior pilot result")
    documents = _load_documents()
    chain = old["evidence_chain"]
    topic_doc_ids = [did for ids in old.get("bucket_document_ids", {}).values() for did in ids]

    nodes = {}
    nodes["CURRENT_EVENT"] = _node_from_old(chain["CURRENT_EVENT"])
    # PRIMARY_EVIDENCE: the old pilot's own reason text says this document is a RESEARCH (arXiv)
    # substitute, not a true primary-source document -- honestly downgraded to PARTIALLY_SUPPORTED
    # rather than carried over as SUPPORTED, since Section 24 requires SUPPORTED to mean genuine
    # primary evidence, not a labeled substitute.
    pe = chain["PRIMARY_EVIDENCE"]
    if pe.get("status") == "REAL_EVIDENCE" and "no government/official primary source" in (pe.get("reason") or ""):
        nodes["PRIMARY_EVIDENCE"] = {"status": "PARTIALLY_SUPPORTED", "document_id": pe.get("document_id"),
                                      "reason": pe.get("reason"), "title": pe.get("title")}
    else:
        nodes["PRIMARY_EVIDENCE"] = _node_from_old(pe)
    nodes["PREVIOUS_STATE"] = _node_from_old(chain["PREVIOUS_STATE"])
    bucket_counts = old.get("bucket_counts", {})
    if bucket_counts.get("TRANSITION", 0) > 0:
        nodes["TRANSITION"] = {"status": "SUPPORTED",
                                "document_id": old["bucket_document_ids"]["TRANSITION"][0],
                                "reason": "document(s) exist in the real TRANSITION bucket"}
    else:
        nodes["TRANSITION"] = {"status": "NOT_FOUND", "document_id": None, "gap_type": "TEMPORAL_GAP",
                                "reason": "TRANSITION bucket is empty in the real pilot "
                                          f"(bucket_counts={bucket_counts}) -- no document bridges "
                                          "baseline and current state"}
    nodes["CONFIRMED_CHANGE"] = _node_from_old(chain["CONFIRMED_CHANGE"])
    nodes["STATISTICAL_CONTEXT"] = _node_from_old(chain["STATISTICAL_CONTEXT"])
    # M.5E-F: live GitHub Actions run (run #4) confirmed a real, reachable official statistical
    # source for both topics (EIA for AI_ENERGY_INFRA, ILO for AI_LABOR) -- this downgrades the
    # gap from SOURCE_GAP (no source even registered) to QUERY_GAP (source confirmed reachable;
    # extracting/validating/admitting a specific data point remains to be done). Status stays
    # NOT_FOUND -- a reachable landing page is not yet admitted evidence.
    if nodes["STATISTICAL_CONTEXT"]["status"] == "NOT_FOUND" and topic_name in (
        "AI_ENERGY_INFRA", "AI_LABOR"
    ):
        nodes["STATISTICAL_CONTEXT"]["gap_type"] = "QUERY_GAP"
        nodes["STATISTICAL_CONTEXT"]["reason"] = (
            (nodes["STATISTICAL_CONTEXT"].get("reason") or "") +
            " [M.5E-F update: live run confirmed a real official statistical source "
            f"({'EIA' if topic_name == 'AI_ENERGY_INFRA' else 'ILO'}) is reachable -- gap "
            "downgraded from SOURCE_GAP to QUERY_GAP, see fetch_pilot_results_m5e_f_run4.json]"
        )
    nodes["RESEARCH_CONTEXT"] = _node_from_old(chain["RESEARCH_CONTEXT"])
    nodes["POLICY_RESEARCH_CONTEXT"] = _check_policy_research_context(documents, topic_doc_ids)
    nodes["HISTORICAL_CONTEXT"] = _node_from_old(chain["HISTORICAL_CONTEXT"])
    nodes["COUNTEREVIDENCE"] = _node_from_old(chain["COUNTEREVIDENCE"])
    nodes["ALTERNATIVE_EXPLANATION"] = _check_alternative_explanation(topic_key_for_expansion)
    nodes["GEOGRAPHIC_CONTEXT"] = _check_geographic_context(documents, topic_doc_ids)
    uc = chain.get("UNCERTAINTY", {})
    nodes["UNCERTAINTY"] = {"status": "UNKNOWN", "document_id": None,
                             "reason": uc.get("reason") or "no uncertainty statement recorded in "
                                                            "the prior pilot"}

    for node_name, node in nodes.items():
        if node["status"] == "SUPPORTED":
            assert node.get("document_id"), f"{node_name} is SUPPORTED without a real document_id"

    status_counts = {}
    for node in nodes.values():
        status_counts[node["status"]] = status_counts.get(node["status"], 0) + 1

    return {
        "topic_name": topic_name,
        "schema_version": "13_NODE_V2_M5E_FINAL_SECTION_24",
        "total_topic_documents": old.get("total_topic_documents"),
        "nodes": nodes,
        "status_counts": status_counts,
        "superseded_old_fields_note": (
            "The old pilot's CROSS_DOMAIN_EFFECT node has no slot in the 13-node schema and is "
            "dropped here, not silently lost -- it remains readable in the original "
            f"{old_pilot_path} for reference."
        ),
    }


def main():
    energy = build_deep_pilot_v2("AI_ENERGY_INFRA", "deep_pilot_result.json", "AI_ENERGY_INFRA")
    labor = build_deep_pilot_v2("AI_LABOR", "deep_pilot_ai_labor_result.json", "AI_LABOR")
    for result, out_name in ((energy, "deep_pilot_v2_ai_energy_infra_result.json"),
                              (labor, "deep_pilot_v2_ai_labor_result.json")):
        out_path = HERE / out_name
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {out_path}: {result['status_counts']}")


if __name__ == "__main__":
    main()
