# N-1 -- 601-doc re-audit using content_aware_relevance instead of N-0's title-only gate.
# Computes Before (N-0 title-only result) vs After (content-aware result) and a transition-count
# table. Never deletes documents.json; writes separate result artifacts only.
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import content_aware_relevance as car  # noqa: E402

ROOT = HERE.parent.parent
DOCUMENTS_PATH = ROOT / "intel" / "documents.json"
N0_VISIBILITY_PATH = HERE / "public_visibility.json"  # N-0's title-only result (kept as Before)

CONTENT_AWARE_RESULT_PATH = HERE / "content_aware_relevance_audit_result.json"
PUBLIC_VISIBILITY_RESULT_PATH = HERE / "public_visibility_result.json"
TRANSITION_RESULT_PATH = HERE / "relevance_transition_result.json"


def run_audit():
    documents = json.loads(DOCUMENTS_PATH.read_text(encoding="utf-8"))
    before = json.loads(N0_VISIBILITY_PATH.read_text(encoding="utf-8")) if N0_VISIBILITY_PATH.exists() else {}

    after = {}
    before_counts, after_counts = {}, {}
    transitions = {}

    for doc_id, doc in documents.items():
        result = car.classify_content_aware_relevance(doc)
        after[doc_id] = {
            "document_id": doc_id, "relevance_class": result["relevance_class"],
            "relevance_basis": result["relevance_basis"], "relevance_scope": result["relevance_scope"],
            "content_depth": result["content_depth"], "publication_eligible": result["publication_eligible"],
            "publication_reason": result["publication_reason"],
            "evidence_relevance": result["evidence_relevance"],
            "evidence_matched_hypotheses": result["evidence_matched_hypotheses"],
            "research_status": "UNKNOWN",  # filled in by research_corpus_audit.py
            "source_type": doc.get("category"),
            "visibility": "PUBLIC" if result["publication_eligible"] else (
                "QUARANTINED" if result["relevance_class"] == "UNCERTAIN_RELEVANCE" else "INTERNAL_ONLY"),
            "updated_at": doc.get("updated_at"),
        }
        after_cat = result["relevance_class"]
        after_counts[after_cat] = after_counts.get(after_cat, 0) + 1

        before_cat = before.get(doc_id, {}).get("public_relevance_category", "NOT_AUDITED")
        before_counts[before_cat] = before_counts.get(before_cat, 0) + 1
        if before_cat != after_cat:
            key = f"{before_cat} -> {after_cat}"
            transitions[key] = transitions.get(key, 0) + 1

    return after, before_counts, after_counts, transitions


def main():
    after, before_counts, after_counts, transitions = run_audit()
    CONTENT_AWARE_RESULT_PATH.write_text(
        json.dumps({"total_audited": len(after), "before_counts": before_counts,
                    "after_counts": after_counts, "transition_count": transitions},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    PUBLIC_VISIBILITY_RESULT_PATH.write_text(json.dumps(after, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    TRANSITION_RESULT_PATH.write_text(json.dumps(transitions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"before_counts": before_counts, "after_counts": after_counts,
                       "transition_count": transitions}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
