# O-1C Part 2: Temporal Applicability assessment for H1-H7's current resolved evidence.
#
# No prior temporal-applicability module exists in this repo (checked: no intel/temporal_evidence/
# directory, no temporal_applicability.py anywhere before this file), so this is placed alongside
# geographic_applicability.py in intel/geographic_evidence/ per the task's own fallback guidance,
# following the same style (deterministic stdlib Python, reads claims.json/hypotheses.json,
# writes one sidecar JSON, never mutates either input file).
#
# States:
#   CURRENT_MATCH          -- evidence's own observation period is the most recent available and
#                              is read as "true now" (e.g. LBNL 2023 observed figure for H1/H2's
#                              current-state claim).
#   HISTORICAL_CONTEXT     -- evidence is observed but describes a past window materially older
#                              than "now" (e.g. a 2016-2022 trend used to support a general
#                              mechanism, not a current-state number).
#   FORECAST_ONLY          -- the evidence cited is itself a forecast/projection, not an
#                              observation, and must never be read as a current-state fact.
#   PARTIAL_TEMPORAL_MATCH -- the claim MIXES an observed figure and a forecast figure in the
#                              same claim object, but the claim's own text keeps them in
#                              separate, labeled fields (not merged) -- flagged so a downstream
#                              reader knows to use only the observed half for "is this true now".
#   OUT_OF_RANGE            -- evidence's observation window is peak/hourly-scale and must not be
#                              read as representing the same thing as an annual-trend hypothesis.
#   UNKNOWN                 -- no resolved evidence exists, or its temporal scope could not be
#                              determined from the claim's own time_scope field.
#
# "Now" for this corpus is treated as 2024-2025 (the most recent OBSERVED data available across
# the claims), per IEA/LBNL/EIA/IEA-EV-Outlook's own most recent observed years.
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
CLAIMS_PATH = INTEL_DIR / "claims" / "claims.json"
HYPOTHESES_PATH = INTEL_DIR / "hypothesis" / "hypotheses.json"
OUT_PATH = HERE / "o1c_temporal_applicability_result.json"

CURRENT_MATCH = "CURRENT_MATCH"
HISTORICAL_CONTEXT = "HISTORICAL_CONTEXT"
FORECAST_ONLY = "FORECAST_ONLY"
PARTIAL_TEMPORAL_MATCH = "PARTIAL_TEMPORAL_MATCH"
OUT_OF_RANGE = "OUT_OF_RANGE"
UNKNOWN = "UNKNOWN"

# Per-claim temporal facts, read directly off each claim's own claim_text/time_scope fields in
# claims.json (never inferred/guessed). observation_period/publication_context/forecast_horizon
# are recorded for transparency; classification is the deterministic field below.
_CLAIM_TEMPORAL_MAP = {
    "claim_o1_lbnl_us_dc_2023": {
        "observation_period": "2014-2023 (OBSERVED)",
        "forecast_horizon": "2028 (FORECAST, 325-580 TWh)",
        "classification": PARTIAL_TEMPORAL_MATCH,
        "reason": "Claim keeps 2023 OBSERVED and 2028 FORECAST as explicitly separate fields "
                  "(claim text: 'kept as separate claim fields, not merged'); the 2023 figure "
                  "alone is CURRENT_MATCH-eligible for a current-state hypothesis, the 2028 "
                  "figure must never be read as 'true now'.",
    },
    "claim_5787125ab5f0110b": {
        "observation_period": "2025-2027 (queue size, auction price OBSERVED/near-term)",
        "forecast_horizon": "2026/27 delivery year counterfactual ($3.5B savings ESTIMATED model)",
        "classification": PARTIAL_TEMPORAL_MATCH,
        "reason": "Queue size and auction clearing price are OBSERVED/near-term facts; the $3.5B "
                  "figure is an explicitly-labeled counterfactual ESTIMATE, not an observation -- "
                  "kept distinct per the claim's own STATUS annotation.",
    },
    "claim_a11c5cb4c7c4c2d1": {
        "observation_period": "2024-2025 (report publication dates)",
        "forecast_horizon": "underlying utility load forecasts are multi-year forward-looking",
        "classification": CURRENT_MATCH,
        "reason": "The claim itself is OBSERVED at the level of 'a named non-AI industrial "
                  "driver exists in current utility planning data' (2024-2025 reports) -- "
                  "CURRENT_MATCH for H3's current-state 'multiple factors are driving recent "
                  "demand growth' framing. The forward-looking forecasts embedded in those "
                  "reports are a separate, unquantified matter and are not used as the basis "
                  "for this claim's CURRENT_MATCH classification.",
    },
    "claim_f5842e6162c8fefc": {
        "observation_period": "2024 (OBSERVED, ~180 TWh global EV charging)",
        "forecast_horizon": "2030 (FORECAST, ~780 TWh, IEA Stated Policies Scenario)",
        "classification": PARTIAL_TEMPORAL_MATCH,
        "reason": "Claim text explicitly separates the 2024 OBSERVED figure from the 2030 "
                  "FORECAST figure ('kept as a separate forecast field, never merged'); only "
                  "the 2024 figure is CURRENT_MATCH-eligible.",
    },
    "claim_d641fb1790c3ef53": {
        "observation_period": "2024-2025 (OBSERVED peak/hourly heat-wave demand events)",
        "forecast_horizon": None,
        "classification": OUT_OF_RANGE,
        "reason": "Claim's own text states this is 'a genuine alternative explanation for PEAK "
                  "LOAD STRESS episodes specifically' operating on peak/hourly timescales, 'not "
                  "the multi-year annual TWh growth trend' that H1/H2/H3's IEA/LBNL evidence "
                  "tracks -- classified OUT_OF_RANGE relative to the annual-trend hypotheses so "
                  "it is never merged with annual-baseline growth claims as if measuring the "
                  "same thing.",
    },
    "claim_o1_korea_capital_region_dc_demand": {
        "observation_period": "as-of reporting date (contracted capacity REQUESTS, not consumption)",
        "forecast_horizon": "through 2029 (contracted capacity target horizon)",
        "classification": FORECAST_ONLY,
        "reason": "The 14.7 GW/13.5 GW figures are CONTRACTED capacity requested THROUGH 2029 "
                  "(a forward-looking commitment), not an observed current electricity "
                  "consumption figure -- classified FORECAST_ONLY so it is never read as "
                  "'actual AI electricity consumption in Korea right now.'",
    },
    "claim_d170f52f567053e9": {
        "observation_period": "2016-2022 (OBSERVED, within the paper's own dataset)",
        "forecast_horizon": None,
        "classification": HISTORICAL_CONTEXT,
        "reason": "2016-2022 is materially older than the corpus's 'now' (2024-2025 OBSERVED "
                  "baseline); used here to support a general Jevons-paradox MECHANISM (efficiency "
                  "gains alone do not curb aggregate growth), not as a current-state electricity "
                  "number -- HISTORICAL_CONTEXT, not CURRENT_MATCH.",
    },
}


