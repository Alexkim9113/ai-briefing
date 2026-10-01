# M.5E FINAL Section 27 -- full gap records for every NOT_FOUND node across both rebuilt Deep
# Pilots, in the exact field shape Te specified: gap_id, topic, node, gap_type, query_attempt,
# source_attempt, access_result, validation_result, reason, remaining_gap, next_possible_action.
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_PATH = HERE / "gap_records_result.json"


def _load(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def build_gap_records():
    pilots = {
        "AI_ENERGY_INFRA": _load("deep_pilot_v2_ai_energy_infra_result.json"),
        "AI_LABOR": _load("deep_pilot_v2_ai_labor_result.json"),
    }
    records = []
    n = 0
    for topic, pilot in pilots.items():
        for node_name, node in pilot["nodes"].items():
            if node["status"] != "NOT_FOUND":
                continue
            n += 1
            records.append({
                "gap_id": f"gap_{topic.lower()}_{node_name.lower()}_{n:03d}",
                "topic": topic,
                "node": node_name,
                "gap_type": node.get("gap_type", "SOURCE_GAP"),
                "query_attempt": "see node reason -- this round reused existing pilot results and "
                                 "ran a direct corpus check for the 3 new nodes (POLICY_RESEARCH_"
                                 "CONTEXT, ALTERNATIVE_EXPLANATION, GEOGRAPHIC_CONTEXT); no new "
                                 "live search queries were executed this round",
                "source_attempt": "existing registered source classes for this Evidence Type "
                                   "(query_planner.route_evidence_type_to_source_classes)",
                "access_result": "N/A -- sandbox network blocked this session; no new acquisition "
                                  "attempted",
                "validation_result": "N/A -- no new candidate reached the admission gate for this "
                                      "node this round",
                "reason": node.get("reason"),
                "remaining_gap": f"{node_name} for {topic} has no SUPPORTED real evidence",
                "next_possible_action": {
                    "SOURCE_GAP": "register the missing source class (e.g. a Korean policy-"
                                   "research-institute or statistical-agency connector) before "
                                   "any search can succeed",
                    "QUERY_GAP": "execute the registered query-expansion/Evidence-Type query plan "
                                 "against a live connector in a network-enabled run (GitHub "
                                 "Actions) and feed results through the real admission gate",
                    "TEMPORAL_GAP": "acquire a document dated in the gap window from an existing "
                                    "registered source",
                    "GEOGRAPHIC_GAP": "add a jurisdiction/event_country field to the document "
                                       "schema before this can be measured at all",
                    "VALIDATION_GAP": "inspect why the candidate failed validation and fix the "
                                       "specific check it failed",
                }.get(node.get("gap_type", "SOURCE_GAP"), "investigate directly"),
            })
    return records


def main():
    records = build_gap_records()
    OUT_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH}: {len(records)} gap records")


if __name__ == "__main__":
    main()
