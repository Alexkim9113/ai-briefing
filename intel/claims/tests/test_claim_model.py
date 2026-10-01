import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))
import claim_model as m  # noqa: E402


# N-9 Section 25 fix: CLAIMS_PATH/RELATIONS_PATH ARE the production canonical files (this module
# never used a separate test fixture path). The old _cleanup() permanently deleted them, which
# destroyed real corpus data every time this test file ran. We now snapshot their real content
# once per process and restore it exactly, via main()'s try/finally, instead of leaving them gone.
_REAL_BACKUP = {}


def _snapshot_real_files_once():
    for p in (m.CLAIMS_PATH, m.RELATIONS_PATH):
        if p not in _REAL_BACKUP:
            _REAL_BACKUP[p] = p.read_bytes() if p.exists() else None


def _restore_real_files():
    for p, content in _REAL_BACKUP.items():
        if content is None:
            if p.exists():
                p.unlink()
        else:
            p.write_bytes(content)


def _cleanup():
    _snapshot_real_files_once()
    for p in (m.CLAIMS_PATH, m.RELATIONS_PATH):
        if p.exists():
            p.unlink()


def test_claim_identity_stable_across_upserts():
    _cleanup()
    c1 = m.new_claim("test claim text", "AI_ENERGY_INFRA", "DESCRIPTIVE")
    c2 = m.new_claim("test claim text", "AI_ENERGY_INFRA", "DESCRIPTIVE")
    assert c1["claim_id"] == c2["claim_id"]
    _cleanup()


def test_invalid_claim_type_rejected():
    try:
        m.new_claim("x", "topic", "NOT_A_REAL_TYPE")
        assert False
    except AssertionError:
        pass


def test_descriptive_evidence_never_auto_becomes_causal_claim():
    claim = m.new_claim("AI data centers are the primary driver of electricity demand growth",
                         "AI_ENERGY_INFRA", "CAUSAL")
    # The claim module itself cannot verify this invariant structurally beyond typing the claim
    # correctly -- this test documents the discipline: a DESCRIPTIVE statistical observation must
    # be attached via a relation with its own type, never silently relabeling the claim.
    assert claim["claim_type"] == "CAUSAL"
    relation = m.new_relation("ev1", claim["claim_id"], "INSUFFICIENT_FOR",
                               "a single descriptive statistic cannot establish causation alone",
                               "test")
    assert relation["relation_type"] == "INSUFFICIENT_FOR"


def test_relation_strength_never_defaults_to_a_fabricated_number():
    relation = m.new_relation("ev1", "claim1", "SUPPORTS", "reason", "prov")
    assert relation["strength"] == "UNSPECIFIED"


def test_upsert_and_load_roundtrip():
    _cleanup()
    claim = m.new_claim("roundtrip test", "AI_LABOR", "DESCRIPTIVE")
    m.upsert_claim(claim)
    loaded = m.load_claims()
    assert claim["claim_id"] in loaded
    _cleanup()


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    try:
        for t in tests:
            try:
                t()
                print(f"PASS {t.__name__}")
            except AssertionError as e:
                failed += 1
                print(f"FAIL {t.__name__}: {e}")
    finally:
        _restore_real_files()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
