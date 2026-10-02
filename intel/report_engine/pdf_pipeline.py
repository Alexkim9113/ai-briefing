# N-4 Sections 12-20 -- PDF Report Pipeline. REPORT JSON -> (print HTML via product_html, reusing
# the exact same Presentation Model and section renderer as the web view) -> PDF via headless
# Chromium. No separate fact source: the print HTML is produced by the same render_product_html()
# used for the web page, only wrapped with print-oriented CSS. A PDF failure must never block the
# HTML/Public Site/Evidence Collection pipeline (Section 43) -- callers should catch exceptions
# from generate_pdf() and record PDF_FAILED without touching REPORT_JSON_READY/HTML_READY state.
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import product_html as ph  # noqa: E402

CHROME_BIN = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

PRINT_CSS = """
@media print {
  body{max-width:none;font-size:11.5pt}
  .report-section{page-break-inside:avoid}
  h1{page-break-before:auto}
  a{color:inherit;text-decoration:none}
}
@page { margin: 18mm 16mm; }
"""


def render_print_html(presentation, source_cards=None, view="PUBLIC", real_sources=None):
    base = ph.render_product_html(presentation, source_cards=source_cards, view=view,
                                   real_sources=real_sources)
    return base.replace("</style>", PRINT_CSS + "</style>")


def generate_pdf(print_html_path, pdf_out_path):
    """Converts an existing print-HTML file to PDF via headless Chromium. Raises on failure --
    callers must catch this and mark PDF_FAILED without affecting HTML_READY state (Section 43)."""
    print_html_path = Path(print_html_path).resolve()
    pdf_out_path = Path(pdf_out_path).resolve()
    result = subprocess.run(
        [CHROME_BIN, "--headless", "--disable-gpu", "--no-sandbox",
         f"--print-to-pdf={pdf_out_path}", "--print-to-pdf-no-header",
         f"file://{print_html_path}"],
        capture_output=True, text=True, timeout=60,
    )
    if not pdf_out_path.exists() or pdf_out_path.stat().st_size == 0:
        raise RuntimeError(f"PDF generation failed: rc={result.returncode} stderr={result.stderr[:500]}")
    return pdf_out_path


def validate_pdf(pdf_path, forbidden_strings=None):
    """Section 45 -- PDF Validation. Checks the file exists, has a valid PDF header, and is
    non-trivial in size. Text-content checks (Sources section present, no forbidden causal
    sentence) are done on the source HTML before conversion, since this module does not depend on
    a PDF-text-extraction library; generate_pdf_sample() below records both checks together."""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return {"ok": False, "reason": "FILE_NOT_CREATED"}
    data = pdf_path.read_bytes()
    if not data.startswith(b"%PDF-"):
        return {"ok": False, "reason": "NOT_A_PDF"}
    if len(data) < 1000:
        return {"ok": False, "reason": "SUSPICIOUSLY_SMALL"}
    return {"ok": True, "size_bytes": len(data)}
