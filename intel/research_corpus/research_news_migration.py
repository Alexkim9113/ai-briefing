# N-2 -- Research -> News migration, actually applied to documents.json's `category` field (not
# sidecar-only as in N-1). Follows the mandated sequence: AUDIT -> DRY_RUN -> DIFF -> VALIDATION
# -> BACKUP -> APPLY -> RE-AUDIT. Only the `category` field is ever changed; document_id and every
# other field (including content_hash, canonical_url, published, etc.) are preserved byte-for-byte
# so existing Claim/Event/Relation references by document_id never break.
import json
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import research_identity as ri  # noqa: E402

ROOT = HERE.parent.parent
DOCUMENTS_PATH = ROOT / "intel" / "documents.json"
BACKUP_DIR = HERE / "migration_backups"
MANIFEST_PATH = HERE / "research_news_migration_manifest.json"
MIGRATION_VERSION = "n2-research-news-migration-v1"


def _is_korean(text):
    return any("가" <= ch <= "힣" for ch in (text or ""))


def _target_news_category(doc):
    # This corpus's only two real NEWS categories are news_ko / news_global -- pick by whether
    # the title contains Hangul (the same signal already used for display routing elsewhere in
    # briefing.py). Never invents a third category.
    return "news_ko" if _is_korean(doc.get("title")) else "news_global"


def audit(documents):
    """Returns {doc_id: (status, id_type, id_value)} for every document -- the AUDIT step."""
    return {did: ri.classify_research_status(doc) for did, doc in documents.items()}


def build_dry_run(documents, audit_result):
    """DRY_RUN + DIFF -- compute the exact category changes without touching documents.json."""
    changes = []
    for did, (status, id_type, id_value) in audit_result.items():
        if status != "NEWS_ABOUT_RESEARCH":
            continue
        doc = documents[did]
        old_category = doc.get("category")
        new_category = _target_news_category(doc)
        changes.append({
            "document_id": did,
            "title": doc.get("title"),
            "old_category": old_category,
            "new_category": new_category,
            "reason": "RESEARCH 영역(papers/research)에 있었으나 실제 연구 identity(DOI/arXiv ID/저장소 출처) 없음 -- 연구를 소개한 뉴스",
        })
    return changes


def validate(documents, changes):
    """VALIDATION -- every change must point at a document that still exists, still has no real
    research identity, and whose document_id/other fields are untouched by this check itself."""
    errors = []
    doc_ids = set(documents.keys())
    for c in changes:
        did = c["document_id"]
        if did not in doc_ids:
            errors.append(f"{did}: document no longer exists")
            continue
        status, _, _ = ri.classify_research_status(documents[did])
        if status != "NEWS_ABOUT_RESEARCH":
            errors.append(f"{did}: re-check no longer classifies as NEWS_ABOUT_RESEARCH (status={status})")
        if c["new_category"] not in ("news_ko", "news_global"):
            errors.append(f"{did}: invalid target category {c['new_category']}")
    # No confirmed-RESEARCH document must ever appear in the change set.
    confirmed_ids = {did for did, (s, _, _) in audit(documents).items() if s == "RESEARCH_IDENTITY_CONFIRMED"}
    changed_ids = {c["document_id"] for c in changes}
    leaked = confirmed_ids & changed_ids
    if leaked:
        errors.append(f"RESEARCH_IDENTITY_CONFIRMED documents present in change set: {sorted(leaked)}")
    return errors


def backup(documents):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    backup_path = BACKUP_DIR / f"documents_before_{MIGRATION_VERSION}_{stamp}.json"
    backup_path.write_text(json.dumps(documents, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return backup_path


def apply(documents, changes):
    """APPLY -- mutate only the `category` field of the exact documents validated above. Returns
    the mutated dict (caller writes it back) and the applied manifest record."""
    before_snapshot = {c["document_id"]: documents[c["document_id"]].get("category") for c in changes}
    for c in changes:
        documents[c["document_id"]]["category"] = c["new_category"]
    after_snapshot = {c["document_id"]: documents[c["document_id"]].get("category") for c in changes}
    return before_snapshot, after_snapshot


def run_migration(dry_run=True):
    documents = json.loads(DOCUMENTS_PATH.read_text(encoding="utf-8"))
    audit_result = audit(documents)
    changes = build_dry_run(documents, audit_result)
    errors = validate(documents, changes)

    result = {
        "migration_version": MIGRATION_VERSION,
        "dry_run": dry_run,
        "change_count": len(changes),
        "validation_errors": errors,
        "changes": changes,
    }

    if errors:
        result["applied"] = False
        result["reason"] = "VALIDATION_FAILED -- no changes written"
        return result, documents

    if dry_run:
        result["applied"] = False
        result["reason"] = "DRY_RUN -- no changes written"
        return result, documents

    backup_path = backup(documents)
    before_snapshot, after_snapshot = apply(documents, changes)
    DOCUMENTS_PATH.write_text(json.dumps(documents, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    manifest = {
        "migration_version": MIGRATION_VERSION,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "backup_path": str(backup_path.relative_to(ROOT)),
        "changed_ids": [c["document_id"] for c in changes],
        "before_values": before_snapshot,
        "after_values": after_snapshot,
        "reason": "N-2 Research->News migration: 75 NEWS_ABOUT_RESEARCH documents reclassified from papers to news_ko/news_global",
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    re_audit_result = audit(documents)
    result["applied"] = True
    result["backup_path"] = str(backup_path.relative_to(ROOT))
    result["re_audit_status_counts"] = {}
    for _, (status, _, _) in re_audit_result.items():
        result["re_audit_status_counts"][status] = result["re_audit_status_counts"].get(status, 0) + 1
    return result, documents


def rollback(manifest_path=None):
    """Restores documents.json's `category` field for every changed_id to its before_value, using
    the manifest -- never a blind restore of the whole backup file (which could discard unrelated
    concurrent writes to documents.json)."""
    manifest_path = Path(manifest_path) if manifest_path else MANIFEST_PATH
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    documents = json.loads(DOCUMENTS_PATH.read_text(encoding="utf-8"))
    restored = []
    for did, old_category in manifest["before_values"].items():
        if did in documents:
            documents[did]["category"] = old_category
            restored.append(did)
    DOCUMENTS_PATH.write_text(json.dumps(documents, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return restored


if __name__ == "__main__":
    dry = "--apply" not in sys.argv
    result, _ = run_migration(dry_run=dry)
    print(json.dumps({k: v for k, v in result.items() if k != "changes"}, ensure_ascii=False, indent=2))
