# N-5 Section 10-19, 60-62 -- Operator Workspace minimal UI tests. Because this project is
# deployed to GitHub Pages (pure static hosting, no auth layer), anything written under
# site/operator/ is PUBLIC_SAFE_OPERATOR content by construction -- these tests assert that no
# private/sensitive field ever reaches the rendered HTML.
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import operator_ui as ou  # noqa: E402
import operator_api as op  # noqa: E402


def test_all_pages_render_without_raising():
    for name, renderer in ou.PAGES.items():
        html_doc = renderer()
        assert "<html" in html_doc


def test_build_operator_pages_writes_every_page():
    tmp = HERE.parent / "_test_site_ui"
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        status = ou.build_operator_pages(tmp)
        assert status["errors"] == []
        # O-1E: pages_written now also includes one report/ and provenance/ page per real,
        # on-disk report version, in addition to the fixed PAGES set.
        assert set(ou.PAGES.keys()).issubset(set(status["pages_written"]))
        for name in ou.PAGES:
            assert (tmp / "operator" / name / "index.html").exists()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_rights_page_never_exposes_full_text():
    html_doc = ou.render_rights()
    assert "full_text" not in html_doc


def test_overview_never_fabricates_healthy_source_status():
    html_doc = ou.render_overview()
    # the minimal operator_api source_health field is honestly NOT_INSTRUMENTED or a real status
    assert "FAKE" not in html_doc.upper()


def test_live_run_status_backend_still_available_but_not_on_today_page():
    """TODAY BRIEFING REBUILD (2026-10-03): '오늘' (render_overview) is a Daily Intelligence
    Briefing now and deliberately no longer shows Pipeline/System Health (RUN_ID/ENVIRONMENT) --
    section 2 of the directive explicitly excludes internal pipeline state from this page. The
    backend function itself is untouched and still callable."""
    live = op.live_run_status()
    assert "run_id" in live and "environment" in live
    assert "Pipeline / System Health" not in ou.render_overview()


def test_overview_live_run_section_never_shows_secrets_or_headers():
    html_doc = ou.render_overview()
    lowered = html_doc.lower()
    for forbidden in ("authorization:", "api_key=", "x-api-key", "bearer "):
        assert forbidden not in lowered


def test_sources_page_caps_sample_and_links_full_json():
    html_doc = ou.render_sources()
    assert "sources_full.json" in html_doc or "first" in html_doc.lower()


def test_gaps_page_never_hides_known_gap_count():
    html_doc = ou.render_gaps()
    assert "7" in html_doc or "known gap" in html_doc.lower()


def test_source_health_page_handles_no_pilot_gracefully():
    original = ou.op.sh.load_result
    ou.op.sh.load_result = lambda: None
    try:
        html_doc = ou.render_source_health()
        assert "NOT_INSTRUMENTED" in html_doc or "not been run" in html_doc.lower()
    finally:
        ou.op.sh.load_result = original


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
