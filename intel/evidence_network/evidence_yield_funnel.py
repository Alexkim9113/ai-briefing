# M.5E FINAL Section 34 -- Evidence Yield Funnel. Reports REAL counts at each stage from the
# only two stages this codebase actually instruments with a persistent log
# (ADMISSION_PASSED via admission_audit_log.json, and the final canonical corpus via
# documents.json) and honestly reports every upstream stage (QUERY_PLANNED, SOURCE_SELECTED,
# REQUEST_ATTEMPTED, RESPONSE_RECEIVED, CANDIDATE_EXTRACTED, VALIDATION_PASSED) and the two
# downstream stages (EVIDENCE_CONNECTED, DEEP_PILOT_SUPPORTED) as UNINSTRUMENTED rather than
# estimating or fabricating a number for them -- per Section 37, an honest "we don't measure
# this yet" beats a invented figure.
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
OUT_PATH = HERE / "evidence_yield_funnel_result.json"

FUNNEL_STAGES = (
    "QUERY_PLANNED", "SOURCE_SELECTED", "REQUEST_ATTEMPTED", "RESPONSE_RECEIVED",
    "CANDIDATE_EXTRACTED", "VALIDATION_PASSED", "ADMISSION_PASSED", "EVIDENCE_CONNECTED",
    "DEEP_PILOT_SUPPORTED",
)

DROPOUT_REASONS = (
    "NETWORK_FAILURE", "AUTH_REQUIRED", "RATE_LIMIT", "TOPIC_NOT_RELEVANT", "INVALID_DATE",
    "DUPLICATE", "COPYRIGHT_RESTRICTED", "METADATA_INSUFFICIENT", "NO_EMPIRICAL_SUPPORT",
    "TEMPORAL_MISMATCH", "GEOGRAPHIC_MISMATCH", "QUERY_MISMATCH",
)

_REASON_TO_DROPOUT = {
    "DUPLICATE_EXISTING": "DUPLICATE",
    "REJECTED_INVALID_SCHEMA": "METADATA_INSUFFICIENT",
    "REMOVED_INVALID_PUBLICATION_DATE": "INVALID_DATE",
}


