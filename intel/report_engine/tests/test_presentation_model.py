# N-4 -- Presentation Contract tests. The Presentation Model must never alter report facts,
# claims, evidence, or statuses -- it only adds display-only metadata.
import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import report_engine as re_  # noqa: E402
import presentation_model as pm  # noqa: E402


def test_presentation_never_changes_report_facts():
    r = re_.build_report("intel_87210a61730c22b9")
    before = copy.deepcopy(r)
    pm.build_presentation(r)
    assert r == before


def test_presentation_never_mutates_sections_dict_identity():
    r = re_.build_report("intel_dbab7b01963396b5")
    before_sections = copy.deepcopy(r["sections"])
    p = pm.build_presentation(r)
    # every section object embedded in the presentation is the same content as the source report
    for entry in p["sections"]:
        assert entry["section"] == before_sections[entry["section_type"]]


def test_real_ai_energy_infra_key_signal_is_evidence_insufficient_not_invented():
    # The only real claim on this object is DESCRIPTIVE/OPEN -- no SUPPORTED/PARTIALLY_SUPPORTED
    # claim exists, so key_signal must never be invented as a confirmed signal.
    r = re_.build_report("intel_87210a61730c22b9")
    p = pm.build_presentation(r)
    assert p["executive_card"]["key_signal_status"] == "EVIDENCE_INSUFFICIENT"
    assert p["executive_card"]["key_signal"] == "EVIDENCE_INSUFFICIENT"


def test_real_ai_labor_key_signal_is_evidence_insufficient_not_invented():
    r = re_.build_report("intel_dbab7b01963396b5")
    p = pm.build_presentation(r)
    assert p["executive_card"]["key_signal_status"] == "EVIDENCE_INSUFFICIENT"


def test_executive_card_no_confirmed_signal_when_no_claims_at_all():
    fake_report = {
        "sections": {
            "KEY_CLAIMS": {"status": "NOT_APPLICABLE", "content_blocks": []},
            "CURRENT_STATE": {"content_blocks": ["x"]},
            "UNCERTAINTIES": {"content_blocks": []},
            "EVIDENCE_GAPS": {"content_blocks": []},
        },
        "readiness": "BLOCKED",
    }
    card = pm.build_executive_card(fake_report)
    assert card["key_signal_status"] == "NO_CONFIRMED_SIGNAL"
    assert card["key_signal"] == "NO_CONFIRMED_SIGNAL"


def test_executive_card_key_signal_present_only_with_real_supported_claim():
    fake_report = {
        "sections": {
            "KEY_CLAIMS": {"status": "AVAILABLE", "content_blocks": [
                {"text": "현재 확보된 증거는 X을(를) 뒷받침한다.", "claim_status": "SUPPORTED"}
            ]},
            "CURRENT_STATE": {"content_blocks": ["x"]},
            "UNCERTAINTIES": {"content_blocks": []},
            "EVIDENCE_GAPS": {"content_blocks": []},
        },
        "readiness": "READY",
    }
    card = pm.build_executive_card(fake_report)
    assert card["key_signal_status"] == "KEY_SIGNAL_PRESENT"
    assert card["key_signal"] == "현재 확보된 증거는 X을(를) 뒷받침한다."


def test_what_to_watch_never_predicts_future_event_only_lists_existing_gaps():
    fake_report = {"sections": {"EVIDENCE_GAPS": {"content_blocks": [
        {"gap_type": "MISSING_COUNTEREVIDENCE_SEARCH"}
    ]}}}
    watch = pm._what_to_watch(fake_report)
    assert watch == ["MISSING_COUNTEREVIDENCE_SEARCH"]


def test_what_to_watch_honest_when_no_gaps_exist():
    fake_report = {"sections": {"EVIDENCE_GAPS": {"content_blocks": []}}}
    watch = pm._what_to_watch(fake_report)
    assert "모니터링 대상 없음" in watch[0]


def test_statistics_chart_spec_never_has_forecast_or_attribution_overlay():
    block = {"indicator": "X", "geography": "USA", "period": "2010-2022",
             "source": "src_x", "trend_status": "NO_CLEAR_SIGNAL", "observation_count": 5}
    spec = pm.build_statistics_chart_spec(block)
    assert spec["forecast_line"] is False
    assert spec["ai_attribution_overlay"] is False


def test_statistics_chart_spec_table_when_single_observation():
    block = {"indicator": "X", "observation_count": 1}
    spec = pm.build_statistics_chart_spec(block)
    assert spec["visualization_type"] == "TABLE"


def test_evidence_status_badge_is_label_only_no_numeric_score():
    for status in ("SUPPORTED", "PARTIALLY_SUPPORTED", "CONTESTED", "INSUFFICIENT_EVIDENCE",
                   "OPEN", "WEAKENED", "REJECTED", "UNKNOWN", "SOMETHING_NEW"):
        badge = pm.evidence_status_badge(status)
        assert isinstance(badge, str)
        assert not isinstance(badge, (int, float))


def test_build_presentation_hides_not_applicable_sections():
    fake_report = {
        "report_id": "report_x_v1", "intelligence_id": "x", "topic": "X", "version": 1,
        "readiness": "BLOCKED",
        "sections": {
            "KEY_QUESTION": {"status": "NOT_APPLICABLE", "content_blocks": []},
            "CURRENT_STATE": {"status": "AVAILABLE", "content_blocks": ["x"]},
            "KEY_CLAIMS": {"status": "NOT_APPLICABLE", "content_blocks": []},
            "UNCERTAINTIES": {"status": "NOT_APPLICABLE", "content_blocks": []},
            "EVIDENCE_GAPS": {"status": "NOT_APPLICABLE", "content_blocks": []},
        },
    }
    p = pm.build_presentation(fake_report)
    by_type = {e["section_type"]: e for e in p["sections"]}
    assert by_type["KEY_QUESTION"]["visibility"] == "HIDDEN"
    assert by_type["CURRENT_STATE"]["visibility"] == "VISIBLE"


def test_real_sample_reports_round_trip_through_presentation_without_error():
    for iid in ("intel_87210a61730c22b9", "intel_dbab7b01963396b5"):
        r = re_.build_report(iid)
        p = pm.build_presentation(r)
        json.dumps(p, ensure_ascii=False)  # must be JSON-serializable
        assert p["report_id"] == r["report_id"]
        assert p["intelligence_id"] == r["intelligence_id"]


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
        except Exception as e:
            failed += 1
            print(f"ERROR {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
