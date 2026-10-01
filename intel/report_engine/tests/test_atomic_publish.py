# N-6 PRIORITY 1 -- Atomic Publish tests: GENERATE -> TEMP WRITE -> VALIDATE -> ATOMIC REPLACE.
# Three intentional-failure tests (JSON validation failure, HTML validation failure, PDF
# conversion failure) each assert the pre-existing artifact is byte-identical to before the
# failed publish attempt, and that no *.tmp file is left behind.
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import atomic_publish as apub  # noqa: E402
import report_ops as ro  # noqa: E402
import report_engine as re_  # noqa: E402
import pdf_pipeline as pp  # noqa: E402

SCRATCH = HERE / "_atomic_publish_scratch"


def _reset_scratch():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    for f in SCRATCH.glob("*"):
        f.unlink()


def test_atomic_write_json_success_replaces_file():
    _reset_scratch()
    target = SCRATCH / "good.json"
    r1 = apub.atomic_write(target, '{"a": 1}', validator=apub.json_validator)
    assert r1["status"] == "PUBLISHED"
    assert target.read_text(encoding="utf-8") == '{"a": 1}'
    assert not (SCRATCH / "good.json.tmp").exists()


def test_atomic_write_json_failure_leaves_existing_file_untouched():
    _reset_scratch()
    target = SCRATCH / "existing.json"
    target.write_text('{"version": 1}', encoding="utf-8")
    before = target.read_bytes()
    result = apub.atomic_write(target, "{not valid json", validator=apub.json_validator)
    assert result["status"] == "PUBLISH_FAILED"
    after = target.read_bytes()
    assert before == after
    assert not (SCRATCH / "existing.json.tmp").exists()


def test_atomic_write_html_failure_leaves_existing_file_untouched():
    _reset_scratch()
    target = SCRATCH / "existing.html"
    target.write_text("<html><body>GOOD</body></html>", encoding="utf-8")
    before = target.read_bytes()
    # Missing closing </html> -- html_validator must reject this.
    result = apub.atomic_write(target, "<html><body>BROKEN", validator=apub.html_validator)
    assert result["status"] == "PUBLISH_FAILED"
    after = target.read_bytes()
    assert before == after
    assert not (SCRATCH / "existing.html.tmp").exists()


def test_atomic_write_empty_html_rejected():
    _reset_scratch()
    target = SCRATCH / "existing2.html"
    target.write_text("<html><body>GOOD</body></html>", encoding="utf-8")
    before = target.read_bytes()
    result = apub.atomic_write(target, "   ", validator=apub.html_validator)
    assert result["status"] == "PUBLISH_FAILED"
    assert target.read_bytes() == before


def test_atomic_write_pdf_conversion_failure_leaves_existing_pdf_untouched():
    """Simulates a PDF-conversion failure (bad CHROME_BIN, matching test_report_ops.py's existing
    monkeypatch pattern) by trying to atomically publish a non-PDF candidate over a previously
    valid PDF artifact -- the pdf_validator_factory()-bound validator must reject it and the
    original PDF bytes must survive unchanged."""
    _reset_scratch()
    target = SCRATCH / "existing.pdf"
    target.write_bytes(b"%PDF-1.4\n" + b"0" * 2000)  # a previously valid, non-trivial PDF
    before = target.read_bytes()
    validator = apub.pdf_validator_factory(pp)
    # Candidate content is NOT a PDF at all -- stands in for a failed Chromium conversion that
    # produced garbage/empty output instead of raising directly.
    result = apub.atomic_write(target, b"NOT A PDF AT ALL", validator=validator)
    assert result["status"] == "PUBLISH_FAILED"
    after = target.read_bytes()
    assert before == after
    assert not (SCRATCH / "existing.pdf.tmp").exists()


def test_build_artifacts_pdf_failure_still_isolated_and_no_tmp_leftovers():
    """Reaffirms (N-6 PRIORITY 1b) the existing report_ops.py failure-isolation contract still
    holds: a real end-to-end PDF generation failure (bad CHROME_BIN) must not affect
    REPORT_JSON_READY/HTML_READY, and must leave no report_ops-owned temp files behind."""
    original_chrome = pp.CHROME_BIN
    pp.CHROME_BIN = "/nonexistent/chrome-binary-n6"
    try:
        r = re_.build_report("intel_dbab7b01963396b5")
        docs = re_._load(re_.DOCUMENTS_PATH)
        status = ro.build_artifacts_with_failure_isolation(r, docs, view="PUBLIC")
        assert status["report_json"] == "REPORT_JSON_READY"
        assert status["html"] == "HTML_READY"
        assert status["pdf"] == "PDF_FAILED"
        leftovers = list(re_.REPORTS_DIR.glob("*_tmp_print.html")) + list(re_.REPORTS_DIR.glob("*_tmp.pdf"))
        assert leftovers == []
    finally:
        pp.CHROME_BIN = original_chrome


def _cleanup_scratch():
    if SCRATCH.exists():
        for f in SCRATCH.glob("*"):
            f.unlink()
        SCRATCH.rmdir()


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
    _cleanup_scratch()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