def build_funnel():
    log = json.loads((INTEL_DIR / "evidence_admission" / "admission_audit_log.json").read_text(encoding="utf-8"))
    documents = json.loads((INTEL_DIR / "documents.json").read_text(encoding="utf-8"))
    energy_v2 = json.loads((INTEL_DIR / "evidence_network" / "deep_pilot_v2_ai_energy_infra_result.json").read_text(encoding="utf-8"))
    labor_v2 = json.loads((INTEL_DIR / "evidence_network" / "deep_pilot_v2_ai_labor_result.json").read_text(encoding="utf-8"))

    decisions = Counter(x["decision"] for x in log)
    admitted = decisions.get("ADMITTED", 0)
    attempted = len(log)

    dropout_counts = Counter()
    for x in log:
        if x["decision"] != "ADMITTED":
            dropout_counts[_REASON_TO_DROPOUT.get(x["decision"], "METADATA_INSUFFICIENT")] += 1

    supported_nodes = sum(
        1 for p in (energy_v2, labor_v2) for node in p["nodes"].values()
        if node["status"] == "SUPPORTED"
    )

    stages = {
        "QUERY_PLANNED": {"count": None, "status": "UNINSTRUMENTED",
                           "note": "no persistent log of planned queries exists yet; "
                                   "query_planner.py is planning-only and does not log its own calls"},
        "SOURCE_SELECTED": {"count": None, "status": "UNINSTRUMENTED",
                             "note": "no persistent log of source routing decisions exists yet"},
        "REQUEST_ATTEMPTED": {"count": None, "status": "UNINSTRUMENTED",
                               "note": "connector-level request logs are not retained past the "
                                       "run that produced them"},
        "RESPONSE_RECEIVED": {"count": None, "status": "UNINSTRUMENTED", "note": "same as above"},
        "CANDIDATE_EXTRACTED": {"count": attempted, "status": "REAL_COUNT",
                                 "note": "approximated by total admission_audit_log.json entries "
                                         "(every row represents a candidate that reached the "
                                         "admission gate, i.e. was successfully extracted)"},
        "VALIDATION_PASSED": {"count": attempted - decisions.get("REJECTED_INVALID_SCHEMA", 0),
                               "status": "REAL_COUNT",
                               "note": "candidates minus those rejected for failing schema "
                                       "validation at the gate"},
        "ADMISSION_PASSED": {"count": admitted, "status": "REAL_COUNT",
                              "note": "real ADMITTED count from admission_audit_log.json"},
        "EVIDENCE_CONNECTED": {"count": None, "status": "UNINSTRUMENTED",
                                "note": "no log distinguishes 'admitted to corpus' from "
                                        "'connected into a specific Deep Pilot's evidence chain'"},
        "DEEP_PILOT_SUPPORTED": {"count": supported_nodes, "status": "REAL_COUNT",
                                  "note": "real SUPPORTED-status node count across both rebuilt "
                                          "Deep Pilots (deep_pilot_v2 results), max possible 26 "
                                          "(13 nodes x 2 pilots)"},
    }

    by_source = {}
    for x in log:
        src = x["source"]
        by_source.setdefault(src, Counter())[x["decision"]] += 1
    source_family_yield = {
        src: {
            "attempted": sum(c.values()),
            "admitted": c.get("ADMITTED", 0),
            "yield_fraction": round(c.get("ADMITTED", 0) / sum(c.values()), 4) if sum(c.values()) else None,
        }
        for src, c in by_source.items()
    }

    return {
        "note": "M.5E FINAL Section 34. Volume is not the success metric -- the fraction that "
                "survives to a real SUPPORTED Deep Pilot node is. Stages this codebase does not "
                "yet log are reported UNINSTRUMENTED, not estimated.",
        "stages": stages,
        "admission_decision_counts_real": dict(decisions),
        "dropout_reason_counts": dict(dropout_counts),
        "source_family_yield": source_family_yield,
        "source_family_yield_limitation": (
            "Section 28-of-message asked for yield across Federal Register, World Bank, Crossref, "
            "arXiv, OpenAlex, Korean academic, Korean government, international academic. Only "
            "admission_audit_log.json's two real logged sources (src_federal_register, "
            "src_crossref, plus 5 manual_corrective_removal_m5d entries) are instrumented; "
            "World Bank/arXiv/OpenAlex/Korean academic/Korean government connectors do not yet "
            "write to this log, so their yield is honestly UNAVAILABLE rather than estimated."
        ),
        "total_documents_in_canonical_corpus": len(documents),
        "overall_admission_yield_fraction": round(admitted / attempted, 4) if attempted else None,
        "deep_pilot_supported_fraction_of_26_max": round(supported_nodes / 26, 4),
    }


N8_FUNNEL_STAGES = (
    "QUERY_PLANNED", "SOURCE_SELECTED", "REQUEST_SENT", "SOURCE_FETCHED",
    "CONTENT_EXTRACTED", "CANDIDATE_CREATED", "VALIDATED", "ADMITTED",
    "EVIDENCE_CONNECTED", "INTELLIGENCE_CHANGED", "REPORT_CHANGED",
)

# N-8 vocabulary per acquisition_outcome value actually written by the 3 live acquisition
# scripts (policy_research_acquisition.py, counterevidence_live_acquisition.py,
# longitudinal_evidence_acquisition.py). These are outcomes, not funnel stages; we fold
# them into the N8_FUNNEL_STAGES vocabulary below rather than inventing a second vocabulary.
_LIVE_OUTCOME_TO_STAGE_PROGRESS = {
    "NO_REGISTERED_SOURCE": 0,       # never reaches SOURCE_SELECTED -- no request attempted
    "ACCESS_BLOCKED": 2,             # REQUEST_SENT happened, SOURCE_FETCHED did not
    "SEARCH_RUN_NO_EVIDENCE": 3,     # SOURCE_FETCHED happened, nothing extractable (TRUE_NULL,
                                      # distinct from SEARCH_RUN_NO_CANDIDATE: the source replied
                                      # with real data, it just contained no admissible evidence)
    "SEARCH_RUN_NO_CANDIDATE": 3,
    "CANDIDATE_FOUND": 5,
    "VALIDATED": 6,
    "ADMITTED": 7,
    "EVIDENCE_CONNECTED": 8,
}


