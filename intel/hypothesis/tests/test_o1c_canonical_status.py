# O-1C Sections 21-25 -- the 5 required regression tests proving the single canonical status
# path (determine_canonical_status, wired into upsert_hypothesis) actually closes the O-1B gap:
# appending evidence through the real write path must never silently bypass the quality-aware
# evaluation layer. Manual def test_...(): + bare assert, no pytest/unittest, per project
# convention. Snapshot/restore discipline for hypotheses.json (N-9B pattern), never destroying
# canonical data.
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))
import hypothesis_model as m  # noqa: E402

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


def _claim(claim_id, text, evidence_independence=None, forecast_fields=None, created_from=None,
           provenance=None):
    c = {"claim_id": claim_id, "claim_text": text, "created_from": created_from or claim_id,
         "provenance": provenance or f"https://example.org/{claim_id}"}
    if evidence_independence:
        c["evidence_independence"] = evidence_independence
    if forecast_fields:
        c["forecast_fields"] = forecast_fields
    return c


# --- 1. Status Reversion test (Section 21) -------------------------------------------------------
# A hypothesis that is PARTIALLY_SUPPORTED because its evidence quality was downgraded by the
# guards must NOT flip to SUPPORTED just because one more (unresolved, low-quality) evidence id
# is appended through the real upsert_hypothesis() write path.
def test_status_reversion_guard_appending_unresolved_evidence_does_not_flip_to_supported():
    _cleanup()
    claims = {
        "c1": _claim("c1", "AI data centers add load. AI_ATTRIBUTION=PARTIAL. STATUS=OBSERVED.",
                     evidence_independence="INDUSTRY_SELF_REPORT"),
    }
    h = m.new_hypothesis("AI_ENERGY_INFRA", "status reversion test hyp")
    h["hypothesis_code"] = "TSR1"
    h = m.upsert_hypothesis(h, new_support_id="c1", all_claims=claims)
    before = m.determine_canonical_status(h, all_claims=claims)
    # Industry-self-report-only evidence cannot be a clean SUPPORTED -- it should already be
    # downgraded by the guard layer before we even append the unresolved id.
    assert before["final_status"] != "REJECTED"
    h["status"] = before["final_status"]
    assert h["status"] in ("PARTIALLY_SUPPORTED", "INSUFFICIENT_EVIDENCE"), h["status"]
    pre_append_status = h["status"]

    # Now append a second, UNRESOLVED evidence id (does not resolve to any real claim) through
    # the real write path.
    h["canonical_status_diagnostics"] = before
    h2 = m.upsert_hypothesis(h, new_support_id="legacy_unresolved_ref:not_a_real_claim",
                              all_claims=claims)
    final = m.determine_canonical_status(h2, all_claims=claims)
    assert final["final_status"] != "SUPPORTED", (
        f"REGRESSION: appending an unresolved evidence id flipped status to SUPPORTED "
        f"(was {pre_append_status}, now {final['final_status']})")
    assert "legacy_unresolved_ref:not_a_real_claim" in final["unresolved_supporting_evidence"]
    _cleanup()


# --- 2. Derivative Duplication test (Section 22) -------------------------------------------------
def test_derivative_duplicate_origin_evidence_does_not_inflate_status():
    _cleanup()
    claims = {
        "c1": _claim("c1", "X. AI_ATTRIBUTION=DIRECT. STATUS=OBSERVED.",
                     evidence_independence="PRIMARY_SOURCE", created_from="SAME_ORIGIN_DOC"),
        "c2": _claim("c2", "X restated. AI_ATTRIBUTION=DIRECT. STATUS=OBSERVED.",
                     evidence_independence="PRIMARY_SOURCE", created_from="SAME_ORIGIN_DOC"),
        "c3": _claim("c3", "X restated again. AI_ATTRIBUTION=DIRECT. STATUS=OBSERVED.",
                     evidence_independence="PRIMARY_SOURCE", created_from="SAME_ORIGIN_DOC"),
    }
    h = m.new_hypothesis("AI_ENERGY_INFRA", "derivative duplication test hyp")
    h["hypothesis_code"] = "TDD1"
    h = m.upsert_hypothesis(h, new_support_id="c1", all_claims=claims)
    h = m.upsert_hypothesis(h, new_support_id="c2", all_claims=claims)
    h = m.upsert_hypothesis(h, new_support_id="c3", all_claims=claims)
    final = m.determine_canonical_status(h, all_claims=claims)
    assert final["final_status"] != "SUPPORTED", (
        "3 derivative (same-origin) items should not out-rank 1 independent origin into SUPPORTED")
    guard = [g for g in final["guard_trail"] if g["guard"] == "DERIVATIVE_EVIDENCE_GUARD"][0]
    assert guard["result"] == "FAILED", guard
    _cleanup()


