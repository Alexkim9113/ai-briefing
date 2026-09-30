# PHASE M.5E-3 -- item 3 (part 2): builds multi_pilot_scored_summary.json, comparing all 3 pilot
# topics' node-support distributions (SUPPORTED/PARTIALLY_SUPPORTED/INSUFFICIENT_EVIDENCE/
# NOT_FOUND/NOT_APPLICABLE/UNKNOWN) side by side. Re-scores AI_ENERGY_INFRA's EXISTING M.5E-2
# chain from the already-committed deep_pilot_result.json (read, never recomputed or altered),
# and the two new topics' freshly-built chains. Zero LLM, deterministic, read-only against
# documents.json.
import json
from pathlib import Path

import deep_pilot as dp
import multi_topic_pilot as mtp
import node_support_evaluator as nse

HERE = Path(__file__).resolve().parent
OUT_PATH = HERE / "multi_pilot_scored_summary.json"


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_summary():
    energy_existing = _load(HERE / "deep_pilot_result.json")
    agents_report = _load(HERE / "deep_pilot_ai_agents_result.json")
    labor_report = _load(HERE / "deep_pilot_ai_labor_result.json")

    topics = {
        "AI_ENERGY_INFRA": energy_existing,
        "AI_AGENTS": agents_report,
        "AI_LABOR": labor_report,
    }

    per_topic = {}
    for name, report in topics.items():
        chain = report["evidence_chain"]
        node_labels = nse.evaluate_chain(chain)
        distribution = nse.support_distribution(chain)
        per_topic[name] = {
            "original_chain_summary": report["chain_summary"],
            "node_support_labels": node_labels,
            "node_support_distribution": distribution,
            "total_topic_documents": report["total_topic_documents"],
            "bucket_counts": report["bucket_counts"],
        }

    energy_orig_real = energy_existing["chain_summary"]["real_evidence_or_noted_nodes"]
    energy_orig_gap = energy_existing["chain_summary"]["gap_nodes"]
    energy_new_supported = per_topic["AI_ENERGY_INFRA"]["node_support_distribution"][nse.SUPPORTED]
    energy_new_partial = per_topic["AI_ENERGY_INFRA"]["node_support_distribution"][nse.PARTIALLY_SUPPORTED]

    return {
        "vocabulary": list(nse.SUPPORT_VOCABULARY),
        "topics": per_topic,
        "ai_energy_infra_vocabulary_change_note": (
            f"Under the original M.5E-2 status field, AI_ENERGY_INFRA scored "
            f"{energy_orig_real}/10 REAL_EVIDENCE-or-NOTED and {energy_orig_gap}/10 gap nodes. "
            f"Under the new 6-value vocabulary this splits into {energy_new_supported}/10 "
            f"SUPPORTED (the REAL_EVIDENCE nodes) plus {energy_new_partial}/10 "
            "PARTIALLY_SUPPORTED (the single UNCERTAINTY/NOTED node), and its 5 real gap nodes "
            "split further into NOT_FOUND (topic-scoped searches that found nothing) versus "
            "INSUFFICIENT_EVIDENCE (the corpus-wide STATISTICAL_GAP node) -- a real, expected, "
            "more granular reclassification, not a score change: no node's underlying "
            "evidence/gap status was altered, only its label under the new vocabulary."
        ),
        "cross_topic_note": (
            "AI_ENERGY_INFRA and AI_AGENTS both resolve identically: 4/10 SUPPORTED, 1/10 "
            "PARTIALLY_SUPPORTED, 1/10 INSUFFICIENT_EVIDENCE, 4/10 NOT_FOUND. AI_LABOR resolves "
            "far fewer nodes as SUPPORTED (1/10) and far more as NOT_FOUND (7/10) -- see "
            "node_support_distribution per topic. This reflects a real difference in how well "
            "this corpus's real documents cover each topic's temporal/cross-domain/"
            "primary-evidence needs, not a difference in methodology rigor between topics."
        ),
    }


def main():
    summary = build_summary()
    OUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH}")
    for name, t in summary["topics"].items():
        print(name, t["node_support_distribution"])


if __name__ == "__main__":
    main()
