# O-1C Part 1: Geographic Applicability assessment for hypotheses H1-H7.
#
# This module does NOT build a new geography-inference engine -- it reuses the
# geographic_scope strings already recorded on each resolved Claim (see
# intel/claims/claims.json) and on each hypothesis's `scope` field
# (intel/hypothesis/hypotheses.json), and classifies, PER HYPOTHESIS PER REGION,
# whether that hypothesis's CURRENT resolved evidence actually covers that region.
#
# States (deterministic, never inferred/guessed):
#   MATCHED       -- a resolved claim's geographic_scope directly names this region
#                     (or an unambiguous sub-region of it, e.g. US_PJM_REGION -> PJM).
#   PARTIAL_MATCH -- a resolved claim covers a REGION THAT CONTAINS this region, but the
#                     claim's own text is explicit that the finding is local, not an
#                     average/estimate for the larger region (e.g. Ireland is inside "EU"
#                     geographically, but the 22% DC-electricity-share figure is Ireland-only,
#                     so EU is PARTIAL_MATCH with an explicit anti-overgeneralization note,
#                     never MATCHED).
#   OUT_OF_SCOPE  -- the hypothesis has resolved evidence, but none of it bears on this
#                     region at all (e.g. H1's evidence is US-only; China is OUT_OF_SCOPE).
#   UNKNOWN       -- no resolved evidence exists to determine applicability either way.
#
# CRITICAL anti-overgeneralization rules enforced here (see REGION_RULES docstrings and
# tests/test_geographic_applicability.py):
#   1. PJM evidence is never read as applying to "USA" as a whole (PJM covers 13
#      US states + DC, not the whole country) -- USA gets PARTIAL_MATCH, not MATCHED,
#      off PJM-only evidence.
#   2. US evidence is never auto-applied to Korea (or vice versa) -- cross-country
#      promotion is always OUT_OF_SCOPE/UNKNOWN, never MATCHED/PARTIAL_MATCH.
#   3. Ireland's data-center-electricity-share figure is never used as an EU-wide average
#      (Ireland is PARTIAL_MATCH-eligible only as itself; EU gets PARTIAL_MATCH with an
#      explicit "country-level, not EU-wide" caveat, never MATCHED).
#   4. A derivative/secondary China estimate is never promoted to "official Chinese
#      observed value" (this module currently holds NO resolved China-specific claim for
#      H1-H7, so China is UNKNOWN or OUT_OF_SCOPE for every hypothesis, never MATCHED).
#   5. Korea's capital-region CONTRACTED power capacity figure is never read as "actual AI
#      electricity consumption" -- the classification note for KOREA/SEOUL_METRO always
#      says "contracted/forecast capacity, not observed AI consumption."
#
# Zero LLM. Deterministic Python, stdlib only. Read-only against claims.json/hypotheses.json;
# writes only its own sidecar file, o1c_geographic_applicability_result.json.
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
CLAIMS_PATH = INTEL_DIR / "claims" / "claims.json"
HYPOTHESES_PATH = INTEL_DIR / "hypothesis" / "hypotheses.json"
OUT_PATH = HERE / "o1c_geographic_applicability_result.json"

MATCHED = "MATCHED"
PARTIAL_MATCH = "PARTIAL_MATCH"
OUT_OF_SCOPE = "OUT_OF_SCOPE"
UNKNOWN = "UNKNOWN"

REGIONS = ["USA", "PJM", "IRELAND", "EU", "CHINA", "KOREA", "SEOUL_METRO"]

