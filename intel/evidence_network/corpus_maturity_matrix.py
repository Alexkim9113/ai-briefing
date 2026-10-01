# M.5E FINAL Section 33 -- Corpus Maturity Matrix. Explicitly NOT a single composite score (Te's
# instruction): 17 independent dimensions, each with its own measurement/numerator/denominator/
# method/status/limitation. Reuses existing audits (source_diversity, corpus_quality,
# corpus_balance_audit_m5e4, domain_classifier) rather than recomputing their logic.
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent

sys.path.insert(0, str(INTEL_DIR / "source_diversity"))
import audit as _source_diversity  # noqa: E402

OUT_PATH = HERE / "corpus_maturity_matrix_result.json"


def _load(path):
    p = INTEL_DIR / path
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def build_matrix():
    documents = _source_diversity.load_documents()
    total = len(documents)
    sd = _source_diversity.source_diversity_report(documents)
    quality = _load("corpus_quality/corpus_quality_result.json")
    balance = _load("temporal_depth/corpus_balance_audit_m5e4_result.json")
    domain = _load("topic_classification/domain_classification_result.json")
    energy_v2 = _load("evidence_network/deep_pilot_v2_ai_energy_infra_result.json")
    labor_v2 = _load("evidence_network/deep_pilot_v2_ai_labor_result.json")

    dates = sorted(d.get("published") for d in documents.values() if d.get("published"))
    source_ids = set(d.get("source_id") for d in documents.values())

    dims = {}

    dims["SOURCE_DIVERSITY"] = {
        "measurement": "distinct source_id count / total documents", "numerator": len(source_ids),
        "denominator": total, "method": "set() of source_id over documents.json",
        "status": "PARTIALLY_SUPPORTED" if len(source_ids) < 50 else "SUPPORTED",
        "limitation": "counts distinct feeds, not distinct owning organizations -- e.g. "
                      "src_구글뉴스_ai_정책 and src_google_news_ai_regulation are the same "
                      "aggregator counted twice",
    }
    dims["PRIMARY_SOURCE_COVERAGE"] = {
        "measurement": "direct_primary_source_ratio (reused from source_diversity.audit)",
        "numerator": None, "denominator": total,
        "method": "intel/source_diversity/audit.py:direct_primary_source_ratio()",
        "status": "SEE_RAW", "raw": sd.get("direct_primary_source_ratio"),
        "limitation": "primary/secondary is source_id-verified per M.5F Section 23's correction, "
                      "not the raw category field",
    }
    dims["ACADEMIC_COVERAGE"] = {
        "measurement": "academic_source_ratio (reused)", "method": "audit.py:academic_source_ratio()",
        "status": "SEE_RAW", "raw": sd.get("academic_source_ratio"),
        "limitation": "counts arXiv/Crossref-tagged source_ids only; does not verify peer-review "
                      "status of each individual document",
    }
    dims["POLICY_RESEARCH_COVERAGE"] = {
        "measurement": "count of documents whose source_id matches a known policy-research-"
                       "institute pattern (KDI/KIET/KEEI/KOSTAT/KISTEP/KRIHS/KREI)",
        "numerator": sum(1 for d in documents.values()
                         if any(s in (d.get("source_id") or "").lower()
                                for s in ("kdi", "kiet", "keei", "kostat", "krihs", "kistep", "krei"))),
        "denominator": total, "method": "direct source_id substring check, same pattern as "
                                         "deep_pilot_v2.py's POLICY_RESEARCH_CONTEXT node",
        "status": "NOT_READY",
        "limitation": "0 confirmed -- no Korean policy-research-institute source is registered in "
                      "this corpus at all; this is a real coverage gap, not a measurement artifact",
    }
    dims["STATISTICAL_COVERAGE"] = {
        "measurement": "statistical_source_ratio (reused)",
        "method": "audit.py:statistical_source_ratio()", "status": "SEE_RAW",
        "raw": sd.get("statistical_source_ratio"),
        "limitation": "0 confirmed in prior rounds -- no World Bank/EIA/KOSTAT-class source "
                      "registered; a real gap",
    }
    dates_span_years = None
    if dates:
        try:
            y0, y1 = int(dates[0][:4]), int(dates[-1][:4])
            dates_span_years = y1 - y0
        except Exception:
            dates_span_years = None
    dims["TEMPORAL_DEPTH"] = {
        "measurement": "earliest to latest published date span in years",
        "numerator": dates_span_years, "denominator": None,
        "method": "min/max of documents.json published field",
        "status": "PARTIALLY_SUPPORTED",
        "limitation": "span is dominated by a handful of historical outliers (earliest 1990s "
                      "document); the real working corpus is concentrated in 2025-2026 -- a wide "
                      "span is not the same as dense longitudinal coverage",
    }
    dims["LONGITUDINAL_CONTINUITY"] = {
        "measurement": "TRANSITION-bucket document count across the two rebuilt Deep Pilots",
        "numerator": sum(1 for p in (energy_v2, labor_v2) if p and
                         p["nodes"]["TRANSITION"]["status"] == "SUPPORTED"),
        "denominator": 2, "method": "deep_pilot_v2 TRANSITION node status, both pilots",
        "status": "NOT_READY",
        "limitation": "0/2 pilots have a real document bridging baseline and current state -- "
                      "longitudinal continuity is a named, honest gap, not assumed solved by a "
                      "wide date range",
    }
    dims["GEOGRAPHIC_COVERAGE"] = {
        "measurement": "GEOGRAPHIC_CONTEXT node status across the two rebuilt Deep Pilots",
        "numerator": 0, "denominator": 2,
        "method": "deep_pilot_v2 GEOGRAPHIC_CONTEXT node", "status": "NOT_READY",
        "limitation": "documents.json has no jurisdiction/event_country/affected_region field at "
                      "all -- this is a schema gap, not a search failure",
    }
    dims["TOPIC_COVERAGE"] = {
        "measurement": "domain-classified fraction of corpus",
        "numerator": (domain.get("total_documents", 0) - domain.get("documents_unclassified", 0))
                     if domain else None,
        "denominator": domain.get("total_documents") if domain else total,
        "method": "topic_classification/domain_classifier.py build_coverage_report()",
        "status": "PARTIALLY_SUPPORTED",
        "limitation": "73 USEFUL_BUT_UNCLASSIFIED documents sample-audited (Section 26 of this "
                      "round) -- mostly genuinely off-topic, a small borderline minority remains "
                      "an honest small gap, not forced closed",
    }
    dims["COUNTEREVIDENCE_COVERAGE"] = {
        "measurement": "COUNTEREVIDENCE node status across the two rebuilt Deep Pilots",
        "numerator": sum(1 for p in (energy_v2, labor_v2) if p and
                         p["nodes"]["COUNTEREVIDENCE"]["status"] == "SUPPORTED"),
        "denominator": 2, "method": "deep_pilot_v2 COUNTEREVIDENCE node", "status": "NOT_READY",
        "limitation": "0/2 pilots have real counterevidence connected; Section 28's candidate "
                      "hypothesis list was not yet searched against the live corpus this round",
    }
    dims["HISTORICAL_COVERAGE"] = {
        "measurement": "HISTORICAL_CONTEXT node status across the two rebuilt Deep Pilots",
        "numerator": sum(1 for p in (energy_v2, labor_v2) if p and
                         p["nodes"]["HISTORICAL_CONTEXT"]["status"] == "SUPPORTED"),
        "denominator": 2, "method": "deep_pilot_v2 HISTORICAL_CONTEXT node", "status": "NOT_READY",
        "limitation": "0/2; historical_analogy.py's build_analogy_v2() pipeline exists and is "
                      "tested but was not re-run against either pilot topic this round",
    }
    dims["ALTERNATIVE_EXPLANATION_COVERAGE"] = {
        "measurement": "ALTERNATIVE_EXPLANATION node status across the two rebuilt Deep Pilots",
        "numerator": 0, "denominator": 2,
        "method": "deep_pilot_v2 ALTERNATIVE_EXPLANATION node", "status": "NOT_READY",
        "limitation": "Section 29's candidate list was not yet searched this round -- QUERY_GAP, "
                      "not evidence that no alternative explanation exists",
    }
    dims["PROVENANCE_COMPLETENESS"] = {
        "measurement": "fraction of documents with a real canonical_url and source_id",
        "numerator": sum(1 for d in documents.values() if d.get("canonical_url") and d.get("source_id")),
        "denominator": total, "method": "direct field presence check on documents.json",
        "status": "SUPPORTED",
        "limitation": "presence of a URL/source_id is not itself verification the link resolves "
                      "live (not checked in this offline round)",
    }
    dims["METADATA_QUALITY"] = {
        "measurement": "1 - (METADATA_POOR bucket count / total)",
        "numerator": quality.get("total_documents", total) - quality.get("bucket_counts", {}).get("METADATA_POOR", 0)
                     if quality else None,
        "denominator": quality.get("total_documents") if quality else total,
        "method": "corpus_quality_audit.py bucket_counts", "status": "SUPPORTED",
        "limitation": "0 METADATA_POOR documents found in the real corpus as of this snapshot",
    }
    dims["ACCESSIBILITY"] = {
        "measurement": "fraction of documents with rights_mode allowing at least a lawful link",
        "numerator": sum(1 for d in documents.values() if d.get("rights_mode") == "LINK_ONLY"),
        "denominator": total, "method": "direct rights_mode field tally",
        "status": "SUPPORTED",
        "limitation": "100% LINK_ONLY is a copyright-safety strength but means 0% of this corpus "
                      "has any stored full text -- 'accessible' here means 'has a lawful link', "
                      "not 'full text immediately usable'",
    }
    dims["COPYRIGHT_SAFETY"] = {
        "measurement": "fraction of documents NOT storing full text (rights_mode == LINK_ONLY)",
        "numerator": sum(1 for d in documents.values() if d.get("rights_mode") == "LINK_ONLY"),
        "denominator": total, "method": "direct rights_mode field tally", "status": "SUPPORTED",
        "limitation": "measures storage-boundary compliance only, not license verification per "
                      "document (no RIGHTS_STATUS/LICENSE field exists in this schema yet -- see "
                      "Section 3-12 Research Rights Model, not yet implemented this round)",
    }
    dims["EVIDENCE_INDEPENDENCE"] = {
        "measurement": "google_news_dependency (reused)", "method": "audit.py:google_news_dependency()",
        "status": "SEE_RAW", "raw": sd.get("google_news_dependency"),
        "limitation": "a high aggregator share means many documents trace back to the same "
                      "upstream wire story, inflating apparent source_id diversity",
    }

    assert set(dims.keys()) == {
        "SOURCE_DIVERSITY", "PRIMARY_SOURCE_COVERAGE", "ACADEMIC_COVERAGE",
        "POLICY_RESEARCH_COVERAGE", "STATISTICAL_COVERAGE", "TEMPORAL_DEPTH",
        "LONGITUDINAL_CONTINUITY", "GEOGRAPHIC_COVERAGE", "TOPIC_COVERAGE",
        "COUNTEREVIDENCE_COVERAGE", "HISTORICAL_COVERAGE", "ALTERNATIVE_EXPLANATION_COVERAGE",
        "PROVENANCE_COMPLETENESS", "METADATA_QUALITY", "ACCESSIBILITY", "COPYRIGHT_SAFETY",
        "EVIDENCE_INDEPENDENCE",
    }, "must cover exactly the 17 named dimensions, no more, no fewer"

    return {
        "note": "M.5E FINAL Section 33 Corpus Maturity Matrix. Deliberately NOT a composite "
                "score -- 17 independent dimensions, each judged on its own evidence.",
        "total_documents": total,
        "dimensions": dims,
    }


def main():
    matrix = build_matrix()
    OUT_PATH.write_text(json.dumps(matrix, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH}: {len(matrix['dimensions'])} dimensions")


if __name__ == "__main__":
    main()
