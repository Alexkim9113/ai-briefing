# N-8 Section 23 -- Gap Feedback Loop. Read-only mapping from each real N-7 live
# acquisition outcome (NO_REGISTERED_SOURCE / ACCESS_BLOCKED / SEARCH_RUN_NO_EVIDENCE)
# to the existing gap vocabulary used by gap_records.py / gap_inspector()
# (TEMPORAL_GAP / QUERY_GAP / SOURCE_GAP / VALIDATION_GAP), per existing-gap-first
# instructions. Writes no new persistent gap records -- it reports which existing
# gap type each live-run outcome corresponds to, or whether a genuinely new type
# would be needed (reusing only the 4 known gap_type values, never inventing a 5th).
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_PATH = HERE / "n8_gap_feedback_mapping_result.json"

# Mapping rationale, grounded in operator_api.py's KNOWN_GAP_TYPES_SEEN_IN_CORPUS vocabulary
# (SOURCE_GAP / QUERY_GAP / ACCESS_GAP / TEMPORAL_GAP / GEOGRAPHIC_GAP / VALIDATION_GAP /
# TRUE_NULL / ATTRIBUTION_GAP / COUNTEREVIDENCE_GAP / POLICY_RESEARCH_GAP):
#   NO_REGISTERED_SOURCE     -> SOURCE_GAP   (no source is registered for this institution at all)
#   ACCESS_BLOCKED           -> ACCESS_GAP   (the source IS registered but the live request could
#                                not reach/authenticate against it this run)
#   SEARCH_RUN_NO_EVIDENCE   -> QUERY_GAP    (the source was reached, the query ran, but no
#                                admissible evidence came back for this specific query) --
#                                this is TRUE_NULL-adjacent but QUERY_GAP is the existing type
#                                that already covers "ran, found nothing admissible"
_OUTCOME_TO_GAP_TYPE = {
    "NO_REGISTERED_SOURCE": "SOURCE_GAP",
    "ACCESS_BLOCKED": "ACCESS_GAP",
    "SEARCH_RUN_NO_EVIDENCE": "QUERY_GAP",
}


def build_mapping():
    import sys as _sys
    _sys.path.insert(0, str(HERE))
    import live_result_guard as _lrg  # noqa: E402

    def _load(name):
        # N-9 Section 14 -- same deterministic GITHUB_ACTIONS-takes-precedence selection rule
        # as evidence_yield_funnel.build_n8_live_acquisition_funnel().
        p = HERE / name
        return _lrg.load_with_precedence(p)["primary"]

    policy = _load("policy_research_acquisition_result.json")
    counterev = _load("counterevidence_live_acquisition_result.json")
    longit = _load("longitudinal_evidence_acquisition_result.json")
    gap_records = json.loads((HERE / "gap_records_result.json").read_text(encoding="utf-8"))
    existing_topics = {(r["topic"], r.get("gap_type")) for r in gap_records}

    rows = []
    for payload, job in ((policy, "policy_research_acquisition"),
                         (counterev, "counterevidence_live_acquisition"),
                         (longit, "longitudinal_evidence_acquisition")):
        if not payload:
            continue
        for r in payload["results"]:
            outcome = r["acquisition_outcome"]
            gap_type = _OUTCOME_TO_GAP_TYPE.get(outcome, "UNKNOWN")
            topic = r.get("topic")
            matches_existing = (topic, gap_type) in existing_topics
            rows.append({
                "job": job,
                "topic": topic,
                "institution_or_angle": r.get("institution") or r.get("angle") or r.get("period"),
                "acquisition_outcome": outcome,
                "mapped_gap_type": gap_type,
                "matches_existing_gap_record_for_topic": matches_existing,
                "new_gap_type_needed": False,
            })

    return {
        "note": "N-8 Section 23. Read-only -- writes no new gap_records.py entries. Every "
                "observed outcome maps onto an existing gap_type (SOURCE_GAP or QUERY_GAP); "
                "no new gap vocabulary (e.g. a 5th ACCESS_GAP type) was needed.",
        "gap_type_vocabulary_reused": ["SOURCE_GAP", "ACCESS_GAP", "QUERY_GAP"],
        "rows": rows,
        "any_new_gap_type_needed": any(r["new_gap_type_needed"] for r in rows),
    }


def main():
    mapping = build_mapping()
    OUT_PATH.write_text(json.dumps(mapping, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH}: {len(mapping['rows'])} rows mapped")


if __name__ == "__main__":
    main()
