# M.5E-F -- Gap Closure Matrix. Assigns CLOSED/PARTIALLY_CLOSED/UNCHANGED/REFINED/BLOCKED to each
# of the 19 M.5E FINAL gap records, grounded in this round's real live GitHub Actions fetch pilot
# run (run #4, intel/source_intelligence/fetch_pilot_results_m5e_f_run4.json) and the new
# geography/research-rights/vault schema modules. No gap is merged or deleted; closures require a
# real evidence reference, never asserted from narrative alone.
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
OUT_PATH = HERE / "gap_closure_matrix_result.json"

_CLOSURE = {
    "gap_ai_energy_infra_transition_001": {
        "status": "UNCHANGED",
        "reason": "no live longitudinal (BASELINE->TRANSITION->CURRENT) chain was established "
                  "this round -- this round's live acquisition targeted source reachability, not "
                  "a specific transition event sequence",
    },
    "gap_ai_energy_infra_confirmed_change_002": {
        "status": "UNCHANGED", "reason": "same as TRANSITION -- no new bridging document found",
    },
    "gap_ai_energy_infra_statistical_context_003": {
        "status": "PARTIALLY_CLOSED",
        "reason": "live GitHub Actions run (run #4, job 110184162407) confirmed "
                  "https://www.eia.gov/electricity/data.php is REAL, LIVE, and REACHABLE "
                  "(HTTP 200, 4992 chars real text, 2 real primary-candidate outbound links) -- "
                  "this closes the prior SOURCE_GAP's 'no statistical source even registered' "
                  "finding. NOT fully closed: no specific data point was extracted/validated/"
                  "admitted through the real admission gate this round, so STATISTICAL_CONTEXT "
                  "stays NOT_FOUND in deep_pilot_v2, with gap_type downgraded from SOURCE_GAP to "
                  "QUERY_GAP (source now confirmed reachable; the search/extraction/admission "
                  "steps remain to be done)",
        "evidence_reference": "fetch_pilot_results_m5e_f_run4.json#eia.gov entry",
    },
    "gap_ai_energy_infra_policy_research_context_004": {
        "status": "BLOCKED",
        "reason": "live run confirmed KDI publication-list page reachable but extraction too "
                  "short (likely JS-rendered), KEEI's guessed path 404'd -- real attempts made, "
                  "real negative result, not merely unattempted",
        "evidence_reference": "fetch_pilot_results_m5e_f_run4.json#kdi.re.kr, keei.re.kr entries",
    },
    "gap_ai_energy_infra_historical_context_005": {
        "status": "UNCHANGED", "reason": "not targeted this round",
    },
    "gap_ai_energy_infra_counterevidence_006": {
        "status": "UNCHANGED",
        "reason": "Section 28's hypothesis-first counterevidence search was not executed live "
                  "this round -- this round's scope was source reachability for the "
                  "POLICY_RESEARCH/STATISTICAL blockers specifically",
    },
    "gap_ai_energy_infra_alternative_explanation_007": {
        "status": "UNCHANGED", "reason": "not executed live this round",
    },
    "gap_ai_energy_infra_geographic_context_008": {
        "status": "REFINED",
        "reason": "geography_model.py now provides a real, additive publisher_country/"
                  "event_country/jurisdiction/affected_region schema (175/601 documents have a "
                  "verified publisher_country) -- the measurement capability now exists. Status "
                  "stays NOT_FOUND/GEOGRAPHIC_GAP for event_country specifically: 0/601 documents "
                  "have a confirmed event_country, honestly, since no inference from publisher/"
                  "language is permitted",
        "evidence_reference": "intel/geography/document_geography.json",
    },
    "gap_ai_labor_primary_evidence_009": {
        "status": "UNCHANGED", "reason": "not targeted this round",
    },
    "gap_ai_labor_previous_state_010": {"status": "UNCHANGED", "reason": "not targeted this round"},
    "gap_ai_labor_transition_011": {"status": "UNCHANGED", "reason": "not targeted this round"},
    "gap_ai_labor_confirmed_change_012": {"status": "UNCHANGED", "reason": "not targeted this round"},
    "gap_ai_labor_statistical_context_013": {
        "status": "PARTIALLY_CLOSED",
        "reason": "live run confirmed https://www.ilo.org/global/statistics-and-databases "
                  "(redirected to ilo.org/data-and-statistics) is REAL, LIVE, and REACHABLE "
                  "(HTTP 200, 1231 chars real text) -- closes the prior 'no statistical source "
                  "registered' finding for AI_LABOR. NOT fully closed: landing page only, no "
                  "specific labor statistic extracted or admitted",
        "evidence_reference": "fetch_pilot_results_m5e_f_run4.json#ilo.org entry",
    },
    "gap_ai_labor_research_context_014": {
        "status": "REFINED",
        "reason": "live run confirmed RISS (https://www.riss.kr/index.do) is reachable with real "
                  "text and 4 real primary-candidate links -- the academic-research acquisition "
                  "path is now confirmed viable for Korean research, but actual paper search "
                  "requires a POST/session this pilot does not perform, so no specific paper was "
                  "obtained this round",
        "evidence_reference": "fetch_pilot_results_m5e_f_run4.json#riss.kr entry",
    },
    "gap_ai_labor_policy_research_context_015": {
        "status": "BLOCKED",
        "reason": "KISDI's guessed research-list path 404'd; STEPI's report-list path returned "
                  "real text but it was a generic download-notice page, not an actual labor "
                  "policy research report -- real attempt, real negative result",
        "evidence_reference": "fetch_pilot_results_m5e_f_run4.json#kisdi.re.kr, stepi.re.kr entries",
    },
    "gap_ai_labor_historical_context_016": {"status": "UNCHANGED", "reason": "not targeted this round"},
    "gap_ai_labor_counterevidence_017": {"status": "UNCHANGED", "reason": "not executed live this round"},
    "gap_ai_labor_alternative_explanation_018": {"status": "UNCHANGED", "reason": "not executed live this round"},
    "gap_ai_labor_geographic_context_019": {
        "status": "REFINED",
        "reason": "same geography_model.py schema extension as gap 008 -- measurement capability "
                  "now exists, event_country remains honestly 0/601 confirmed",
        "evidence_reference": "intel/geography/document_geography.json",
    },
}

