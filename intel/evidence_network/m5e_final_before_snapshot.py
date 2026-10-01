# M.5E FINAL Section 2 -- BEFORE SNAPSHOT. Freezes the real state of the corpus and existing
# sidecar results at the start of Section 24-35 work, for an honest AFTER diff in the final
# report's Section B. Reuses existing sidecars rather than recomputing their logic; reads
# documents.json directly only for fields no existing sidecar already reports.
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
OUT_PATH = HERE / "m5e_final_before_snapshot.json"


def _git_head():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=INTEL_DIR.parent,
                                        text=True).strip()
    except Exception as e:
        return f"UNKNOWN ({e})"


def _load(path):
    p = INTEL_DIR / path
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def build_snapshot():
    docs = json.loads((INTEL_DIR / "documents.json").read_text(encoding="utf-8"))
    category_counts = Counter(d.get("category") for d in docs.values())
    # This corpus's real schema has no top-level NEWS/RESEARCH/POLICY/OTHER field -- `category`
    # is the real content-type tag. Mapping is explicit and honest, not invented: news_ko +
    # news_global -> NEWS, papers + research -> RESEARCH, policy -> POLICY, anything else -> OTHER.
    news = category_counts.get("news_ko", 0) + category_counts.get("news_global", 0)
    research = category_counts.get("papers", 0) + category_counts.get("research", 0)
    policy = category_counts.get("policy", 0)
    other = len(docs) - news - research - policy

    dates = sorted(d.get("published") for d in docs.values() if d.get("published"))
    source_counts = Counter(d.get("source_id") for d in docs.values())

    balance = _load("temporal_depth/corpus_balance_audit_m5e4_result.json")
    domain = _load("topic_classification/domain_classification_result.json")
    quality = _load("corpus_quality/corpus_quality_result.json")
    deep_pilot_energy = _load("evidence_network/deep_pilot_result.json")
    deep_pilot_labor = _load("evidence_network/deep_pilot_ai_labor_result.json")

    snapshot = {
        "note": (
            "M.5E FINAL Section 2 BEFORE snapshot. Frozen before any Section 24-35 code was "
            "written. Fields with no existing sidecar to reuse are computed directly from "
            "documents.json here; this script performs no network access and writes nothing to "
            "documents.json."
        ),
        "git_head": _git_head(),
        "document_count": len(docs),
        "category_breakdown_real_field": dict(category_counts),
        "news_research_policy_other_mapped": {
            "NEWS": news, "RESEARCH": research, "POLICY": policy, "OTHER": other,
            "mapping_note": "category news_ko+news_global->NEWS, papers+research->RESEARCH, "
                            "policy->POLICY, else->OTHER (this corpus has no native top-level "
                            "NEWS/RESEARCH/POLICY/OTHER field)",
        },
        "primary_vs_secondary": (
            balance.get("primary_vs_secondary_distribution") if balance else
            "UNAVAILABLE -- corpus_balance_audit_m5e4_result.json not found"
        ),
        "primary_secondary_correction_note": (
            balance.get("primary_vs_secondary_distribution_correction_note") if balance else None
        ),
        "source_counts_top20": dict(source_counts.most_common(20)),
        "distinct_source_count": len(source_counts),
        "earliest_date": dates[0] if dates else None,
        "latest_date": dates[-1] if dates else None,
        "temporal_span_note": (
            f"{dates[0]} to {dates[-1]}" if dates else "no dated documents"
        ),
        "domain_classification_coverage": (
            {
                "total_documents": domain.get("total_documents"),
                "documents_unclassified": domain.get("documents_unclassified"),
                "documents_classified": (
                    domain.get("total_documents", 0) - domain.get("documents_unclassified", 0)
                ),
                "documents_unclassified_fraction": domain.get("documents_unclassified_fraction"),
            } if domain else "UNAVAILABLE"
        ),
        "corpus_quality_bucket_counts": quality.get("bucket_counts") if quality else "UNAVAILABLE",
        "corpus_quality_total_documents": quality.get("total_documents") if quality else None,
        "deep_pilot_ai_energy_infra_state_before": (
            {
                "topic_field_value": deep_pilot_energy.get("topic_field_value"),
                "total_topic_documents": deep_pilot_energy.get("total_topic_documents"),
                "note": "pre-rebuild (old 10-node scoring, M.5E era) -- see Section 24/25 rebuild",
            } if deep_pilot_energy else "UNAVAILABLE"
        ),
        "deep_pilot_ai_labor_state_before": (
            {
                "topic_field_value": deep_pilot_labor.get("topic_field_value"),
                "total_topic_documents": deep_pilot_labor.get("total_topic_documents"),
                "note": "pre-rebuild (old 10-node scoring, M.5E era) -- see Section 24/26 rebuild",
            } if deep_pilot_labor else "UNAVAILABLE"
        ),
        "known_gaps_before": [
            "USEFUL_BUT_UNCLASSIFIED: 73 documents (Corpus Quality Section 21) -- root cause not "
            "yet sample-audited as of this snapshot",
            "AI_LABOR Deep Pilot historically weak (2/10 old-scoring) -- root cause not yet "
            "diagnosed as of this snapshot",
            "NOT_FOUND_GAP_CLASSES taxonomy had a VALIDATION_GAP vs CLASSIFICATION_GAP vocabulary "
            "discrepancy vs this message's own spec -- resolved earlier in this round by adding "
            "VALIDATION_GAP alongside the existing CLASSIFICATION_GAP",
        ],
        "known_regression_failures_before": [
            "None open as of this snapshot -- intel/interpretive_contract/tests/test_fixture.py "
            "reported PASSED=72/72 at the end of the prior round (commit b59f59f)",
        ],
    }
    return snapshot


def main():
    snap = build_snapshot()
    OUT_PATH.write_text(json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH}: documents={snap['document_count']} head={snap['git_head']}")


if __name__ == "__main__":
    main()
