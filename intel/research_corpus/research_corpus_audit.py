# N-1 -- Research vs News corpus audit. Uses research_identity.classify_research_status() against
# the real 601-doc corpus to (a) report real RESEARCH_IDENTITY_CONFIRMED / NEWS_ABOUT_RESEARCH /
# NO_IDENTITY_NEWS counts, (b) list every NEWS_ABOUT_RESEARCH document (the actual
# RESEARCH -> NEWS reclassification set), and (c) report duplicate-identity groups. Never deletes
# or mutates documents.json -- writes separate result artifacts only.
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import research_identity as ri  # noqa: E402

ROOT = HERE.parent.parent
DOCUMENTS_PATH = ROOT / "intel" / "documents.json"

RESULT_PATH = HERE / "research_corpus_audit_result.json"
MIGRATION_PATH = HERE / "research_news_migration_result.json"
COVERAGE_PATH = HERE / "research_source_coverage_result.json"


def run_audit():
    documents = json.loads(DOCUMENTS_PATH.read_text(encoding="utf-8"))

    status_counts = {}
    id_type_counts = {}
    migration_records = []  # RESEARCH-tagged docs with no real identity -> reclassify to NEWS
    confirmed_but_not_research_tagged = []  # real identity found, but category wasn't papers/research

    for doc_id, doc in documents.items():
        status, id_type, id_value = ri.classify_research_status(doc)
        status_counts[status] = status_counts.get(status, 0) + 1
        if id_type:
            id_type_counts[id_type] = id_type_counts.get(id_type, 0) + 1

        category = doc.get("category") or ""
        if status == "NEWS_ABOUT_RESEARCH":
            migration_records.append({
                "document_id": doc_id, "title": doc.get("title"), "source_id": doc.get("source_id"),
                "old_category": category, "new_category": "NEWS",
                "reason": "RESEARCH 영역에 태그되어 있으나 실제 연구 identity(DOI/arXiv ID/저장소 출처) 없음",
            })
        elif status == "RESEARCH_IDENTITY_CONFIRMED" and category not in ("papers", "research"):
            confirmed_but_not_research_tagged.append({
                "document_id": doc_id, "title": doc.get("title"), "category": category,
                "identity_type": id_type,
            })

    dup_groups = ri.group_by_research_identity(documents)
    duplicate_report = [{"identity_key": k, "document_ids": v} for k, v in dup_groups.items()]

    source_coverage = {}
    for doc_id, doc in documents.items():
        if (doc.get("category") or "") in ("papers", "research"):
            sid = doc.get("source_id") or "UNKNOWN"
            source_coverage.setdefault(sid, {"total": 0, "RESEARCH_IDENTITY_CONFIRMED": 0,
                                              "NEWS_ABOUT_RESEARCH": 0, "NO_IDENTITY_NEWS": 0})
            status, _, _ = ri.classify_research_status(doc)
            source_coverage[sid]["total"] += 1
            source_coverage[sid][status] += 1

    return {
        "total_documents": len(documents),
        "status_counts": status_counts,
        "identity_type_counts": id_type_counts,
        "news_about_research_count": len(migration_records),
        "confirmed_identity_but_not_research_tagged_count": len(confirmed_but_not_research_tagged),
        "duplicate_identity_group_count": len(duplicate_report),
    }, migration_records, duplicate_report, confirmed_but_not_research_tagged, source_coverage


def main():
    summary, migration_records, duplicate_report, confirmed_but_not_research_tagged, source_coverage = run_audit()

    RESULT_PATH.write_text(json.dumps({
        **summary,
        "duplicate_identity_groups": duplicate_report,
        "confirmed_identity_but_not_research_tagged": confirmed_but_not_research_tagged,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    MIGRATION_PATH.write_text(json.dumps({
        "migration_count": len(migration_records),
        "migrations": migration_records,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    COVERAGE_PATH.write_text(json.dumps(source_coverage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nNEWS_ABOUT_RESEARCH examples (first 10 of {len(migration_records)}):")
    for rec in migration_records[:10]:
        print(f"  - [{rec['document_id']}] {rec['title']} (source={rec['source_id']})")


if __name__ == "__main__":
    main()
