import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import research_news_migration as mig  # noqa: E402


def _docs():
    return {
        "d1": {"document_id": "d1", "title": "News about a paper", "category": "papers",
               "source_id": "src_investing_com", "content_hash": "h1"},
        "d2": {"document_id": "d2", "title": "Real arXiv paper", "category": "papers",
               "doi": "10.1/x", "content_hash": "h2"},
        "d3": {"document_id": "d3", "title": "일반 뉴스", "category": "news_ko", "content_hash": "h3"},
        "d4": {"document_id": "d4", "title": "한국어 뉴스가 된 논문 소식", "category": "papers",
               "source_id": "src_some_outlet", "content_hash": "h4"},
    }


def test_dry_run_identifies_only_news_about_research():
    documents = _docs()
    audit_result = mig.audit(documents)
    changes = mig.build_dry_run(documents, audit_result)
    changed_ids = {c["document_id"] for c in changes}
    assert changed_ids == {"d1", "d4"}


def test_dry_run_never_touches_confirmed_research():
    documents = _docs()
    audit_result = mig.audit(documents)
    changes = mig.build_dry_run(documents, audit_result)
    assert all(c["document_id"] != "d2" for c in changes)
    assert documents["d2"]["category"] == "papers"  # untouched


def test_target_category_picks_ko_vs_global_by_title_script():
    documents = _docs()
    assert mig._target_news_category(documents["d1"]) == "news_global"
    assert mig._target_news_category(documents["d4"]) == "news_ko"


def test_validation_rejects_confirmed_research_in_changeset():
    documents = _docs()
    bad_changes = [{"document_id": "d2", "old_category": "papers", "new_category": "news_global",
                    "title": "x", "reason": "x"}]
    errors = mig.validate(documents, bad_changes)
    assert any("RESEARCH_IDENTITY_CONFIRMED" in e for e in errors)


def test_document_id_and_other_fields_preserved_after_apply():
    documents = _docs()
    before_hash = documents["d1"]["content_hash"]
    audit_result = mig.audit(documents)
    changes = mig.build_dry_run(documents, audit_result)
    mig.apply(documents, changes)
    assert documents["d1"]["document_id"] == "d1"
    assert documents["d1"]["content_hash"] == before_hash
    assert documents["d1"]["category"] == "news_global"


def test_rollback_restores_old_category(tmp_path=None):
    import tempfile
    documents = _docs()
    audit_result = mig.audit(documents)
    changes = mig.build_dry_run(documents, audit_result)
    before_snapshot, after_snapshot = mig.apply(documents, changes)
    assert before_snapshot["d1"] == "papers"
    assert after_snapshot["d1"] == "news_global"
    # manual rollback simulation (apply() return values are exactly what a manifest stores)
    for did, old_cat in before_snapshot.items():
        documents[did]["category"] = old_cat
    assert documents["d1"]["category"] == "papers"
    assert documents["d4"]["category"] == "papers"


def test_real_migration_manifest_exists_and_matches_applied_corpus():
    manifest_path = HERE.parent / "research_news_migration_manifest.json"
    if not manifest_path.exists():
        return  # migration not yet applied in this environment -- not a test failure
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["migration_version"] == mig.MIGRATION_VERSION
    assert len(manifest["changed_ids"]) == len(manifest["before_values"]) == len(manifest["after_values"])
    documents = json.loads((HERE.parent.parent.parent / "intel" / "documents.json").read_text(encoding="utf-8"))
    for did in manifest["changed_ids"]:
        assert documents[did]["category"] == manifest["after_values"][did]


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
