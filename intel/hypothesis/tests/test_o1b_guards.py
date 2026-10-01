# O-1B Sections 9-12 -- tests for the Deterministic Evidence Sufficiency Rules and the four
# guards (Forecast, AI Attribution, Derivative Evidence, Industry Self-Report). Manual
# def test_...(): + bare assert, no pytest/unittest, per project convention.
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))
import hypothesis_model as m  # noqa: E402
import evidence_evaluation as ee  # noqa: E402


def _claim(claim_id, text, evidence_independence=None, forecast_fields=None, created_from=None,
           provenance=None):
    c = {"claim_id": claim_id, "claim_text": text, "created_from": created_from or claim_id,
         "provenance": provenance or f"https://example.org/{claim_id}"}
    if evidence_independence:
        c["evidence_independence"] = evidence_independence
    if forecast_fields:
        c["forecast_fields"] = forecast_fields
    return c


def _hyp(code, supporting, contradicting=None, requires_ai_attribution=False, requires_current_state=True):
    h = m.new_hypothesis("TEST_TOPIC", f"synthetic hypothesis for {code}")
    h["hypothesis_code"] = code
    h["supporting_evidence"] = supporting
    h["contradicting_evidence"] = contradicting or []
    req = {code: {"requires_ai_attribution": requires_ai_attribution,
                  "requires_current_state": requires_current_state, "note": "test"}}
    return h, req


# --- Forecast Guard (Section 9) -----------------------------------------------------------------
def test_forecast_only_evidence_cannot_support_current_state_hypothesis():
    claims = {
        "c1": _claim("c1", "Global demand will be X by 2030. STATUS=FORECAST.",
                     evidence_independence="ACADEMIC_RESEARCH"),
    }
    hyp, req = _hyp("TFG1", ["c1"], requires_current_state=True)
    result = m.evaluate_hypothesis_sufficiency(hyp, claims, requirements=req)
    assert result["base_status_count_based"] == "SUPPORTED"
    assert result["recommended_status"] == "INSUFFICIENT_EVIDENCE", result["recommended_status"]
    failed = [g for g in result["guard_trail"] if g["guard"] == "FORECAST_GUARD"]
    assert failed[0]["result"] == "FAILED"


def test_forecast_guard_does_not_fire_when_hypothesis_is_not_about_current_state():
    claims = {
        "c1": _claim("c1", "Global demand will be X by 2030. STATUS=FORECAST.",
                     evidence_independence="ACADEMIC_RESEARCH"),
    }
    hyp, req = _hyp("TFG2", ["c1"], requires_current_state=False)
    result = m.evaluate_hypothesis_sufficiency(hyp, claims, requirements=req)
    g = [g for g in result["guard_trail"] if g["guard"] == "FORECAST_GUARD"][0]
    assert g["result"] == "PASSED"


# --- AI Attribution Guard (Section 10) -----------------------------------------------------------
def test_data_center_general_evidence_cannot_strongly_support_ai_specific_hypothesis():
    claims = {
        "c1": _claim("c1", "Data centers in general grew. STATUS=OBSERVED. AI_ATTRIBUTION=INDIRECT.",
                     evidence_independence="ACADEMIC_RESEARCH"),
    }
    hyp, req = _hyp("TAG1", ["c1"], requires_ai_attribution=True)
    result = m.evaluate_hypothesis_sufficiency(hyp, claims, requirements=req)
    assert result["base_status_count_based"] == "SUPPORTED"
    assert result["recommended_status"] != "SUPPORTED", result["recommended_status"]
    g = [g for g in result["guard_trail"] if g["guard"] == "AI_ATTRIBUTION_GUARD"][0]
    assert g["result"] == "FAILED"


def test_ai_partial_attribution_evidence_passes_the_guard():
    claims = {
        "c1": _claim("c1", "AI is named as a driver. STATUS=OBSERVED. AI_ATTRIBUTION=PARTIAL.",
                     evidence_independence="ACADEMIC_RESEARCH"),
    }
    hyp, req = _hyp("TAG2", ["c1"], requires_ai_attribution=True)
    result = m.evaluate_hypothesis_sufficiency(hyp, claims, requirements=req)
    g = [g for g in result["guard_trail"] if g["guard"] == "AI_ATTRIBUTION_GUARD"][0]
    assert g["result"] == "PASSED"


