# N-4B Section 15-23 -- Public Intelligence Page delivery. A thin delivery layer only: it reuses
# the exact same build_public_view() + build_presentation() + render_product_html() already used
# and tested in N-4, and writes their output as PREBUILT static files under site/intelligence/,
# matching this project's existing static-site convention (every other page -- category archives,
# the editor, feeds -- is written the same way by briefing.py's build()). No new renderer, no
# request-time computation: this runs only at build time, same as the rest of the site.
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import report_engine as re_  # noqa: E402
import presentation_model as pm  # noqa: E402
import product_html as ph  # noqa: E402

ROOT = HERE.parents[1]
REPORTS_DIR = re_.REPORTS_DIR


def _source_cards(pub_report, documents_by_id):
    prov_blocks = pub_report["sections"]["SOURCE_PROVENANCE"].get("content_blocks", [])
    cards = []
    for b in prov_blocks:
        sid = b.get("source_id")
        if sid in documents_by_id:
            cards.append(re_.build_source_card(documents_by_id[sid]))
        else:
            cards.append({"title": sid, "publisher": "NON_DOCUMENT_PROVENANCE", "date": "UNKNOWN",
                          "access_status": "UNKNOWN", "rights_status": "UNKNOWN"})
    return cards


def discover_real_reports():
    """Section 19 -- the Public Intelligence Index is built from the real reports that already
    exist on disk, never a hardcoded list. No automatic mass exposure of future topics beyond
    what the Report Engine has actually produced (Section 27's no-mass-exposure rule)."""
    return sorted(REPORTS_DIR.glob("report_intel_*_v*.json"))


def build_intelligence_index_entry(report_path):
    r = json.loads(report_path.read_text(encoding="utf-8"))
    pdf_path = REPORTS_DIR / f"{report_path.stem}.pdf"
    # Section 7 -- short summary comes straight from the report's own real CURRENT_STATE text,
    # never a separately written description that could drift from the canonical content.
    current_state_blocks = r["sections"].get("CURRENT_STATE", {}).get("content_blocks") or []
    summary = current_state_blocks[0] if current_state_blocks else "UNKNOWN"
    return {
        "report_id": r["report_id"],
        "intelligence_id": r["intelligence_id"],
        "topic": r["topic"],
        "title": f"{r['topic']} Intelligence Report",
        "summary": summary,
        "version": r["version"],
        "generated_at": r["generated_at"],
        "updated_at": r["generated_at"],
        "readiness": r["readiness"],
        "available_formats": {
            "html": True,  # product_html is always generated alongside the Report JSON in this pipeline
            "pdf": pdf_path.exists(),
        },
    }


def build_report_index():
    """Section 20 -- minimal Report Search/Index. No full-body duplication: just the fields a
    list/search view needs."""
    return [build_intelligence_index_entry(p) for p in discover_real_reports()]


def search_report_index(index, query=None, readiness=None):
    """Section 21 -- simple deterministic filtering, not a search engine. Matches on topic/
    title/report_id substring (case-insensitive) and/or exact readiness."""
    rows = index
    if query:
        q = query.lower()
        rows = [r for r in rows if q in r["topic"].lower() or q in r["title"].lower()
                or q in r["report_id"].lower()]
    if readiness:
        rows = [r for r in rows if r["readiness"] == readiness]
    return rows


def render_public_page_for_report(report_path, documents_by_id):
    r = json.loads(report_path.read_text(encoding="utf-8"))
    pub = re_.build_public_view(r)
    presentation = pm.build_presentation(pub)
    cards = _source_cards(pub, documents_by_id)
    html_doc = ph.render_product_html(presentation, source_cards=cards, view="PUBLIC")
    pdf_exists = (REPORTS_DIR / f"{report_path.stem}.pdf").exists()
    return html_doc, pdf_exists


def build_public_intelligence_pages(site_dir):
    """Writes site/intelligence/index.html (the Public Intelligence Index, Section 19) and
    site/intelligence/{report-id}/index.html per real report (Section 16's '/intelligence/
    {report-id}' route, chosen to match this project's existing convention of one static
    directory-with-index.html per page, e.g. SITE_DIR/{category}/index.html).

    This function never raises -- Section 32's Failure Isolation principle: a failure here must
    never block the rest of the site build. Callers should wrap it in try/except regardless, but
    internal errors are also caught and reported in the returned status dict."""
    documents_by_id = re_._load(re_.DOCUMENTS_PATH)
    status = {"pages_written": [], "errors": []}
    intel_dir = Path(site_dir) / "intelligence"
    try:
        intel_dir.mkdir(parents=True, exist_ok=True)
        index = build_report_index()
        for report_path, entry in zip(discover_real_reports(), index):
            try:
                html_doc, pdf_exists = render_public_page_for_report(report_path, documents_by_id)
                page_dir = intel_dir / entry["report_id"]
                page_dir.mkdir(parents=True, exist_ok=True)
                (page_dir / "index.html").write_text(html_doc, encoding="utf-8")
                if pdf_exists:
                    pdf_src = REPORTS_DIR / f"{report_path.stem}.pdf"
                    (page_dir / "report.pdf").write_bytes(pdf_src.read_bytes())
                status["pages_written"].append(entry["report_id"])
            except Exception as e:  # noqa: BLE001 -- one bad report must not block the others
                status["errors"].append({"report_id": entry.get("report_id"), "error": str(e)})

        index_html = _render_index_page(index)
        (intel_dir / "index.html").write_text(index_html, encoding="utf-8")
        (intel_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        status["errors"].append({"report_id": None, "error": str(e)})
    return status


def _render_index_page(index):
    import html as _html

    def _row(e):
        pdf_link = ""
        if e["available_formats"]["pdf"]:
            href = _html.escape(e["report_id"]) + "/report.pdf"
            pdf_link = f" <a class='pdf' href='{href}'>PDF</a>"
        return (f'<li><h2><a href="{_html.escape(e["report_id"])}/">{_html.escape(e["title"])}</a></h2>'
                f'<p>{_html.escape(e["summary"])}</p>'
                f'<p><span class="badge">Evidence Status: {_html.escape(e["readiness"])}</span> '
                f'<span class="meta">Updated {_html.escape(e["updated_at"][:10])}</span>{pdf_link}</p></li>')

    rows = "".join(_row(e) for e in index)
    return (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>Intelligence Reports</title></head><body>"
        "<main><h1>METAXIS Intelligence Reports</h1><ul>"
        f"{rows}</ul></main></body></html>"
    )


if __name__ == "__main__":
    # N-5 PRIORITY 1 -- an independent build step, never a briefing.py modification (see
    # n5_public_integration_decision.json). Invoked as its own shell step in daily.yml, after
    # `python briefing.py build` has produced site/, and before the gh-pages commit -- so it
    # writes into an already-built site/ tree without briefing.py ever importing or calling it.
    site_dir = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "site")
    result = build_public_intelligence_pages(site_dir)
    print(json.dumps(result, ensure_ascii=False))
    # Failure isolation at the process level too: errors are reported in `result`, never raised,
    # so a non-zero exit here would be the only way this step could ever block site publishing --
    # and it doesn't, because build_public_intelligence_pages() never raises.
