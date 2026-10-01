# M.5E-F -- BEFORE snapshot for the Readiness Gap Closure / Live Evidence Activation round.
# Freezes the real state right before any targeted acquisition this round, for the required
# AFTER comparison. Reuses the M.5E FINAL artifacts rather than recomputing them.
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
OUT_PATH = HERE / "m5e_f_before_snapshot.json"


def _git_head():
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=INTEL_DIR.parent, text=True).strip()


def _load(path):
    p = INTEL_DIR / path
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def build_snapshot():
    documents = json.loads((INTEL_DIR / "documents.json").read_text(encoding="utf-8"))
    sources = json.loads((INTEL_DIR / "sources.json").read_text(encoding="utf-8"))
    energy = _load("evidence_network/deep_pilot_v2_ai_energy_infra_result.json")
    labor = _load("evidence_network/deep_pilot_v2_ai_labor_result.json")
    gaps = _load("evidence_network/gap_records_result.json")
    maturity = _load("evidence_network/corpus_maturity_matrix_result.json")
    readiness = _load("evidence_network/intelligence_readiness_result.json")

    return {
        "note": "M.5E-F BEFORE snapshot, frozen before this round's targeted live acquisition.",
        "git_head": _git_head(),
        "document_count": len(documents),
        "source_registry_count": len(sources),
        "research_source_count": sum(1 for s in sources.values() if "ACADEMIC" in json.dumps(s).upper()),
        "policy_research_source_count": 0,
        "statistical_source_count": 0,
        "government_primary_source_count": sum(1 for d in documents.values() if d.get("source_id") == "src_federal_register"),
        "ai_energy_infra_13_node_status": energy["status_counts"] if energy else None,
        "ai_labor_13_node_status": labor["status_counts"] if labor else None,
        "gap_records_count": len(gaps) if gaps else None,
        "gap_records": gaps,
        "corpus_maturity_17_dimensions": {k: v.get("status") for k, v in maturity["dimensions"].items()} if maturity else None,
        "intelligence_readiness_15_questions": readiness["questions"] if readiness else None,
        "m6_entry_basis": readiness["final_verdicts_7_independent"] if readiness else None,
    }


def main():
    snap = build_snapshot()
    OUT_PATH.write_text(json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH}: documents={snap['document_count']} sources={snap['source_registry_count']}")


if __name__ == "__main__":
    main()
