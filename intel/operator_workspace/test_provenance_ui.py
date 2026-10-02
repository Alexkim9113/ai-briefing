# O-1E Part 6 -- real provenance full-chain test. Uses the REAL AI_ENERGY_INFRA v4 report and
# real canonical stores (hypotheses.json, claims.json, evidence_claim_relations.json,
# intelligence_objects.json) -- no fake fixture. Asserts the chain actually reaches
# Report -> IO -> Hypothesis -> Claim -> Evidence (Source where resolvable), and that the
# rendered Provenance Inspector page contains that same real data.
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import operator_api as op  # noqa: E402
import operator_ui as ui  # noqa: E402

REPORT_ID = "report_intel_87210a61730c22b9_v4"


def test_provenance_chain_reaches_report_to_io():
    chain = op.provenance_chain_full(REPORT_ID)
    assert chain["status"] == "FOUND"
    assert chain["nodes"]["report"]["report_id"] == REPORT_ID
    assert chain["nodes"]["intelligence_object"]["intelligence_id"] == "intel_87210a61730c22b9"
    assert chain["nodes"]["intelligence_object"]["topic"] == "AI_ENERGY_INFRA"


def test_provenance_chain_reaches_hypothesis_and_claim():
    chain = op.provenance_chain_full(REPORT_ID)
    assert len(chain["hypotheses"]) >= 7, "expected H1-H7 for AI_ENERGY_INFRA"
    codes = {h["hypothesis_id"] for h in chain["hypotheses"]}
    assert "hyp_o0_h2_ai_energy_infra" in codes
    total_claims = sum(len(h["claims"]) for h in chain["hypotheses"])
    assert total_claims > 0, "no claims reached via any hypothesis"
    # At least one claim must carry real human-readable text, not a placeholder.
    sample_texts = [c["claim_text"] for h in chain["hypotheses"] for c in h["claims"]]
    assert any(t not in (None, "UNKNOWN") and len(t) > 10 for t in sample_texts)


def test_provenance_chain_reaches_evidence_and_attempts_source():
    chain = op.provenance_chain_full(REPORT_ID)
    all_evidence = [e for h in chain["hypotheses"] for c in h["claims"] for e in c["evidence"]]
    assert len(all_evidence) > 0, "no evidence edges reached at all"
    # Connectivity states must be drawn only from the allowed vocabulary (Section 17) --
    # never a fabricated or out-of-vocabulary state.
    allowed = {"CONNECTED", "PARTIALLY_CONNECTED", "NOT_CONNECTED", "UNRESOLVED_REFERENCE"}
    for e in all_evidence:
        assert e["connectivity"] in allowed, f"unexpected connectivity state: {e['connectivity']}"
    for h in chain["hypotheses"]:
        assert h["connectivity"] in allowed
        for c in h["claims"]:
            assert c["connectivity"] in allowed
    # At least one evidence edge must have a real, non-placeholder source attribution (a URL),
    # proving the chain reaches an actual Source, not just a dangling id.
    sourced = [e for e in all_evidence if isinstance(e["source_id"], str) and e["source_id"].startswith("http")]
    assert sourced, "expected at least one evidence edge to resolve to a real source URL"


def test_statistical_chain_present_for_this_report():
    chain = op.provenance_chain_full(REPORT_ID)
    assert isinstance(chain["statistical_chain"], list)
    assert len(chain["statistical_chain"]) > 0
    for s in chain["statistical_chain"]:
        assert "statistical_series_id" in s and "source_id" in s


def test_rendered_provenance_page_contains_real_chain_data():
    html = ui.render_provenance_inspector(REPORT_ID)
    assert "report_intel_87210a61730c22b9_v4" in html
    assert "intel_87210a61730c22b9" in html
    assert "AI_ENERGY_INFRA" in html
    assert "hyp_o0_h2_ai_energy_infra" in html
    assert "PARTIALLY_CONNECTED" in html or "CONNECTED" in html
    assert "NOT_CONNECTED" in html or "UNRESOLVED_REFERENCE" in html or "PARTIALLY_CONNECTED" in html


def test_intelligence_index_handles_ai_labor_without_crashing():
    # AI_LABOR has far fewer claims/hypotheses than AI_ENERGY_INFRA -- this must not crash.
    rows = op.intelligence_index()
    topics = {r["topic"] for r in rows}
    assert "AI_ENERGY_INFRA" in topics
    assert "AI_LABOR" in topics
    labor_row = next(r for r in rows if r["topic"] == "AI_LABOR")
    assert labor_row["claim_count"] >= 0
    html = ui.render_intelligence_index()
    assert "AI_LABOR" in html


def test_report_inspector_renders_for_every_real_version():
    import report_engine as re_  # noqa: E402  (already on sys.path via operator_api import chain)
    paths = sorted(re_.REPORTS_DIR.glob("report_intel_87210a61730c22b9_v*.json"))
    assert len(paths) >= 4, "expected v1-v4 to still exist on disk"
    for p in paths:
        html = ui.render_report_inspector(p.stem)
        assert p.stem in html
        assert "NOT_FOUND" not in html


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
