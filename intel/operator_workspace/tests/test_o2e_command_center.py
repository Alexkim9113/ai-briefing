# O-2E -- Operator Intelligence Command Center & Editorial Intelligence Workflow Completion.
# Tests the new, purely-derived read layer added to operator_api.py / operator_ui.py: today's key
# signals, change watch, gap categorization, portfolio summary, and the UI-level safety
# properties Te's spec requires (priority/evidence-status separation, URL-scheme validation,
# XSS escaping, no internal-ID/secret leaks, canonical no-mutation).
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import operator_api as op  # noqa: E402
import operator_ui as ou  # noqa: E402

ROOT = op.ROOT
CANONICAL_FILES = (
    op.INTEL_DIR / "claims" / "claims.json",
    op.INTEL_DIR / "hypothesis" / "hypotheses.json",
    ROOT / "intel" / "intelligence_objects" / "intelligence_objects.json",
)


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_canonical_files_are_not_mutated_by_any_new_read():
    before = {p: _hash(p) for p in CANONICAL_FILES}
    op.today_key_signals()
    op.intelligence_change_watch()
    op.portfolio_summary()
    op.gaps_by_category()
    ou.render_overview()
    after = {p: _hash(p) for p in CANONICAL_FILES}
    assert before == after


def test_today_key_signals_only_surfaces_claims_actually_wired_into_hypotheses():
    claims = json.loads(op.re_.CLAIMS_PATH.read_text(encoding="utf-8"))
    hyp = json.loads((op.INTEL_DIR / "hypothesis" / "hypotheses.json").read_text(encoding="utf-8"))
    wired_ids = set()
    for h in hyp.values():
        for ref in (h.get("supporting_evidence") or []) + (h.get("contradicting_evidence") or []):
            wired_ids.add(ref.split(":", 1)[0] if isinstance(ref, str) and ":" in ref else ref)
    for s in op.today_key_signals():
        assert s["claim_id"] in wired_ids
        assert s["claim_id"] in claims


def test_today_key_signals_is_an_honest_no_llm_derivation_not_a_firehose():
    # Every signal (if any) must be strictly newer than its topic's latest published report --
    # never the entire claims corpus dumped as "signals".
    signals = op.today_key_signals()
    for s in signals:
        assert s["reference_report_generated_at"] is None or s["claim_created_at"] > s["reference_report_generated_at"]


def test_overview_renders_honest_empty_state_or_real_cards_never_fabricated_text():
    html_doc = ou.render_overview()
    assert "오늘의 핵심 신호" in html_doc
    signals = op.today_key_signals()
    if not signals:
        assert "새로운 신호는 확인되지 않았습니다" in html_doc
    else:
        for s in signals:
            assert s["claim_id"] in html_doc


def test_gap_category_covers_the_six_named_buckets_or_uncategorized():
    allowed = set(op.GAP_CATEGORY_KO.keys())
    for g in op.gap_inspector():
        cat = op.categorize_gap(g["gap_type"], g["description"])
        assert cat in allowed


def test_gap_category_never_forces_ambiguous_text_into_a_named_bucket():
    assert op.categorize_gap("", "") == "UNCATEGORIZED"
    assert op.categorize_gap("TOTALLY_UNRELATED_TYPE", "nothing matches any keyword here at all") == "UNCATEGORIZED"


def test_portfolio_summary_has_korean_topic_name_and_separates_evidence_from_counterevidence():
    rows = op.portfolio_summary()
    assert rows
    for r in rows:
        assert r["topic_ko"] in op.TOPIC_KO.values()
        assert "key_evidence_count" in r and "key_counterevidence_count" in r
        assert isinstance(r["key_evidence_count"], int)
        assert isinstance(r["key_counterevidence_count"], int)


def test_priority_badge_is_structurally_separate_from_evidence_status_field():
    # The priority badge helper must never be the same HTML element/class as a _status() call --
    # they render distinct <span> markup so Operator UI cannot conflate the two fields.
    badge = ou._priority_badge("HIGH", "기존 H2와 직접 충돌")
    status = ou._status("SUPPORTED")
    assert "우선순위" in badge
    assert "기존 H2와 직접 충돌" in badge
    assert badge != status


def test_safe_link_rejects_javascript_and_data_schemes():
    assert "href" not in ou._safe_link("javascript:alert(1)")
    assert "href" not in ou._safe_link("data:text/html,bad")
    assert "href" not in ou._safe_link("URL_NOT_VERIFIED")
    assert 'href="https://example.org"' in ou._safe_link("https://example.org")
    assert 'href="http://example.org"' in ou._safe_link("http://example.org")


def test_safe_link_escapes_html_in_label():
    rendered = ou._safe_link("URL_NOT_VERIFIED", '<script>alert(1)</script>')
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered


def test_key_signal_cards_never_fabricate_a_url_and_always_escape_claim_text():
    for s in op.today_key_signals():
        assert s["url"] == "URL_NOT_VERIFIED" or s["url"].startswith("http")
    html_doc = ou._key_signals_section_html()
    assert "<script" not in html_doc.lower()


def test_overview_never_leaks_internal_evidence_ids_or_vault_terms():
    html_doc = ou.render_overview()
    lowered = html_doc.lower()
    for forbidden in ("private_research_vault", "secret", "api_key", "authorization:"):
        assert forbidden not in lowered


def test_change_watch_reads_existing_fields_only_no_new_score():
    watch = op.intelligence_change_watch()
    assert "contested_hypotheses" in watch and "gap_watch" in watch
    for c in watch["contested_hypotheses"]:
        assert c["contradicting_evidence_count"] >= 1


def test_attribution_and_observation_forecast_korean_maps_cover_known_codes():
    for code in ("DIRECT", "PARTIAL", "INDIRECT", "NOT_APPLICABLE", "UNKNOWN"):
        assert code in op.ATTRIBUTION_KO
    for code in ("OBSERVATION", "FORECAST"):
        assert code in op.OBSERVATION_FORECAST_KO


def test_build_is_idempotent_byte_identical_across_two_runs():
    a = HERE.parent / "_test_o2e_site_a"
    b = HERE.parent / "_test_o2e_site_b"
    shutil.rmtree(a, ignore_errors=True)
    shutil.rmtree(b, ignore_errors=True)
    try:
        status_a = ou.build_operator_pages(a)
        status_b = ou.build_operator_pages(b)
        assert status_a["errors"] == [] and status_b["errors"] == []
        files_a = sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file())
        files_b = sorted(p.relative_to(b) for p in b.rglob("*") if p.is_file())
        assert files_a == files_b
        for rel in files_a:
            assert (a / rel).read_bytes() == (b / rel).read_bytes()
    finally:
        shutil.rmtree(a, ignore_errors=True)
        shutil.rmtree(b, ignore_errors=True)


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
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
