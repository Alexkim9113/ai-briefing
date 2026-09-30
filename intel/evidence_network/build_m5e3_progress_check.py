# PHASE M.5E-3 -- item 4: honest minimum-meaningful-progress check comparing this slice against
# the M.5E-2 baseline (AI_ENERGY_INFRA's chain, 5/10 real nodes under the original status field).
# Zero LLM, deterministic, read-only.
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_PATH = HERE / "m5e3_progress_check.json"


def build():
    agents = json.loads((HERE / "deep_pilot_ai_agents_result.json").read_text(encoding="utf-8"))
    labor = json.loads((HERE / "deep_pilot_ai_labor_result.json").read_text(encoding="utf-8"))

    return {
        "baseline": {
            "topic": "AI_ENERGY_INFRA",
            "slice": "M.5E-2",
            "real_evidence_or_noted_nodes": 5,
            "total_nodes": 10,
        },
        "document_growth_metric": {
            "note": (
                "Lowest-priority metric per the M.5E-3 spec -- reported for completeness, not "
                "credited as progress on its own. This slice adds ZERO new documents to "
                "intel/documents.json (the corpus stays at 597 real documents); it only runs "
                "the existing Deep Pilot methodology against 2 additional topics using "
                "documents that were already admitted."
            ),
            "documents_added_by_this_slice": 0,
            "corpus_size_before_and_after": 597,
        },
        "evidentiary_progress_assessment": {
            "topics_added": ["AI_AGENTS", "AI_LABOR"],
            "ai_agents_chain_summary": agents["chain_summary"],
            "ai_labor_chain_summary": labor["chain_summary"],
            "real_finding": (
                "AI_AGENTS (12 real field-tagged documents) resolves 5/10 real-evidence-or-noted "
                "nodes -- the SAME count as the AI_ENERGY_INFRA baseline -- because it has real "
                "CURRENT-bucket NEWS and RESEARCH documents plus a real title-matched POLICY "
                "document in the BASELINE window. AI_LABOR (11 real field-tagged documents) "
                "resolves only 2/10 real-evidence-or-noted nodes: it has real CURRENT-bucket "
                "documents but NO real POLICY document in this corpus title-matches the labor "
                "keyword set used here (ai jobs / labor market / workforce / automation jobs / "
                "job displacement), so PREVIOUS_STATE and CONFIRMED_CHANGE both come back as "
                "real, honestly reported TEMPORAL_GAP. This is a genuine, previously "
                "undocumented corpus-coverage finding: this corpus's real POLICY (Federal "
                "Register) holdings do not cover AI-and-labor-market subject matter the way they "
                "cover AI-and-energy-infrastructure subject matter."
            ),
            "is_this_new_information": True,
            "was_this_finding_knowable_before_running_the_pipeline": (
                "No -- it required actually running the topic-keyword search against POLICY "
                "documents for AI_LABOR's keyword set, which had not been done before this "
                "slice. pilot_topic_coverage.py's PILOT_TOPICS comment already noted 11 real "
                "AI_LABOR field-tagged documents exist, but did not check POLICY-document "
                "coverage for that topic specifically."
            ),
        },
        "honest_conclusion": (
            "This slice's evidentiary progress is real but narrow: it confirms the Deep Pilot "
            "methodology generalizes correctly (byte-for-byte-equivalent AI_ENERGY_INFRA "
            "regression) and surfaces one genuine new coverage gap (AI_LABOR has no real "
            "matching POLICY/BASELINE document in this corpus, unlike AI_ENERGY_INFRA or "
            "AI_AGENTS). It does NOT close any evidence gap, add any document, or improve any "
            "topic's real-evidence count above what the corpus already, honestly supports. "
            "Framed against the spec's own priority order (document growth lowest, genuine "
            "evidentiary progress higher), this slice's real contribution is the AI_LABOR "
            "coverage-gap finding above, not corpus growth -- and that finding is itself a gap, "
            "not a closure, so it should not be overstated as meaningful forward progress on "
            "AI_LABOR specifically. It IS meaningful progress on breadth-of-methodology "
            "validation, which was this slice's actual scope."
        ),
    }


def main():
    OUT_PATH.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