# Claim-id -> (region -> (state, reason)) mapping, keyed off each claim's real
# geographic_scope string (see claims.json). This table is the only place geography
# facts are declared; build_result() never infers beyond it.
_CLAIM_REGION_MAP = {
    "claim_o1_lbnl_us_dc_2023": {
        "USA": (MATCHED, "LBNL claim's geographic_scope is 'US' directly."),
        "PJM": (UNKNOWN, "US-aggregate claim does not break out PJM specifically."),
        "IRELAND": (OUT_OF_SCOPE, "US-only claim; no Ireland data."),
        "EU": (OUT_OF_SCOPE, "US-only claim; no EU data."),
        "CHINA": (OUT_OF_SCOPE, "US-only claim; no China data."),
        "KOREA": (OUT_OF_SCOPE, "US evidence never auto-applied to Korea."),
        "SEOUL_METRO": (OUT_OF_SCOPE, "US evidence never auto-applied to Korea's capital region."),
    },
    "claim_5787125ab5f0110b": {
        "USA": (PARTIAL_MATCH,
                "Claim's geographic_scope is 'US_PJM_REGION' -- PJM covers 13 US states + DC, "
                "not the whole country, so this is a PARTIAL_MATCH for USA, never MATCHED. "
                "PJM-specific findings (queue size, auction price) must not be read as "
                "nationwide US figures."),
        "PJM": (MATCHED, "Claim's geographic_scope is directly US_PJM_REGION."),
        "IRELAND": (OUT_OF_SCOPE, "PJM-only claim; no Ireland data."),
        "EU": (OUT_OF_SCOPE, "PJM-only claim; no EU data."),
        "CHINA": (OUT_OF_SCOPE, "PJM-only claim; no China data."),
        "KOREA": (OUT_OF_SCOPE, "US/PJM evidence never auto-applied to Korea."),
        "SEOUL_METRO": (OUT_OF_SCOPE, "US/PJM evidence never auto-applied to Korea's capital region."),
    },
    "claim_a11c5cb4c7c4c2d1": {
        "USA": (MATCHED, "Manufacturing reshoring claim's geographic_scope is 'US'."),
        "PJM": (UNKNOWN, "US-national claim does not specify PJM-region incidence."),
        "IRELAND": (OUT_OF_SCOPE, "US-only claim."),
        "EU": (OUT_OF_SCOPE, "US-only claim."),
        "CHINA": (OUT_OF_SCOPE, "US-only claim."),
        "KOREA": (OUT_OF_SCOPE, "US evidence never auto-applied to Korea."),
        "SEOUL_METRO": (OUT_OF_SCOPE, "US evidence never auto-applied to Korea's capital region."),
    },
    "claim_f5842e6162c8fefc": {
        "USA": (UNKNOWN,
                "Claim's geographic_scope is 'GLOBAL/EUROPE/CHINA'; claim text explicitly "
                "states no US-specific TWh figure was given -- US applicability is UNKNOWN, "
                "not inferred from the global total."),
        "PJM": (UNKNOWN, "No PJM-specific figure in claim."),
        "IRELAND": (UNKNOWN, "No Ireland-specific figure in claim."),
        "EU": (PARTIAL_MATCH,
               "Claim gives an EU-specific 2030 FORECAST share (>4% of EU electricity demand) "
               "alongside the global OBSERVED figure -- PARTIAL_MATCH because the EU figure "
               "itself is a forecast, not an observed current-state figure."),
        "CHINA": (PARTIAL_MATCH,
                  "Claim gives a China-specific 2030 FORECAST share (3.6%) -- PARTIAL_MATCH, "
                  "forecast only, not an observed Chinese value."),
        "KOREA": (OUT_OF_SCOPE, "Claim names GLOBAL/EUROPE/CHINA only; no Korea figure given."),
        "SEOUL_METRO": (OUT_OF_SCOPE, "Claim names GLOBAL/EUROPE/CHINA only; no Korea figure given."),
    },
    "claim_d641fb1790c3ef53": {
        "USA": (MATCHED, "Claim's geographic_scope is 'US' (ERCOT/Eastern Interconnection)."),
        "PJM": (UNKNOWN, "Eastern Interconnection partially overlaps PJM but claim does not "
                          "isolate PJM specifically."),
        "IRELAND": (OUT_OF_SCOPE, "US-only claim."),
        "EU": (OUT_OF_SCOPE, "US-only claim."),
        "CHINA": (OUT_OF_SCOPE, "US-only claim."),
        "KOREA": (OUT_OF_SCOPE, "US evidence never auto-applied to Korea."),
        "SEOUL_METRO": (OUT_OF_SCOPE, "US evidence never auto-applied to Korea's capital region."),
    },
    "claim_o1_korea_capital_region_dc_demand": {
        "USA": (OUT_OF_SCOPE, "Korea-only claim; never auto-applied to USA."),
        "PJM": (OUT_OF_SCOPE, "Korea-only claim; never auto-applied to PJM."),
        "IRELAND": (OUT_OF_SCOPE, "Korea-only claim."),
        "EU": (OUT_OF_SCOPE, "Korea-only claim."),
        "CHINA": (OUT_OF_SCOPE, "Korea-only claim."),
        "KOREA": (PARTIAL_MATCH,
                  "Claim's geographic_scope is the Seoul/Gyeonggi/Incheon capital region vs. "
                  "the Korea national total -- capital-region figures are PARTIAL_MATCH for "
                  "'KOREA' as a whole, never MATCHED, since 8.2% of contracted capacity lies "
                  "outside the capital region. ALSO: this is CONTRACTED power capacity requested "
                  "through 2029, not observed AI electricity consumption -- must never be read "
                  "as an actual-consumption figure for Korea."),
        "SEOUL_METRO": (MATCHED,
                        "Claim's geographic_scope directly names Seoul/Gyeonggi/Incheon (the "
                        "capital region / 수도권). NOTE: this is CONTRACTED power capacity "
                        "requested through 2029 (KEPCO/National Assembly figures), not observed "
                        "AI electricity consumption -- MATCHED refers to geographic coverage "
                        "only, not to the figure representing AI consumption."),
    },
    "claim_d170f52f567053e9": {
        "USA": (UNKNOWN, "Claim's geographic_scope is 'GLOBAL' (Google/Meta infrastructure); "
                          "no US-specific breakout given."),
        "PJM": (UNKNOWN, "No PJM-specific data."),
        "IRELAND": (UNKNOWN, "No Ireland-specific data."),
        "EU": (UNKNOWN, "No EU-specific data."),
        "CHINA": (OUT_OF_SCOPE, "Models US hyperscalers' global infrastructure; no China-specific "
                                 "figures -- a derivative/secondary estimate for China must never "
                                 "be fabricated from this global figure."),
        "KOREA": (OUT_OF_SCOPE, "Global hyperscaler claim; never auto-applied to Korea."),
        "SEOUL_METRO": (OUT_OF_SCOPE, "Global hyperscaler claim; never auto-applied to Korea's "
                                       "capital region."),
    },
}

