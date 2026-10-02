# O-3B -- AI RELEVANCE GATE (Te's spec section 5). METAXIS is not a general news
# Intelligence system: a collected document/event must pass a single question before it can
# ever reach Discovery/Candidate/Evidence/Claim status -- "이 사건에서 AI가 실제 핵심
# 변수인가?" (Is AI actually the central variable in this event?). A document that merely
# mentions AI in passing is excluded.
#
# This module does NOT reinvent relevance detection. It reuses the existing, already
# battle-tested deterministic classifier chain:
#   intel/source_intelligence/ai_relevance.py::assess_ai_relevance()  (CENTRAL/PERIPHERAL/
#     NONE/AMBIGUOUS via the REMOVE_AI_TEST counterfactual)
#   intel/public_relevance/relevance_gate.py::classify_public_relevance()  (adds the
#     weak-keyword-is-not-evidence rule and AI_* subtype naming on top)
# That existing module was built for a different purpose (Public Feed display categories) and
# was never wired into the Discovery/Event/Candidate production pipeline. This module wires the
# SAME deterministic judgment into that pipeline for Intelligence purposes, additively: it never
# deletes or edits production_events.json/documents.json, it only produces a parallel gate
# verdict per event/document that downstream Candidate Engine work (O-3E) can read.
#
# PASS vocabulary is intentionally narrow: only CENTRAL passes outright. AMBIGUOUS is never
# auto-passed or auto-failed (Te: "억지로 만들어내지 않는다") -- it is reported as its own
# bucket for an operator to look at, never silently merged into PASS or FAIL.
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "intel" / "public_relevance"))
sys.path.insert(0, str(ROOT / "intel" / "source_intelligence"))
import relevance_gate as _prg  # noqa: E402

GATE_PASS = "PASS"
GATE_FAIL = "FAIL"
GATE_AMBIGUOUS = "NEEDS_REVIEW"


def evaluate(title, summary=""):
    """Returns {"gate": PASS/FAIL/NEEDS_REVIEW, "category": ..., "reason": ...}.
    Deterministic, no LLM call (Te section 18: taxonomy/relevance classification is a LOW VALUE
    token task, must not spend LLM budget)."""
    verdict = _prg.classify_public_relevance(title, summary)
    category = verdict["category"]
    basis_status = verdict["basis"]["status"]
    if basis_status == "CENTRAL":
        gate = GATE_PASS
    elif basis_status == "AMBIGUOUS" or category == "INSUFFICIENT_EVIDENCE":
        gate = GATE_AMBIGUOUS
    else:
        gate = GATE_FAIL
    return {"gate": gate, "category": category, "reason": verdict["reason"]}


def run_on_documents(documents_path=None, facts_path=None, out_path=None):
    """Real-data runner (O-3 section 29 deliverable items 1-2): applies the gate to every
    document in intel/documents.json (the Evidence Pipeline's curated document pool), using
    each document's own title plus its linked fact's `object` text as the closest available
    stand-in for a summary (documents.json carries no separate summary field). Writes a result
    file and returns the summary counts; never mutates documents.json/facts.json."""
    documents_path = Path(documents_path or ROOT / "intel" / "documents.json")
    facts_path = Path(facts_path or ROOT / "intel" / "facts.json")
    out_path = Path(out_path or HERE / "ai_relevance_gate_result.json")

    documents = json.loads(documents_path.read_text(encoding="utf-8"))
    facts = json.loads(facts_path.read_text(encoding="utf-8"))
    fact_object_by_doc = {}
    for f in facts.values():
        doc_id = f.get("document_id")
        obj = f.get("object")
        if doc_id and obj and doc_id not in fact_object_by_doc:
            fact_object_by_doc[doc_id] = obj

    results = {}
    counts = {GATE_PASS: 0, GATE_FAIL: 0, GATE_AMBIGUOUS: 0}
    for doc_id, doc in documents.items():
        title = doc.get("title") or ""
        summary = fact_object_by_doc.get(doc_id, "")
        verdict = evaluate(title, summary)
        results[doc_id] = verdict
        counts[verdict["gate"]] += 1

    output = {
        "generated_from": "intel/documents.json (real collected document pool)",
        "document_count": len(documents),
        "counts": counts,
        "results": results,
    }
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


if __name__ == "__main__":
    result = run_on_documents()
    print(json.dumps({"document_count": result["document_count"], "counts": result["counts"]},
                      ensure_ascii=False, indent=2))