_VALID_STATUSES = {"CLOSED", "PARTIALLY_CLOSED", "UNCHANGED", "REFINED", "BLOCKED"}


def build_gap_closure_matrix():
    gap_records = json.loads((INTEL_DIR / "evidence_network" / "gap_records_result.json").read_text(encoding="utf-8"))
    gap_ids = {r["gap_id"] for r in gap_records}
    assert gap_ids == set(_CLOSURE.keys()), (
        f"closure matrix must cover exactly the 19 real gap_ids, no merging/dropping: "
        f"missing={gap_ids - set(_CLOSURE.keys())} extra={set(_CLOSURE.keys()) - gap_ids}"
    )
    for gap_id, closure in _CLOSURE.items():
        assert closure["status"] in _VALID_STATUSES, f"{gap_id} has invalid status {closure['status']!r}"

    counts = {}
    for closure in _CLOSURE.values():
        counts[closure["status"]] = counts.get(closure["status"], 0) + 1

    return {
        "note": "M.5E-F Gap Closure Matrix. All 19 M.5E FINAL gaps preserved (none merged/"
                "deleted). Every CLOSED/PARTIALLY_CLOSED/REFINED entry carries a real evidence "
                "reference to this round's live GitHub Actions run or new schema module.",
        "total_gaps": len(_CLOSURE),
        "status_counts": counts,
        "closures": _CLOSURE,
    }


def main():
    matrix = build_gap_closure_matrix()
    OUT_PATH.write_text(json.dumps(matrix, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH}: {matrix['status_counts']}")


if __name__ == "__main__":
    main()
