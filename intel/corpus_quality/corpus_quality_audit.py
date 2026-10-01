# M.5F SECTION 21 -- Corpus Quality audit. Classifies each document into one of 4 honest
# buckets Te's spec names: A) USEFUL_BUT_UNCLASSIFIED, B) METADATA_POOR, C) DUPLICATE_OR_DERIVATIVE,
# D) LOW_INTELLIGENCE_VALUE. D is NEVER auto-deleted (separate governance per Te's explicit
# instruction) -- this module only classifies and reports counts; it never writes
# documents.json and never removes anything.
#
# Reuses, rather than reforks, two already-built M.5F modules: topic_classification's
# DOMAIN_UNKNOWN result (bucket A) and this corpus's own real content_hash field (bucket C,
# the only dedup signal this schema already carries).
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
DOCUMENTS_PATH = INTEL_DIR / "documents.json"
OUT_PATH = HERE / "corpus_quality_result.json"

sys.path.insert(0, str(INTEL_DIR / "topic_classification"))
import domain_classifier as _domain_classifier  # noqa: E402

# A document's title this short is a conservative, documented signal of low intelligence value
# (e.g. a bare market-ticker digest like "[개장전특징주]엔비디아, 마이크론, 테슬라" or a one-word
# stub) -- NOT a judgment that the topic is unimportant, only that this particular document
# carries too little content to analyze. Chosen from direct inspection of this corpus's own
# shortest real titles, not an abstract guess.
_SHORT_TITLE_CHAR_THRESHOLD = 12


def load_documents(documents_path=DOCUMENTS_PATH):
    return json.loads(Path(documents_path).read_text(encoding="utf-8"))


def _find_duplicate_content_hashes(documents):
    counts = Counter(doc.get("content_hash") for doc in documents.values())
    return {h for h, c in counts.items() if h and c > 1}


def classify_document_quality(doc, duplicate_hashes, domain_result=None):
    """Returns a list of bucket labels (a document can honestly land in more than one, e.g.
    both METADATA_POOR and LOW_INTELLIGENCE_VALUE) plus the evidence for each. Returns
    "GOOD_QUALITY_NO_ISSUE" (not a Te-named bucket, but the honest default) when none apply."""
    buckets = []

    if doc.get("content_hash") in duplicate_hashes:
        buckets.append({"bucket": "DUPLICATE_OR_DERIVATIVE",
                         "evidence": f"content_hash {doc.get('content_hash')!r} shared by >1 document"})

    missing = [f for f in ("title", "canonical_url", "published") if not doc.get(f)]
    if missing:
        buckets.append({"bucket": "METADATA_POOR", "evidence": f"missing fields: {missing}"})

    title = doc.get("title") or ""
    if 0 < len(title) < _SHORT_TITLE_CHAR_THRESHOLD:
        buckets.append({"bucket": "LOW_INTELLIGENCE_VALUE",
                         "evidence": f"title shorter than {_SHORT_TITLE_CHAR_THRESHOLD} chars: {title!r}"})

    if domain_result is None:
        domain_result = _domain_classifier.classify_document(doc)
    if not domain_result["domains"] and not missing:
        # Genuinely useful-looking document (real title/url/date) that simply has no domain
        # signal yet -- distinct from METADATA_POOR, where the document itself is thin.
        buckets.append({"bucket": "USEFUL_BUT_UNCLASSIFIED",
                         "evidence": "has real title/url/date but domain_classifier found no "
                                     "EXISTING_FIELD/SOURCE_TOPIC_SUFFIX/TITLE_KEYWORD signal"})

    if not buckets:
        return [{"bucket": "GOOD_QUALITY_NO_ISSUE", "evidence": None}]
    return buckets


def build_quality_audit(documents=None):
    documents = documents if documents is not None else load_documents()
    duplicate_hashes = _find_duplicate_content_hashes(documents)

    per_document = {}
    bucket_counts = Counter()
    for did, doc in documents.items():
        result = classify_document_quality(doc, duplicate_hashes)
        per_document[did] = result
        for entry in result:
            bucket_counts[entry["bucket"]] += 1

    return {
        "note": (
            "M.5F Section 21 Corpus Quality audit. A document may land in more than one bucket "
            "(e.g. METADATA_POOR + LOW_INTELLIGENCE_VALUE) -- bucket counts can sum to more than "
            "total_documents. LOW_INTELLIGENCE_VALUE and DUPLICATE_OR_DERIVATIVE documents are "
            "NEVER auto-deleted by this module or any other -- deletion is separate governance, "
            "per Te's explicit instruction."
        ),
        "total_documents": len(documents),
        "bucket_counts": dict(bucket_counts),
        "duplicate_content_hash_groups": len(duplicate_hashes),
        "per_document": per_document,
    }


def main():
    audit = build_quality_audit()
    OUT_PATH.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH}: total={audit['total_documents']} buckets={audit['bucket_counts']}")


if __name__ == "__main__":
    main()
