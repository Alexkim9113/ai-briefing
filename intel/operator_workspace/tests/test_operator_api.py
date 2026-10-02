# N-4B -- Operator Workspace Foundation tests. Verifies every surface reads real data only --
# never fabricates HEALTHY/READY values a backend doesn't actually have.
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import operator_api as op  # noqa: E402
sys.path.insert(0, str(HERE.parent.parent / "report_engine"))
import report_engine as re_  # noqa: E402


def test_overview_counts_match_known_real_corpus_scale():
    # DYNAMIC CONTRACT (O-1E Part 1, Te spec 43-44): the corpus grows over time via an
    # unrelated automated daily acquisition cron job, so a hardcoded literal (e.g.
    # documents == 601) goes stale on its own schedule, independent of any code change.
    # Instead of comparing against a fixed number, or calling overview() twice (which
    # would just compare the function to itself), this test re-reads the same raw
    # source files overview() reads and recomputes each count with its own simple,
    # independent counting logic. If overview()'s internal counting logic and this
    # test's counting logic ever diverge, the test will genuinely fail -- which is the
    # point: it is now a correctness check against the raw corpus, not a snapshot.
    o = op.overview()

    documents = op._load(re_.DOCUMENTS_PATH)
    claims = op._load(re_.CLAIMS_PATH)
    objects = op._load(op.ROOT / "intel" / "intelligence_objects" / "intelligence_objects.json")
    reports = list(re_.REPORTS_DIR.glob("report_intel_*_v*.json"))

    assert o["documents"] == len(documents)
    assert o["intelligence_objects"] == len(objects)
    assert o["reports"] == len(reports)
    assert o["claims"] == len(claims)


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
    # DYNAMIC CONTRACT (O-1E Part 1, Te spec 43-44): a specific hardcoded claim_id/
    # source_id string can stop existing as the underlying data evolves. Instead of
    # hardcoding one, this test independently resolves the real claim_id straight out
    # of the report JSON file on disk (the same thing provenance_inspector() reads),
    # and independently resolves a real statistical source_id by reading the
    # intelligence object's own "statistics" list and looking each series up in
    # statistical_evidence.json -- the same raw sources provenance_inspector() uses,
    # read here with separate, parallel logic. The test then asserts
    # provenance_inspector() actually surfaces those same real, currently-existing ids.
    report_id = "report_intel_87210a61730c22b9_v1"
    report = op._load(re_.REPORTS_DIR / f"{report_id}.json")
    expected_claim_ids = report["sections"]["KEY_CLAIMS"].get("claim_ids", [])
    assert expected_claim_ids, "expected the real report to reference at least one claim"
    expected_claim_id = expected_claim_ids[0]

    objects = op._load(op.ROOT / "intel" / "intelligence_objects" / "intelligence_objects.json")
    obj = objects[report["intelligence_id"]]
    stat_ids = obj.get("statistics") or []
    assert stat_ids, "expected the real intelligence object to reference at least one statistical series"
    stats_by_id = op._load(re_.STAT_PATH)
    expected_source_id = stats_by_id[stat_ids[0]].get("source_id")
    assert expected_source_id

    prov = op.provenance_inspector(report_id)
    assert prov["status"] == "FOUND"
    assert prov["claim_chain"][0]["claim_id"] == expected_claim_id
    assert prov["statistical_chain"][0]["source_id"] == expected_source_id


def test_provenance_inspector_not_connected_for_object_with_no_claims():
    prov = op.provenance_inspector("report_intel_does_not_exist_v1")
    assert prov["status"] == "NOT_FOUND"


def test_gap_inspector_never_hides_a_known_gap():
    # DYNAMIC CONTRACT (O-1E Part 1, Te spec 43-44): the real known_gaps count grows as
    # new gap types are legitimately discovered (e.g. O-1C/O-1D added
    # AI_ONLY_ATTRIBUTION_DISAGGREGATION_GAP), so a hardcoded literal count goes stale
    # on its own schedule. Instead, this test independently reads
    # intelligence_objects.json itself and sums len(known_gaps) across every IO with its
    # own simple loop -- the same raw source gap_inspector() reads -- and asserts
    # gap_inspector()'s output has exactly that many rows (gap_inspector does not add or
    # remove gaps, only joins in richer optional metadata), so the test can never hide a
    # future gap addition or removal by comparing against a frozen number.
    objects = op._load(op.ROOT / "intel" / "intelligence_objects" / "intelligence_objects.json")
    expected_total = sum(len(o.get("known_gaps") or []) for o in objects.values())
    expected_topics = {o.get("topic") for o in objects.values() if o.get("known_gaps")}

    gaps = op.gap_inspector()
    assert len(gaps) == expected_total
    topics = {g["topic"] for g in gaps}
    assert topics == expected_topics


def test_gap_inspector_filters_by_topic():
    # O-2 round 5: IO v2 added a new AI_LABOR known_gaps entry (AI_DISPLACEMENT_VS_PRODUCTIVITY_
    # DISAGGREGATION_GAP), so the real, current gap count is checked against the live source of
    # truth (the IO's own known_gaps) rather than a round-specific hardcoded number.
    import json
    io_path = Path(__file__).resolve().parents[2] / "intelligence_objects" / "intelligence_objects.json"
    objects = json.loads(io_path.read_text(encoding="utf-8"))
    io = next(o for o in objects if o.get("intelligence_id") == "intel_dbab7b01963396b5") \
        if isinstance(objects, list) else objects["intel_dbab7b01963396b5"]
    expected = len(io.get("known_gaps", []))
    gaps = op.gap_inspector(topic="AI_LABOR")
    assert all(g["topic"] == "AI_LABOR" for g in gaps)
    assert len(gaps) == expected


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