# --- Derivative Evidence Guard (Section 11) ------------------------------------------------------
def test_multiple_articles_citing_same_original_source_do_not_count_as_independent():
    claims = {
        f"c{i}": _claim(f"c{i}", "News coverage of the IEA report. STATUS=OBSERVED. AI_ATTRIBUTION=PARTIAL.",
                        evidence_independence="DERIVATIVE_REPORTING", created_from="IEA_ORIGINAL_REPORT")
        for i in range(1, 6)
    }
    claims["c0"] = _claim("c0", "The original IEA report. STATUS=OBSERVED. AI_ATTRIBUTION=PARTIAL.",
                           evidence_independence="ACADEMIC_RESEARCH", created_from="IEA_ORIGINAL_REPORT")
    hyp, req = _hyp("TDG1", list(claims.keys()))
    result = m.evaluate_hypothesis_sufficiency(hyp, claims, requirements=req)
    distinct = m._distinct_origin_count(result["supporting_evaluation"])
    assert distinct == 1, f"6 items citing one IEA original must collapse to 1 independent unit, got {distinct}"
    assert result["base_status_count_based"] == "SUPPORTED"
    assert result["recommended_status"] == "PARTIALLY_SUPPORTED", result["recommended_status"]
    g = [g for g in result["guard_trail"] if g["guard"] == "DERIVATIVE_EVIDENCE_GUARD"][0]
    assert g["result"] == "FAILED"


def test_independent_origins_are_not_collapsed():
    claims = {
        "c1": _claim("c1", "IEA report finding. STATUS=OBSERVED. AI_ATTRIBUTION=PARTIAL.",
                     evidence_independence="ACADEMIC_RESEARCH", created_from="IEA_REPORT"),
        "c2": _claim("c2", "LBNL report finding. STATUS=OBSERVED. AI_ATTRIBUTION=PARTIAL.",
                     evidence_independence="ACADEMIC_RESEARCH", created_from="LBNL_REPORT"),
    }
    hyp, req = _hyp("TDG2", ["c1", "c2"])
    result = m.evaluate_hypothesis_sufficiency(hyp, claims, requirements=req)
    distinct = m._distinct_origin_count(result["supporting_evaluation"])
    assert distinct == 2


# --- Industry Self-Report Guard (Section 12) ------------------------------------------------------
def test_industry_self_report_alone_cannot_reach_supported():
    claims = {
        "c1": _claim("c1", "NVIDIA reports its own efficiency gains. STATUS=OBSERVED. AI_ATTRIBUTION=DIRECT.",
                     evidence_independence="INDUSTRY_SELF_REPORT (vendor press release)"),
    }
    hyp, req = _hyp("TISR1", ["c1"])
    result = m.evaluate_hypothesis_sufficiency(hyp, claims, requirements=req)
    assert result["base_status_count_based"] == "SUPPORTED"
    assert result["recommended_status"] != "SUPPORTED", result["recommended_status"]
    g = [g for g in result["guard_trail"] if g["guard"] == "INDUSTRY_SELF_REPORT_GUARD"][0]
    assert g["result"] == "FAILED"


def test_source_tier_parser_does_not_misfire_on_negated_phrasing():
    # Regression guard for a real bug found this phase: "ACADEMIC_RESEARCH (... not a corporate
    # self-report)" must classify as PRIMARY_RESEARCH, never INDUSTRY_SELF_REPORT.
    claim = _claim("c1", "x", evidence_independence="ACADEMIC_RESEARCH (DOE-funded national lab report, not a corporate self-report)")
    assert ee.classify_source_tier(claim) == "PRIMARY_RESEARCH"


# --- No single collapsed score (Section 7 hard constraint) ----------------------------------------
def test_evaluation_output_is_never_a_single_number():
    claims = {"c1": _claim("c1", "x. STATUS=OBSERVED. AI_ATTRIBUTION=PARTIAL.", evidence_independence="ACADEMIC_RESEARCH")}
    rec = ee.evaluate_claim(claims["c1"], claims)
    for forbidden in ("score", "quality_score", "confidence", "weight"):
        assert forbidden not in rec, f"evaluation record must never carry a collapsed {forbidden!r} field"
    assert set(rec.keys()) == {"claim_id", "SOURCE_TIER", "EVIDENCE_DIRECTNESS", "ATTRIBUTION_STRENGTH",
                                "TEMPORAL_TYPE", "INDEPENDENCE"}


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