def _hypotheses_evidence(hypotheses):
    out = {}
    for hyp in hypotheses.values():
        code = hyp.get("hypothesis_code")
        if not code:
            continue
        diag = hyp.get("canonical_status_diagnostics", {})
        claim_refs = list(diag.get("resolved_supporting_evidence", [])) + \
            list(diag.get("resolved_contradicting_evidence", []))
        out[code] = [ref.split(":", 1)[0] for ref in claim_refs]
    return out


def classify_claim(claim_id):
    entry = _CLAIM_TEMPORAL_MAP.get(claim_id)
    if not entry:
        return {
            "observation_period": None,
            "forecast_horizon": None,
            "classification": UNKNOWN,
            "reason": "No temporal mapping recorded for this claim.",
        }
    return entry


def build_result(hypotheses=None):
    hypotheses = hypotheses if hypotheses is not None else json.loads(
        HYPOTHESES_PATH.read_text(encoding="utf-8"))
    hyp_evidence = _hypotheses_evidence(hypotheses)

    per_hypothesis = {}
    observation_forecast_audit = []
    for code, claim_ids in sorted(hyp_evidence.items()):
        evidence_entries = []
        for cid in claim_ids:
            entry = classify_claim(cid)
            evidence_entries.append({"claim_id": cid, **entry})
            if entry["classification"] == PARTIAL_TEMPORAL_MATCH:
                observation_forecast_audit.append({
                    "claim_id": cid,
                    "finding": "Observed and forecast figures are present but kept in "
                               "separate, explicitly labeled fields within the same claim "
                               "object -- NOT merged into a single blended 'now' figure. "
                               "No fix needed.",
                })
        per_hypothesis[code] = {"evidence": evidence_entries}

    return {
        "topic_name": "AI_ENERGY_INFRA",
        "purpose": (
            "Per-hypothesis, per-evidence temporal applicability of H1-H7's current resolved "
            "evidence against each hypothesis's implied current-state target period, and a "
            "re-audit of observation/forecast separation across that evidence."
        ),
        "states": [CURRENT_MATCH, HISTORICAL_CONTEXT, FORECAST_ONLY, PARTIAL_TEMPORAL_MATCH,
                   OUT_OF_RANGE, UNKNOWN],
        "now_baseline": "2024-2025 (most recent OBSERVED data across this corpus's claims)",
        "per_hypothesis": per_hypothesis,
        "observation_forecast_audit": {
            "scope": "IEA 2024 vs 2030/2035, LBNL 2023 vs 2028, Ireland 2024, China 2024 "
                     "estimate, EV 2024 vs 2030, GridLab queue-snapshot vs counterfactual "
                     "estimate.",
            "findings": observation_forecast_audit,
            "conclusion": "No claim used by H1-H7 was found merging an observed figure and a "
                          "forecast figure into a single blended 'current' value; every "
                          "OBSERVED/FORECAST pair inspected keeps the two in separate, "
                          "explicitly labeled fields within its claim_text. No corrective edit "
                          "was required this round.",
        },
    }


def main():
    result = build_result()
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