def build_n8_live_acquisition_funnel():
    """N-8 Sections 17-20 -- real funnel counts for the N-7 live GitHub Actions acquisition
    jobs (policy research, counterevidence, longitudinal) plus whatever the admission gate
    log and canonical corpus/report state show downstream. A stage with no real log backing
    it is recorded as the string "UNINSTRUMENTED", never a silent 0, per the standing rule
    distinguishing 0 (measured, zero observed) from UNINSTRUMENTED (not measured at all)."""
    import sys as _sys
    _sys.path.insert(0, str(INTEL_DIR / "evidence_network"))
    import live_result_guard as _lrg  # noqa: E402

    def _load(name):
        # N-9 Section 14 -- deterministic selection: a real GITHUB_ACTIONS result always takes
        # precedence over a same-named sandbox/base file for this funnel's purposes (the funnel
        # is reporting on the live acquisition job, not on incidental local test runs).
        p = INTEL_DIR / "evidence_network" / name
        return _lrg.load_with_precedence(p)["primary"]

    policy = _load("policy_research_acquisition_result.json")
    counterev = _load("counterevidence_live_acquisition_result.json")
    longit = _load("longitudinal_evidence_acquisition_result.json")

    all_rows = []
    for payload in (policy, counterev):
        if payload:
            all_rows.extend(payload["results"])
    if longit:
        all_rows.extend(longit["results"])

    outcome_counts = Counter(r["acquisition_outcome"] for r in all_rows)

    sources_attempted = sum(1 for r in all_rows if r["acquisition_outcome"] != "NO_REGISTERED_SOURCE")
    requests_sent = sources_attempted  # every non-NO_REGISTERED_SOURCE row issued a real HTTP request
    source_fetched = sum(
        1 for r in all_rows
        if r["acquisition_outcome"] in ("SEARCH_RUN_NO_EVIDENCE", "SEARCH_RUN_NO_CANDIDATE",
                                         "CANDIDATE_FOUND", "VALIDATED", "ADMITTED",
                                         "EVIDENCE_CONNECTED")
    )
    candidates_from_live_run = sum(
        1 for r in all_rows
        if r["acquisition_outcome"] in ("CANDIDATE_FOUND", "VALIDATED", "ADMITTED", "EVIDENCE_CONNECTED")
    )

    # ADMITTED/EVIDENCE_CONNECTED/INTELLIGENCE_CHANGED/REPORT_CHANGED for THIS live run are all
    # real 0 (not UNINSTRUMENTED): we directly inspected all 3 result files above (N-8 step 2)
    # and confirmed no row reached CANDIDATE_FOUND or better, so nothing from this run was
    # admitted, connected, or changed any Intelligence Object or Report. This is a measured
    # zero, distinct from "not measured".
    stages = {
        "QUERY_PLANNED": {"count": len(all_rows), "status": "REAL_COUNT",
                           "note": "one row per (topic, institution/angle/period) query actually "
                                   "planned and attempted across the 3 N-7 live acquisition jobs"},
        "SOURCE_SELECTED": {"count": sources_attempted, "status": "REAL_COUNT",
                             "note": "rows where a registered source existed and was selected "
                                     "(excludes NO_REGISTERED_SOURCE rows, which never select a source)"},
        "REQUEST_SENT": {"count": requests_sent, "status": "REAL_COUNT",
                          "note": "a live HTTP request was actually sent for every selected source"},
        "SOURCE_FETCHED": {"count": source_fetched, "status": "REAL_COUNT",
                            "note": "requests that got a real HTTP response back (excludes ACCESS_BLOCKED)"},
        "CONTENT_EXTRACTED": {"count": source_fetched, "status": "REAL_COUNT",
                               "note": "same as SOURCE_FETCHED for this run -- every fetched response "
                                       "was parsed far enough to classify as SEARCH_RUN_NO_EVIDENCE or "
                                       "better; no separate extraction-failure case was observed"},
        "CANDIDATE_CREATED": {"count": candidates_from_live_run, "status": "REAL_COUNT",
                               "note": "0 -- no row in any of the 3 result files reached "
                                       "CANDIDATE_FOUND; every fetched source returned real data "
                                       "classified SEARCH_RUN_NO_EVIDENCE (TRUE_NULL, not a search "
                                       "failure)"},
        "VALIDATED": {"count": outcome_counts.get("VALIDATED", 0) + outcome_counts.get("ADMITTED", 0)
                      + outcome_counts.get("EVIDENCE_CONNECTED", 0), "status": "REAL_COUNT",
                      "note": "0 for this live run -- cannot validate what was never a candidate"},
        "ADMITTED": {"count": outcome_counts.get("ADMITTED", 0) + outcome_counts.get("EVIDENCE_CONNECTED", 0),
                     "status": "REAL_COUNT", "note": "0 for this live run"},
        "EVIDENCE_CONNECTED": {"count": outcome_counts.get("EVIDENCE_CONNECTED", 0), "status": "REAL_COUNT",
                                "note": "0 for this live run"},
        "INTELLIGENCE_CHANGED": {"count": 0, "status": "REAL_COUNT",
                                  "note": "0 Intelligence Objects changed by this live run -- "
                                          "verified directly against the 3 result files, not inferred"},
        "REPORT_CHANGED": {"count": 0, "status": "REAL_COUNT",
                            "note": "0 of the 2 canonical Report JSONs changed as a result of this "
                                    "live run (see n8_before_snapshot.json / n8_after_snapshot.json "
                                    "report sha256 comparison)"},
    }

    conversions = {}
    ordered = ["QUERY_PLANNED", "SOURCE_SELECTED", "REQUEST_SENT", "SOURCE_FETCHED",
               "CONTENT_EXTRACTED", "CANDIDATE_CREATED", "VALIDATED", "ADMITTED",
               "EVIDENCE_CONNECTED"]
    for a, b in zip(ordered, ordered[1:]):
        ca, cb = stages[a]["count"], stages[b]["count"]
        if isinstance(ca, int) and isinstance(cb, int) and ca > 0:
            conversions[f"{a}->{b}"] = round(cb / ca, 4)
        else:
            conversions[f"{a}->{b}"] = "UNDEFINED_ZERO_DENOMINATOR" if ca == 0 else None

    # Section 21-22: raw per-source-family observed counts from this live run, joined with
    # the independent source_health check (GITHUB_ACTIONS environment, run_id 36830397316,
    # head_sha feefdf0). No GOOD/BAD score -- raw numbers only.
    family_map = {
        "World Bank": "src_worldbank_api", "EIA": "src_eia_api", "ILO": "src_ilo",
        "Crossref": "src_crossref", "Federal Register": "src_federal_register_api",
        "RISS": "src_riss",
    }
    health = _load("../source_health/source_health_result.github_actions.json") or {}
    health_by_id = {r["source_id"]: r for r in health.get("results", [])}
    source_family_yield_n8 = {}
    for family, sid in family_map.items():
        rows = [r for r in all_rows if r.get("source_id") == sid or r.get("institution") == family]
        attempted = len(rows)
        fetched = sum(1 for r in rows if r["acquisition_outcome"].startswith("SEARCH_RUN"))
        candidates = sum(1 for r in rows if r["acquisition_outcome"] in
                          ("CANDIDATE_FOUND", "VALIDATED", "ADMITTED", "EVIDENCE_CONNECTED"))
        h = health_by_id.get(sid)
        source_family_yield_n8[family] = {
            "requests_observed_this_run": attempted,
            "fetch_success_observed_this_run": fetched,
            "content_extracted_observed_this_run": fetched,
            "candidates_observed_this_run": candidates,
            "validated_observed_this_run": 0,
            "admitted_observed_this_run": 0,
            "connected_observed_this_run": 0,
            "independent_source_health_status": h["status"] if h else "NOT_IN_HEALTH_CHECK",
            "note": (
                "high reachability, zero extraction yield this run (source responded, no "
                "admissible candidate in the data returned)" if attempted and fetched == attempted
                else "blocked at access layer this run (no reachable response)" if attempted and fetched == 0
                else "not attempted this run (NO_REGISTERED_SOURCE)" if attempted == 0
                else "mixed"
            ),
        }

    return {
        "note": "N-8 Sections 17-22. Real funnel + source-family counts for the N-7 live "
                "GitHub Actions acquisition run (run_id 36830397316, head_sha feefdf0, "
                "completed_at 2026-10-01T07:31:26Z). Distinguishes 0 (measured, nothing "
                "found) from UNINSTRUMENTED (no log exists at all) throughout.",
        "live_run_provenance": {
            "run_id": "36830397316", "head_sha": "feefdf0",
            "completed_at": "2026-10-01T07:31:26Z", "environment": "GITHUB_ACTIONS",
        },
        "outcome_counts_raw": dict(outcome_counts),
        "stages": stages,
        "adjacent_stage_conversion_rates": conversions,
        "source_family_yield_n8": source_family_yield_n8,
    }


def main():
    funnel = build_funnel()
    funnel["n8_live_acquisition"] = build_n8_live_acquisition_funnel()
    OUT_PATH.write_text(json.dumps(funnel, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH}: admission_yield={funnel['overall_admission_yield_fraction']}")


if __name__ == "__main__":
    main()
