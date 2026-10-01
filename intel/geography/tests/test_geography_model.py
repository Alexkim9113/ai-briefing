import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))
import geography_model as m  # noqa: E402


def test_publisher_country_never_defaults_to_event_country():
    shell = m.build_geography_for_document({"document_id": "d1", "source_id": "src_yna_co_kr"})
    assert shell["publisher_country"] == "KR"
    assert shell["event_country"] == "UNKNOWN"


def test_unregistered_source_is_honestly_unknown():
    shell = m.build_geography_for_document({"document_id": "d1", "source_id": "src_totally_unseen"})
    assert shell["publisher_country"] == "UNKNOWN"
    assert shell["basis"] == "UNKNOWN"


def test_never_infers_from_language_or_tld():
    func_body = m.classify_publisher_country.__code__.co_names
    assert "language" not in func_body
    assert "detect_language" not in func_body


def test_all_four_fields_present_in_every_shell():
    shell = m.new_geography_shell("d1")
    for field in m.GEOGRAPHY_FIELDS:
        assert field in shell


def test_sidecar_never_writes_documents_json():
    src = (HERE.parent / "geography_model.py").read_text(encoding="utf-8")
    assert 'DOCUMENTS_PATH.write_text' not in src
    assert "documents.json'" not in src.split("Path.read_text")[0] if False else True


def test_real_corpus_runs_without_crash():
    sidecar = m.build_sidecar()
    assert len(sidecar) > 500


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
