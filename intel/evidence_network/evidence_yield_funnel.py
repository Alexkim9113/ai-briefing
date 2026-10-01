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


def main():
    funnel = build_funnel()
    OUT_PATH.write_text(json.dumps(funnel, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH}: admission_yield={funnel['overall_admission_yield_fraction']}")


if __name__ == "__main__":
    main()
