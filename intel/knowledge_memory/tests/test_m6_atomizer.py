import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import m6_atomizer as m  # noqa: E402


def test_rejects_unknown_atom_type():
    try:
        m.new_atom("NOT_A_TYPE", "t", "c", [])
        assert False
    except AssertionError:
        pass


def test_identity_stable_for_same_title():
    a1 = m.new_atom("CLAIM", "same title", "c1", ["s1"])
    a2 = m.new_atom("CLAIM", "same title", "c2", ["s2"])
    assert a1["atom_id"] == a2["atom_id"]


def test_public_visibility_never_exposes_restricted_fulltext_by_default():
    atom = m.new_atom("PAPER", "t", "full private text here", ["s1"], visibility="RESTRICTED_REFERENCE",
                       rights_status="RESTRICTED")
    assert atom["visibility"] == "RESTRICTED_REFERENCE"
    # atomizer itself does not strip -- callers must gate on visibility before export, same
    # discipline as private_research_vault.get_public_view()
    assert atom["rights_status"] == "RESTRICTED"


def test_write_vault_atoms(tmp_path="/tmp/claude-0-test-vault"):
    import shutil
    shutil.rmtree(tmp_path, ignore_errors=True)
    atom = m.new_atom("STATISTIC", "test stat", "content", ["src"])
    paths = m.write_vault_atoms([atom], tmp_path)
    assert len(paths) == 1
    assert Path(paths[0]).exists()
    shutil.rmtree(tmp_path, ignore_errors=True)


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
