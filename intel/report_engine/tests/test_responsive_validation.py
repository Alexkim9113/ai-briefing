# N-6 PRIORITY 2 -- Responsive Validation tests. Confirms responsive_validation.py renders every
# target page at every achievable viewport width with no failures, and re-confirms (via simple
# string checks, not a new accessibility framework) that the existing semantic-heading / landmark /
# aria-label / focus-visible affordances are still present in the rendered output.
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent / "operator_workspace"))
import responsive_validation as rv  # noqa: E402

SCRATCH = HERE / "_responsive_validation_scratch"


def _run():
    return rv.run_responsive_validation(SCRATCH)


def test_all_four_target_pages_are_generated():
    report = _run()
    pages_seen = {r["page"] for r in report["results"]}
    assert pages_seen == {"public_index", "public_detail", "operator_overview", "print_report"}


def test_every_page_renders_at_every_requested_width_with_no_failures():
    report = _run()
    assert len(report["results"]) == len(rv.REQUESTED_WIDTHS) * 4
    non_rendered = [r for r in report["results"] if r["status"] != "RENDERED"]
    assert non_rendered == [], f"non-rendered rows: {non_rendered}"


def test_375_request_honestly_records_the_500px_environment_proxy():
    """Section: never silently substitute an achieved width for a requested one -- the 375px rows
    must explicitly record actual_width=500 and say so in notes, not claim actual_width=375."""
    report = _run()
    rows_375 = [r for r in report["results"] if r["requested_width"] == 375]
    assert rows_375, "no 375px rows produced"
    for r in rows_375:
        assert r["actual_width"] == 500
        assert "500" in r["notes"] or "proxy" in r["notes"]


def test_environment_limitation_is_documented_in_every_report():
    report = _run()
    assert "500px" in report["environment_limitation"]
    assert "window-size" in report["environment_limitation"] or "--window-size" in report["environment_limitation"]


def test_public_detail_page_has_semantic_landmarks_and_aria_labels():
    report = _run()
    detail_row = next(r for r in report["results"] if r["page"] == "public_detail")
    assert detail_row["status"] == "RENDERED"
    # Re-read the actual HTML (not the screenshot) that was rendered for this check.
    built = rv.build_sample_pages(SCRATCH)
    html = Path(built["pages"]["public_detail"]).read_text(encoding="utf-8")
    assert "<h1>" in html
    assert "<h2" in html
    assert 'aria-label="Intelligence Report"' in html or "aria-label='Intelligence Report'" in html
    assert "aria-labelledby=" in html
    assert "focus-visible" in html  # focus-visible outline rule must still be in the stylesheet


def test_operator_overview_has_nav_landmark_and_focus_visible():
    built = rv.build_sample_pages(SCRATCH)
    html = Path(built["pages"]["operator_overview"]).read_text(encoding="utf-8")
    assert "<nav " in html
    assert "aria-label=" in html
    assert "focus-visible" in html


def test_print_report_page_renders_without_horizontal_scroll_css_regression():
    """Minimal regression check: the print page must still carry the page's own responsive CSS
    (overflow-wrap / table-wrap) -- not a pixel check, just confirms the fix shipped into the print
    path too, since render_print_html() reuses render_product_html()."""
    built = rv.build_sample_pages(SCRATCH)
    html = Path(built["pages"]["print_report"]).read_text(encoding="utf-8")
    assert "overflow-wrap" in html
    assert "chart-table-wrap" in html or "chart-table" not in html


def _cleanup():
    import shutil
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH, ignore_errors=True)


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
    _cleanup()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
