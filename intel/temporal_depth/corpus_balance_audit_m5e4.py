# PHASE M.5E-4 section 14 -- Corpus Balance Audit at phase end.
#
# Te's spec asked for a balance audit covering: source type, domain, geography, time, evidence
# family, primary/secondary, and topic distributions -- to surface over-concentration and feed
# the next phase's acquisition-priority decision. Never a target/threshold check (no "pass/fail"
# here) -- purely descriptive, honest counts.
#
# This module is ADDITIVE, not a rewrite: intel/temporal_depth/corpus_balance.py (M.5E-3) already
# covers source_type/source_tier/domain/temporal_bucket/independent_source_family honestly and is
# reused here UNMODIFIED (imported, not reforked). This module adds the three dimensions Te's
# M.5E-4 spec named that corpus_balance.py did not yet cover: GEOGRAPHY (publisher-only, per the
# still-outstanding structural separation from event/jurisdiction geography -- explicitly labeled
# as publisher geography, never silently presented as event geography), EVIDENCE_FAMILY (real
# admitted document vs. the general-knowledge/gap-closure sidecar outputs this phase produced),
# and PRIMARY_VS_SECONDARY + TOPIC (this corpus's own `category`/`field` values, honestly reported
# as-is -- `field` is None for the majority of documents, which is reported plainly, not hidden).
#
# Zero LLM calls. Stdlib only. Read-only -- writes only this module's own result sidecar file,
# never documents.json.
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
DOCUMENTS_PATH = INTEL_DIR / "documents.json"
OUT_PATH = HERE / "corpus_balance_audit_m5e4_result.json"


def _load_isolated(path, unique_name):
    key = f"_corpus_balance_audit_m5e4_isolated__{unique_name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


def _corpus_balance():
    return _load_isolated(HERE / "corpus_balance.py", "corpus_balance")


def _geography_inference():
    return _load_isolated(INTEL_DIR / "geographic_evidence" / "geography_inference.py",
                           "geography_inference")


def load_documents(documents_path=DOCUMENTS_PATH):
    return json.loads(Path(documents_path).read_text(encoding="utf-8"))


# Category values this corpus actually uses (from a real, direct count of intel/documents.json,
# see module docstring): "papers"/"research" are the closest proxy this corpus has for a primary/
# academic source; "policy" is a primary/government source; "news_ko"/"news_global" are secondary/
# journalistic. This mapping is explicit and honestly reported as a judgment call, not asserted as
# an authoritative primary/secondary taxonomy this corpus schema doesn't actually encode.
_PRIMARY_SECONDARY_MAP = {
    "papers": "PRIMARY_ACADEMIC",
    "research": "PRIMARY_ACADEMIC",
    "policy": "PRIMARY_GOVERNMENT",
    "news_ko": "SECONDARY_JOURNALISTIC",
    "news_global": "SECONDARY_JOURNALISTIC",
}


def primary_secondary_distribution(documents):
    counts = Counter()
    for doc in documents.values():
        category = doc.get("category")
        label = _PRIMARY_SECONDARY_MAP.get(category, f"UNCLASSIFIED({category!r})")
        counts[label] += 1
    return dict(counts)


def topic_field_distribution(documents, top_n=20):
    """Honest, as-is count of this corpus's own `field` values -- including the large `None`
    bucket, which is reported plainly rather than dropped or folded into a misleading label."""
    counts = Counter(doc.get("field") for doc in documents.values())
    top = dict(counts.most_common(top_n))
    return {
        "total_distinct_field_values": len(counts),
        "documents_with_no_field_value": counts.get(None, 0),
        "top_field_values": top,
    }


def geography_distribution(documents):
    """PUBLISHER geography only (per geography_inference.py's own documented scope -- this is
    where the document's publisher/outlet is based, NOT the event/jurisdiction the document is
    about). Explicitly labeled as such so this audit is never mistaken for the event-geography
    breakdown Te's spec separately asks for as future structural work (see M.5E-4 report section
    on publisher-vs-event geography)."""
    gi = _geography_inference()
    counts = Counter()
    for doc in documents.values():
        inference = gi.infer_document_geography(doc)
        country = inference["country"] if inference else "UNKNOWN"
        counts[country] += 1
    total = len(documents)
    unknown = counts.get("UNKNOWN", 0)
    return {
        "scope": "PUBLISHER_GEOGRAPHY_ONLY -- not event/jurisdiction geography (structurally "
                 "unseparated as of this phase; see M.5E-4 report)",
        "distribution": dict(counts),
        "unknown_count": unknown,
        "unknown_fraction": round(unknown / total, 4) if total else None,
    }


# Evidence-family sources: this phase's own gap-closure/general-knowledge sidecar outputs, read
# directly (not re-derived) so the audit reports exactly what those modules already honestly
# concluded, never re-judging their findings.
_EVIDENCE_FAMILY_SIDECARS = {
    "HISTORICAL_GENERAL_KNOWLEDGE": (
        INTEL_DIR / "historical_evidence" / "energy_infra_analogies_result.json",
        lambda r: len(r.get("general_historical_knowledge", {}).get("analogies", [])),
    ),
    "HISTORICAL_REAL_SOURCE_GATE_LOG": (
        INTEL_DIR / "historical_evidence" / "real_historical_evidence_gate_log.json",
        lambda r: sum(1 for row in r if row.get("verdict") == "REAL_HISTORICAL_EVIDENCE_ADMITTED"),
    ),
    "COUNTEREVIDENCE_REAL_SOURCE_GATE_LOG": (
        INTEL_DIR / "counterevidence" / "real_counterevidence_gate_log.json",
        lambda r: sum(1 for row in r if row.get("verdict") == "REAL_COUNTEREVIDENCE_ADMITTED"),
    ),
    "TRANSITION_REAL_SOURCE_GATE_LOG": (
        INTEL_DIR / "gap_closure" / "transition_admission_gate_log.json",
        lambda r: sum(1 for row in r if row.get("verdict") == "TRANSITION_ADMITTED_CANDIDATE"),
    ),
}


def evidence_family_summary():
    """Reads each gap-closure module's own already-written sidecar output and reports its
    admitted/qualifying count -- honestly zero where that module's own gate found nothing (never
    re-interpreted as a different outcome here)."""
    summary = {}
    for family, (path, counter_fn) in _EVIDENCE_FAMILY_SIDECARS.items():
        if not path.exists():
            summary[family] = {"status": "SIDECAR_NOT_YET_GENERATED", "count": None}
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            summary[family] = {"status": "SIDECAR_UNREADABLE", "count": None}
            continue
        summary[family] = {"status": "OK", "count": counter_fn(data)}
    return summary


def build_audit(documents=None):
    documents = documents if documents is not None else load_documents()
    cb = _corpus_balance()
    base_report = cb.corpus_balance_report(documents=documents, independence_sample_limit=150)
    return {
        "audit_scope_note": (
            "Descriptive only -- no pass/fail thresholds. Surfaces concentration for the next "
            "phase's acquisition-priority decision, per Te's M.5E-4 section 14."
        ),
        "base_corpus_balance": base_report,
        "primary_vs_secondary_distribution": primary_secondary_distribution(documents),
        "topic_field_distribution": topic_field_distribution(documents),
        "geography_distribution": geography_distribution(documents),
        "evidence_family_summary": evidence_family_summary(),
    }


def main():
    audit = build_audit()
    OUT_PATH.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH}: total_documents={audit['base_corpus_balance']['total_documents']}")


if __name__ == "__main__":
    main()
