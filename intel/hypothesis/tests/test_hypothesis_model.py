import atexit
import sys
from contextlib import contextmanager
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))
sys.path.insert(0, str(PKG_DIR.parent / "claims"))
import hypothesis_model as m  # noqa: E402


# N-9 Section 25 fix: HYPOTHESES_PATH is the production canonical file. The old _cleanup()
# permanently deleted it. We now snapshot+restore instead (see claim_model's test for the
# identical fix and rationale).
_REAL_BACKUP = {}


def _snapshot_real_files_once():
    if m.HYPOTHESES_PATH not in _REAL_BACKUP:
        p = m.HYPOTHESES_PATH
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
    if m.HYPOTHESES_PATH.exists():
        m.HYPOTHESES_PATH.unlink()


# O-1F fix: see test_claim_model.py's identical fix for the full rationale -- main()'s
# try/finally never runs under pytest, so restore must also be registered at interpreter exit.
atexit.register(_restore_real_files)


# O-1F residual fix: atexit only fires once the WHOLE python process exits, which is too late
# when several of these test files run together in one pytest invocation -- an earlier file's
# _cleanup() left the canonical file deleted for the entire rest of the session, breaking later
# tests (in this file or others) that read it. Every mutating test must restore the real file
# immediately after itself, not just at process exit. atexit stays registered above purely as a
# last-resort backstop for an uncaught crash path.
@contextmanager
def _isolated_canonical_files():
    _cleanup()
    try:
        yield
    finally:
        _restore_real_files()


def test_identity_stable():
    h1 = m.new_hypothesis("AI_ENERGY_INFRA", "AI data centers drive electricity demand growth")
    h2 = m.new_hypothesis("AI_ENERGY_INFRA", "AI data centers drive electricity demand growth")
    assert h1["hypothesis_id"] == h2["hypothesis_id"]


def test_no_evidence_is_insufficient_not_open():
    assert m.classify_status([], []) == "INSUFFICIENT_EVIDENCE"


def test_counterevidence_never_deleted_only_appended():
    # O-1C: the canonical write path (determine_canonical_status) resolves evidence ids against
    # the real claims.json, so this test now uses actual resolvable claim_ids rather than
    # placeholder strings -- an unresolved placeholder id can no longer drive a SUPPORTED/
    # CONTESTED determination at all (see test_o1c_canonical_status.py's Unresolved Evidence ID
    # Guard tests), which is the intended O-1C behavior change.
    with _isolated_canonical_files():
        import claim_model as cm  # noqa: E402
        real_claim_id = next(iter(cm.load_claims().keys()))
        h = m.new_hypothesis("AI_ENERGY_INFRA", "test hyp")
        h = m.upsert_hypothesis(h, new_support_id=real_claim_id)
        assert h["status"] in ("SUPPORTED", "PARTIALLY_SUPPORTED"), h["status"]
        assert h["canonical_status_diagnostics"]["resolved_only_status_count_based"] == "SUPPORTED"
        h = m.upsert_hypothesis(h, new_counterevidence_id=real_claim_id)
        assert h["supporting_evidence"] == [real_claim_id], "support must still be present, never dropped"
        assert h["contradicting_evidence"] == [real_claim_id]
        assert h["canonical_status_diagnostics"]["resolved_only_status_count_based"] == "CONTESTED"


def test_unresolved_evidence_id_alone_cannot_reach_supported():
    # O-1C Section 8: a placeholder/legacy id that does not resolve to a real Claim record must
    # never, by itself, produce SUPPORTED.
    with _isolated_canonical_files():
        h = m.new_hypothesis("AI_ENERGY_INFRA", "test hyp 2")
        h = m.upsert_hypothesis(h, new_support_id="o1_counterevidence:does_not_exist_in_claims_json")
        assert h["status"] == "INSUFFICIENT_EVIDENCE", h["status"]
        assert h["canonical_status_diagnostics"]["unresolved_supporting_evidence"] == [
            "o1_counterevidence:does_not_exist_in_claims_json"]


def test_status_is_named_vocabulary_only():
    for s in ("SUPPORTED", "WEAKENED", "REJECTED", "CONTESTED"):
        assert s in m.HYPOTHESIS_STATUSES


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