# --- 3. Forecast-Only test (Section 23) ------------------------------------------------------------
def test_forecast_only_evidence_cannot_support_current_state_hypothesis_via_write_path():
    _cleanup()
    claims = {
        "c1": _claim("c1", "Demand will reach X by 2030. AI_ATTRIBUTION=DIRECT. STATUS=FORECAST.",
                     evidence_independence="ACADEMIC_RESEARCH",
                     forecast_fields={"observed_or_projected": "FORECAST"}),
    }
    h = m.new_hypothesis("AI_ENERGY_INFRA", "forecast only test hyp")
    h["hypothesis_code"] = "H1"  # reuse H1's real requirement profile: requires_current_state=True
    h = m.upsert_hypothesis(h, new_support_id="c1", all_claims=claims)
    final = m.determine_canonical_status(h, all_claims=claims)
    assert final["final_status"] == "INSUFFICIENT_EVIDENCE", final["final_status"]
    guard = [g for g in final["guard_trail"] if g["guard"] == "FORECAST_GUARD"][0]
    assert guard["result"] == "FAILED", guard
    _cleanup()


# --- 4. General Data Center test (Section 24) -------------------------------------------------------
def test_general_data_center_evidence_cannot_strongly_support_ai_specific_hypothesis_via_write_path():
    _cleanup()
    claims = {
        "c1": _claim("c1", "Data center load grew. AI_ATTRIBUTION=INDIRECT. STATUS=OBSERVED.",
                     evidence_independence="PRIMARY_SOURCE"),
    }
    h = m.new_hypothesis("AI_ENERGY_INFRA", "general dc test hyp")
    h["hypothesis_code"] = "H1"  # H1 requires_ai_attribution=True
    h = m.upsert_hypothesis(h, new_support_id="c1", all_claims=claims)
    final = m.determine_canonical_status(h, all_claims=claims)
    assert final["final_status"] != "SUPPORTED", final["final_status"]
    guard = [g for g in final["guard_trail"] if g["guard"] == "AI_ATTRIBUTION_GUARD"][0]
    assert guard["result"] == "FAILED", guard
    _cleanup()


# --- 5. Industry Self-Report test (Section 25) -------------------------------------------------------
def test_single_industry_self_report_cannot_alone_produce_strong_verified_status_via_write_path():
    _cleanup()
    claims = {
        "c1": _claim("c1", "Our efficiency improved. AI_ATTRIBUTION=DIRECT. STATUS=OBSERVED.",
                     evidence_independence="INDUSTRY_SELF_REPORT (corporate blog post)"),
    }
    h = m.new_hypothesis("AI_ENERGY_INFRA", "industry self report test hyp")
    h["hypothesis_code"] = "TISR1"
    h = m.upsert_hypothesis(h, new_support_id="c1", all_claims=claims)
    final = m.determine_canonical_status(h, all_claims=claims)
    assert final["final_status"] != "SUPPORTED", final["final_status"]
    guard = [g for g in final["guard_trail"] if g["guard"] == "INDUSTRY_SELF_REPORT_GUARD"][0]
    assert guard["result"] == "FAILED", guard
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
    import sys as _sys
    _sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
