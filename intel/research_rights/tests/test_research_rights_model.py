import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))
import research_rights_model as m  # noqa: E402


def test_access_status_never_derived_from_rights_status():
    doc = {"document_id": "d1", "rights_mode": "LINK_ONLY"}
    record = m.classify_rights_for_document(doc)
    assert record["RIGHTS_STATUS"] == "LINK_ONLY"
    assert record["ACCESS_STATUS"] == "UNKNOWN_ACCESS"


def test_fulltext_storage_never_allowed_for_link_only():
    doc = {"document_id": "d1", "rights_mode": "LINK_ONLY"}
    record = m.classify_rights_for_document(doc)
    assert record["FULLTEXT_STORAGE_ALLOWED"] is False
    assert record["FULLTEXT_PUBLICATION_ALLOWED"] is False
    assert record["TRANSLATION_STORAGE_ALLOWED"] is False


def test_unknown_rights_mode_never_auto_upgraded_to_oa():
    doc = {"document_id": "d1", "rights_mode": "SOMETHING_NEW"}
    record = m.classify_rights_for_document(doc)
    assert record["RIGHTS_STATUS"] == "UNKNOWN_RIGHTS"
    assert record["FULLTEXT_STORAGE_ALLOWED"] is False


def test_all_18_fields_present():
    record = m.new_research_rights_record("d1")
    assert set(record.keys()) == set(m.RESEARCH_RECORD_FIELDS)


def test_never_writes_documents_json():
    src = (HERE.parent / "research_rights_model.py").read_text(encoding="utf-8")
    assert "DOCUMENTS_PATH" not in src or "write_text" not in src.split("DOCUMENTS_PATH")[-1][:200]


def test_real_corpus_matches_known_100_percent_link_only():
    sidecar = m.build_sidecar()
    assert all(v["RIGHTS_STATUS"] == "LINK_ONLY" for v in sidecar.values())


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
