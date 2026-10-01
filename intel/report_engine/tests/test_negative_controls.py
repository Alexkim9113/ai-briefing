# N-3 Section 30 -- deliberately dangerous inputs the Report Engine must refuse to render as fact.
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import report_engine as re_  # noqa: E402
import schema as sc  # noqa: E402


def test_ai_datacenter_caused_us_power_crisis_not_asserted_without_evidence():
    # The AI_ENERGY_INFRA object's real claim is DESCRIPTIVE/OPEN -- no SUPPORTED causal claim
    # exists in this corpus. If someone tried to render a CAUSAL claim with this text and status
    # OPEN, the renderer must fall back to the insufficient-evidence template, never assert it.
    claim = {"status": "OPEN", "claim_type": "CAUSAL",
             "scope": "AI 데이터센터 때문에 미국 전력 위기가 발생했다"}
    sentence = re_.render_claim_sentence(claim)
    assert sentence == sc.CLAIM_STATUS_TEMPLATES["INSUFFICIENT_EVIDENCE"]
    assert "발생했다" not in sentence


def test_ai_reduced_labor_participation_not_asserted_from_general_statistics_alone():
    # AI_LABOR's only real claim is a DESCRIPTIVE labor-force-participation series with no
    # AI-attribution relation connected -- a CAUSAL claim asserting AI reduced participation must
    # never render as fact even if someone constructs one with status OPEN/INSUFFICIENT_EVIDENCE.
    claim = {"status": "INSUFFICIENT_EVIDENCE", "claim_type": "CAUSAL",
             "scope": "AI가 노동참가율을 감소시켰다"}
    sentence = re_.render_claim_sentence(claim)
    assert sentence == sc.CLAIM_STATUS_TEMPLATES["INSUFFICIENT_EVIDENCE"]


def test_real_ai_labor_report_contains_no_causal_ai_assertion():
    r = re_.build_report("intel_dbab7b01963396b5")
    key_claims_text = " ".join(b.get("text", "") for b in r["sections"]["KEY_CLAIMS"]["content_blocks"])
    assert "감소시켰다" not in key_claims_text
    assert "AI 때문에" not in key_claims_text


def test_real_ai_energy_infra_report_contains_no_unsupported_crisis_claim():
    r = re_.build_report("intel_87210a61730c22b9")
    key_claims_text = " ".join(b.get("text", "") for b in r["sections"]["KEY_CLAIMS"]["content_blocks"])
    assert "위기가 발생했다" not in key_claims_text
    assert "전력망 위기를 만들고 있다" not in key_claims_text


def test_metaxis_point_with_causal_marker_and_no_grounding_excluded_from_public():
    r = re_.build_report("intel_87210a61730c22b9",
                         mx_point_text="AI 데이터센터 때문에 미국 전력 위기가 발생했다.",
                         mx_provenance={"grounding_status": "UNSUPPORTED_INTERPRETATION",
                                        "interpretation_type": "CAUSAL"})
    pub = re_.build_public_view(r)
    assert pub["sections"]["METAXIS_POINT"]["content_blocks"] == []
    operator = re_.build_operator_view(r)
    # Operator CAN still see it (Section 9: Operator-visible, Public-excluded)
    assert len(operator["sections"]["METAXIS_POINT"]["content_blocks"]) == 1


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
