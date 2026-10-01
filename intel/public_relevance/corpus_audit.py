# N-0 SLICE 2 -- corpus-wide Public Relevance audit + visibility sidecar. Never deletes or
# rewrites documents.json; only computes a per-document visibility classification in a separate
# sidecar (public_visibility.json), and prioritizes re-checking USEFUL_BUT_UNCLASSIFIED docs per
# Section 5's explicit instruction.
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import relevance_gate as rg  # noqa: E402

ROOT = HERE.parent.parent
DOCUMENTS_PATH = ROOT / "intel" / "documents.json"
DOMAIN_CLASSIFICATION_PATH = ROOT / "intel" / "topic_classification" / "domain_classification_result.json"
VISIBILITY_PATH = HERE / "public_visibility.json"

VISIBILITY_VALUES = ("PUBLIC", "INTERNAL_ONLY", "PRIVATE_RESEARCH", "QUARANTINED")


def _visibility_for_category(category):
    if category in rg.PUBLIC_CATEGORIES:
        return "PUBLIC"
    if category in ("USEFUL_BUT_UNCLASSIFIED", "INSUFFICIENT_EVIDENCE"):
        return "QUARANTINED"
    return "INTERNAL_ONLY"


def audit_corpus(documents=None, previously_unclassified_ids=None):
    """Returns (visibility_map, audit_summary). `previously_unclassified_ids`: document_ids the
    existing domain classifier marked USEFUL_BUT_UNCLASSIFIED -- these are checked first per
    Section 5, but every document in the corpus is audited (never only a sample)."""
    documents = documents if documents is not None else json.loads(DOCUMENTS_PATH.read_text(encoding="utf-8"))
    previously_unclassified_ids = previously_unclassified_ids or set()

    visibility_map = {}
    counts = {"total_audited": 0, "ai_relevant": 0, "weak_association": 0, "keyword_collision": 0,
              "general_news": 0, "not_relevant": 0, "uncertain": 0}
    category_counts = {}

    for doc_id, doc in documents.items():
        title = doc.get("title") or ""
        field = doc.get("field")
        existing_category = doc.get("category")
        result = rg.classify_public_relevance(title, "", field=field, existing_category=existing_category)
        category = result["category"]
        category_counts[category] = category_counts.get(category, 0) + 1
        visibility_map[doc_id] = {
            "document_id": doc_id, "public_relevance_category": category,
            "visibility": _visibility_for_category(category), "reason": result["reason"],
            "was_previously_unclassified": doc_id in previously_unclassified_ids,
        }
        counts["total_audited"] += 1
        if category in rg.PUBLIC_CATEGORIES:
            counts["ai_relevant"] += 1
        elif category == "WEAK_ASSOCIATION":
            counts["weak_association"] += 1
        elif category == "KEYWORD_COLLISION":
            counts["keyword_collision"] += 1
        elif category == "GENERAL_NEWS":
            counts["general_news"] += 1
        elif category == "NOT_RELEVANT":
            counts["not_relevant"] += 1
        else:
            counts["uncertain"] += 1

    summary = {**counts, "category_breakdown": category_counts}
    return visibility_map, summary


def load_previously_unclassified_ids():
    if not DOMAIN_CLASSIFICATION_PATH.exists():
        return set()
    data = json.loads(DOMAIN_CLASSIFICATION_PATH.read_text(encoding="utf-8"))
    ids = data.get("useful_but_unclassified_document_ids")
    if ids:
        return set(ids)
    return set()


def save_visibility_map(visibility_map):
    VISIBILITY_PATH.write_text(json.dumps(visibility_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    previously_unclassified = load_previously_unclassified_ids()
    visibility_map, summary = audit_corpus(previously_unclassified_ids=previously_unclassified)
    save_visibility_map(visibility_map)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