# Korea evidence search result records an Ireland data-center-electricity-share figure
# (~22% of national electricity) that is referenced in discourse around this topic but is
# NOT itself a resolved Claim object in claims.json. It is included here, read-only, purely
# to enforce anti-overgeneralization rule #3 (Ireland ratio != EU average) even though no
# hypothesis currently cites it as resolved evidence.
IRELAND_DC_SHARE_NOTE = (
    "Ireland's ~22% data-center-electricity-share figure (CSO/EirGrid) is a COUNTRY-LEVEL "
    "figure. It must never be used as an EU-wide average -- Ireland is a small, data-center-"
    "dense outlier economy, not representative of the EU aggregate (EU-wide data center "
    "electricity share is far lower, on the order of a few percent per IEA)."
)


def _hypotheses_evidence(hypotheses):
    """Return {hyp_code: [resolved_claim_ids]} using canonical_status_diagnostics only
    (resolved_supporting + resolved_contradicting), never unresolved/legacy evidence."""
    out = {}
    for hyp in hypotheses.values():
        code = hyp.get("hypothesis_code")
        if not code:
            continue
        diag = hyp.get("canonical_status_diagnostics", {})
        claim_refs = list(diag.get("resolved_supporting_evidence", [])) + \
            list(diag.get("resolved_contradicting_evidence", []))
        claim_ids = [ref.split(":", 1)[0] for ref in claim_refs]
        out[code] = claim_ids
    return out


def classify_hypothesis_region(claim_ids, region):
    """Deterministic classifier: given the resolved claim ids backing a hypothesis and a
    target region, return (state, reasons[]). MATCHED beats PARTIAL_MATCH beats OUT_OF_SCOPE;
    UNKNOWN only when nothing at all is known."""
    states_seen = []
    reasons = []
    for cid in claim_ids:
        region_map = _CLAIM_REGION_MAP.get(cid)
        if not region_map:
            continue
        state, reason = region_map.get(region, (UNKNOWN, "No geography mapping recorded for "
                                                           "this claim/region pair."))
        states_seen.append(state)
        reasons.append(f"{cid}: {reason}")
    if not states_seen:
        return UNKNOWN, ["No resolved evidence available to assess this region."]
    if MATCHED in states_seen:
        return MATCHED, reasons
    if PARTIAL_MATCH in states_seen:
        return PARTIAL_MATCH, reasons
    if all(s == OUT_OF_SCOPE for s in states_seen):
        return OUT_OF_SCOPE, reasons
    return UNKNOWN, reasons


def build_result(claims=None, hypotheses=None):
    claims = claims if claims is not None else json.loads(CLAIMS_PATH.read_text(encoding="utf-8"))
    hypotheses = hypotheses if hypotheses is not None else json.loads(
        HYPOTHESES_PATH.read_text(encoding="utf-8"))

    hyp_evidence = _hypotheses_evidence(hypotheses)
    per_hypothesis = {}
    for code, claim_ids in sorted(hyp_evidence.items()):
        region_results = {}
        for region in REGIONS:
            state, reasons = classify_hypothesis_region(claim_ids, region)
            region_results[region] = {"state": state, "reasons": reasons}
        per_hypothesis[code] = {
            "resolved_claim_ids": claim_ids,
            "regions": region_results,
        }

    return {
        "topic_name": "AI_ENERGY_INFRA",
        "purpose": (
            "Per-hypothesis, per-region geographic applicability of H1-H7's CURRENT resolved "
            "evidence, built to prevent single-region findings from being silently read as "
            "national/multi-national/cross-country generalizations."
        ),
        "states": [MATCHED, PARTIAL_MATCH, OUT_OF_SCOPE, UNKNOWN],
        "regions_considered": REGIONS,
        "anti_overgeneralization_rules": [
            "PJM evidence is never promoted to MATCHED for USA as a whole.",
            "US evidence is never promoted to MATCHED/PARTIAL_MATCH for Korea, and vice versa.",
            "Ireland's data-center-electricity-share figure is never used as an EU-wide average.",
            "A derivative/secondary China estimate is never promoted to an official Chinese "
            "observed value.",
            "Korea capital-region CONTRACTED power capacity is never converted into actual AI "
            "electricity consumption.",
        ],
        "ireland_eu_note": IRELAND_DC_SHARE_NOTE,
        "per_hypothesis": per_hypothesis,
    }


def main():
    result = build_result()
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
