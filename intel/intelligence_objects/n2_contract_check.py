# N-2 Section 30-31 -- verifies the EXISTING intelligence_object.py schema already satisfies the
# minimum Phase N backend contract, and runs a Report Engine contract test against real data
# (never fabricated fixtures) to confirm a minimal report CAN be assembled from an Intelligence
# Object alone. Read-only against intelligence_objects.json -- writes only its own result files.
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import intelligence_object as io  # noqa: E402

REQUIRED_CONTRACT_FIELDS = (
    "topic", "current_state", "key_claims", "supporting_evidence", "counterevidence",
    "alternative_explanations", "statistics", "research_context", "policy_context",
    "geographic_context", "temporal_chain", "uncertainties", "known_gaps", "provenance",
    "revision_history", "readiness",
)

REPORT_SECTIONS = (
    "Executive Summary", "What Happened", "Evidence", "Research", "Statistics",
    "Counterevidence", "Alternative Explanations", "Uncertainty", "METAXIS Point", "Sources",
)

RESULT_PATH = HERE / "intelligence_object_contract_result.json"
REPORT_CONTRACT_RESULT_PATH = HERE / "report_engine_contract_test_result.json"


def check_schema_contract():
    sample = io.new_intelligence_object("contract_check_topic", "contract_check_question")
    missing = [f for f in REQUIRED_CONTRACT_FIELDS if f not in sample]
    return {"schema_fields_checked": REQUIRED_CONTRACT_FIELDS, "missing_fields": missing,
            "status": "READY" if not missing else "NOT_READY"}


def build_minimal_report_skeleton(obj):
    """Assembles a minimal report using ONLY fields already present on a real Intelligence
    Object -- never invents data. A section with no real content is explicitly marked
    'insufficient evidence', never silently omitted or filled with placeholder narrative."""
    def _section(items):
        return items if items else "insufficient evidence"
    return {
        "Executive Summary": obj.get("current_state") or "insufficient evidence",
        "What Happened": obj.get("topic") or "insufficient evidence",
        "Evidence": _section(obj.get("supporting_evidence")),
        "Research": _section(obj.get("research_context")),
        "Statistics": _section(obj.get("statistics")),
        "Counterevidence": _section(obj.get("counterevidence")),
        "Alternative Explanations": _section(obj.get("alternative_explanations")),
        "Uncertainty": _section(obj.get("uncertainties")),
        "METAXIS Point": "not sourced from Intelligence Object in this contract test -- generated separately by briefing.py",
        "Sources": _section(obj.get("provenance")),
    }


def run_report_engine_contract_test():
    objects = io._load()
    if not objects:
        return {"status": "NOT_TESTABLE", "reason": "no real Intelligence Objects exist to test against"}
    results = []
    for intelligence_id, obj in objects.items():
        skeleton = build_minimal_report_skeleton(obj)
        missing_sections = [s for s, v in skeleton.items() if v == "insufficient evidence"]
        results.append({
            "intelligence_id": intelligence_id, "topic": obj.get("topic"),
            "sections_present": [s for s in REPORT_SECTIONS if skeleton.get(s) != "insufficient evidence"],
            "sections_insufficient_evidence": missing_sections,
        })
    return {"status": "READY", "tested_objects": len(results), "results": results}


def main():
    schema_result = check_schema_contract()
    RESULT_PATH.write_text(json.dumps(schema_result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    report_result = run_report_engine_contract_test()
    REPORT_CONTRACT_RESULT_PATH.write_text(json.dumps(report_result, ensure_ascii=False, indent=1) + "\n",
                                           encoding="utf-8")
    print(json.dumps({"schema": schema_result, "report_contract": report_result}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
