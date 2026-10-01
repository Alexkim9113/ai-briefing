import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))
import vault as m  # noqa: E402


def _lawful_test_record():
    # Explicit test-only lawful fixture per Te's instruction: no real copyrighted full text, a
    # synthetic placeholder standing in for "some private-only research content".
    return m.new_vault_record(
        record_id="vault_test_001", visibility="PRIVATE_RESEARCH",
        citation="Test Institute (2026). Synthetic Test Record for Vault Boundary Testing.",
        source="src_test_fixture", full_text="[TEST FIXTURE PLACEHOLDER -- not real content]",
        rights_status="PRIVATE_RESEARCH_ONLY",
    )


def test_public_view_never_includes_full_text_for_any_visibility():
    for visibility in m.VISIBILITY_VALUES:
        record = m.new_vault_record(f"r_{visibility}", visibility, "cite", "src",
                                     full_text="SECRET TEXT")
        view = m.get_public_view(record)
        assert "full_text" not in view


def test_operator_view_requires_explicit_true():
    record = _lawful_test_record()
    non_op_view = m.get_operator_view(record, actor_is_operator=False)
    assert "full_text" not in non_op_view
    op_view = m.get_operator_view(record, actor_is_operator=True)
    assert op_view["full_text"] == record["full_text"]


def test_invalid_visibility_rejected():
    try:
        m.new_vault_record("r1", "NOT_A_REAL_VISIBILITY", "cite", "src")
        assert False
    except AssertionError:
        pass


def test_upsert_and_load_roundtrip(tmp_path=None):
    record = _lawful_test_record()
    m.upsert_record(record)
    loaded = m.load_vault()
    assert record["record_id"] in loaded
    assert loaded[record["record_id"]]["visibility"] == "PRIVATE_RESEARCH"


def test_vault_is_logically_separate_from_documents_json():
    assert m.VAULT_PATH.name != "documents.json"
    assert m.VAULT_PATH.parent.name == "private_research_vault"


def test_restricted_reference_full_text_never_in_public_view():
    record = m.new_vault_record("r2", "RESTRICTED_REFERENCE", "cite", "src",
                                 full_text="RESTRICTED CONTENT")
    assert "full_text" not in m.get_public_view(record)


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
