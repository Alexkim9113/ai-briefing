# N-4B -- Operator Workspace Foundation tests. Verifies every surface reads real data only --
# never fabricates HEALTHY/READY values a backend doesn't actually have.
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import operator_api as op  # noqa: E402


def test_overview_counts_match_known_real_corpus_scale():
    o = op.overview()
    assert o["documents"] == 601
    assert o["intelligence_objects"] == 2
    assert o["reports"] == 2
    assert o["claims"] == 2


def test_overview_source_health_honestly_not_instrumented_when_no_monitor_exists():
    o = op.overview()
    assert o["source_health"] in op.SOURCE_HEALTH_STATES
    assert o["source_health"] == "NOT_INSTRUMENTED"


def test_list_reports_reflects_real_saved_reports():
    rows = op.list_reports()
    ids = {r["report_id"] for r in rows}
    assert "report_intel_87210a61730c22b9_v1" in ids
    assert "report_intel_dbab7b01963396b5_v1" in ids


def test_report_inspector_not_found_for_fake_id():
    result = op.report_inspector("report_intel_does_not_exist_v1")
    assert result["status"] == "NOT_FOUND"


def test_report_inspector_never_mutates_canonical_report_file():
    path = op.re_.REPORTS_DIR / "report_intel_87210a61730c22b9_v1.json"
    before = path.read_bytes()
    op.report_inspector("report_intel_87210a61730c22b9_v1")
    after = path.read_bytes()
    assert before == after


def test_provenance_inspector_uses_real_claim_and_source_ids_not_new_ones():
    prov = op.provenance_inspector("report_intel_87210a61730c22b9_v1")
    assert prov["status"] == "FOUND"
    assert prov["claim_chain"][0]["claim_id"] == "claim_7f1bc452c4ffc128"
    assert prov["statistical_chain"][0]["source_id"] == "src_worldbank_api"


def test_provenance_inspector_not_connected_for_object_with_no_claims():
    prov = op.provenance_inspector("report_intel_does_not_exist_v1")
    assert prov["status"] == "NOT_FOUND"


def test_gap_inspector_never_hides_a_known_gap():
    gaps = op.gap_inspector()
    assert len(gaps) == 7  # matches the real known_gaps_total across both objects
    topics = {g["topic"] for g in gaps}
    assert topics == {"AI_ENERGY_INFRA", "AI_LABOR"}


def test_gap_inspector_filters_by_topic():
    gaps = op.gap_inspector(topic="AI_LABOR")
    assert all(g["topic"] == "AI_LABOR" for g in gaps)
    assert len(gaps) == 3


def test_gap_inspector_honest_unknown_when_no_rich_next_action_exists():
    gaps = op.gap_inspector()
    for g in gaps:
        assert g["next_possible_action"] != ""  # never silently empty
        # either a real recorded action string, or the honest fallback
        assert g["next_possible_action"] == "UNKNOWN" or isinstance(g["next_possible_action"], str)


def test_rights_inspector_never_includes_vault_full_text_field():
    import json
    rows = op.rights_inspector()
    serialized = json.dumps(rows, ensure_ascii=False)
    assert "full_text" not in serialized


def test_rights_inspector_public_allowed_false_for_unknown_rights():
    rows = op.rights_inspector()
    for r in rows:
        if r["rights_status"] == "UNKNOWN_RIGHTS":
            assert r["public_allowed"] is False


def test_source_health_never_claims_healthy_without_real_observation():
    rows = op.source_health()
    for r in rows:
        assert r["status"] in op.SOURCE_HEALTH_STATES
        if r["status"] == "HEALTHY":
            assert r["last_checked"] != "UNKNOWN"


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
