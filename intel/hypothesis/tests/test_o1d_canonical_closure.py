# O-1D Sections 10-14 -- Legacy Status Engine audit regression test + Canonical Status Invariant
# test + extra Status Reversion Guard simulations. Manual def test_...(): + bare assert, no
# pytest/unittest, per project convention. Snapshot/restore discipline for hypotheses.json.
import ast
import atexit
import inspect
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))
sys.path.insert(0, str(PKG_DIR.parent / "claims"))
import hypothesis_model as m  # noqa: E402
import claim_model as cm  # noqa: E402

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


# --- 1. Static-analysis regression: upsert_hypothesis() never calls classify_status() directly ---
def test_upsert_hypothesis_never_calls_classify_status_directly():
    source = inspect.getsource(m.upsert_hypothesis)
    tree = ast.parse(source)
    func_def = tree.body[0]
    # Drop the docstring (its first statement is an Expr/Constant string) so prose mentions of
    # "classify_status()" inside the docstring don't trip this static check -- only actual Call
    # nodes in the executable body count.
    body = func_def.body
    if body and isinstance(body[0], ast.Expr) and isinstance(
            getattr(body[0], "value", None), (ast.Constant, ast.Str)):
        body = body[1:]
    called_names = set()
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called_names.add(node.func.id)
    assert "classify_status" not in called_names, (
        "REGRESSION: upsert_hypothesis() now contains a direct classify_status( call -- this "
        "would bypass the single canonical path (determine_canonical_status). See "
        "o1d_legacy_status_engine_audit.json CASE A.")
    assert "determine_canonical_status" in called_names, (
        "upsert_hypothesis() must call determine_canonical_status() to compute status")


# --- 2. Canonical Status Invariant (O-1D Section 13) ----------------------------------------------
# For every hypothesis currently in the real hypotheses.json, re-running it through
# upsert_hypothesis() as a no-op append (re-appending an id already present) must leave
# hyp["status"] exactly equal to a fresh determine_canonical_status(hyp)["final_status"].
def test_canonical_status_invariant_holds_for_every_real_hypothesis():
    _snapshot_real_files_once()
    real_hyps = json.loads(m.HYPOTHESES_PATH.read_text(encoding="utf-8"))
    all_claims = cm.load_claims()
    try:
        for hyp_id, hyp in real_hyps.items():
            # No-op append: re-append the first existing support id (or None if there is none).
            existing_support = hyp.get("supporting_evidence", [])
            noop_support = existing_support[0] if existing_support else None
            updated = m.upsert_hypothesis(dict(hyp), new_support_id=noop_support,
                                           all_claims=all_claims)
            fresh = m.determine_canonical_status(updated, all_claims=all_claims)
            assert updated["status"] == fresh["final_status"], (
                f"{hyp_id}: status={updated['status']!r} != fresh determine_canonical_status "
                f"final_status={fresh['final_status']!r}")
    finally:
        _restore_real_files()


# --- 3. Extra Status Reversion Guard simulations (O-1D Section 14) -------------------------------
# Appending a new UNRESOLVED evidence id to H3/H4-like hypotheses must not improperly upgrade
# status. (test_o1c_canonical_status.py already covers the generic unresolved-id-cannot-flip-to-
# SUPPORTED case; these two add H3/H4-specific simulations using their real requirement profiles.)
def test_h3_style_hypothesis_appending_unresolved_evidence_does_not_upgrade():
    _cleanup()
    claims = {
        "c1": {"claim_id": "c1", "claim_text": "Multi-factor demand growth. STATUS=OBSERVED.",
                "evidence_independence": "PRIMARY_OFFICIAL", "provenance": "https://example.org/c1",
                "created_from": "c1"},
    }
    h = m.new_hypothesis("AI_ENERGY_INFRA", "h3 style reversion test")
    h["hypothesis_code"] = "H3"
    h = m.upsert_hypothesis(h, new_support_id="c1", all_claims=claims)
    before = h["status"]
    h = m.upsert_hypothesis(h, new_support_id="legacy_ref:not_a_real_claim", all_claims=claims)
    assert h["status"] != "SUPPORTED" or before == "SUPPORTED", (
        f"H3-style hypothesis must not be upgraded to SUPPORTED by an unresolved id "
        f"(was {before}, now {h['status']})")
    assert "legacy_ref:not_a_real_claim" in h["canonical_status_diagnostics"][
        "unresolved_supporting_evidence"]
    _cleanup()


def test_h4_style_hypothesis_appending_unresolved_evidence_does_not_upgrade():
    _cleanup()
    claims = {
        "c1": {"claim_id": "c1",
                "claim_text": "Regional concentration. AI_ATTRIBUTION=AI_PARTIAL. STATUS=OBSERVED.",
                "evidence_independence": "PRIMARY_SOURCE", "provenance": "https://example.org/c1",
                "created_from": "c1"},
    }
    h = m.new_hypothesis("AI_ENERGY_INFRA", "h4 style reversion test")
    h["hypothesis_code"] = "H4"
    h = m.upsert_hypothesis(h, new_support_id="c1", all_claims=claims)
    before = h["status"]
    h = m.upsert_hypothesis(h, new_support_id="legacy_ref:another_unresolved", all_claims=claims)
    assert h["status"] != "SUPPORTED" or before == "SUPPORTED", (
        f"H4-style hypothesis must not be upgraded to SUPPORTED by an unresolved id "
        f"(was {before}, now {h['status']})")
    assert "legacy_ref:another_unresolved" in h["canonical_status_diagnostics"][
        "unresolved_supporting_evidence"]
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
