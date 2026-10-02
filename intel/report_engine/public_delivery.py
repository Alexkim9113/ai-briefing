# N-4B Section 15-23 -- Public Intelligence Page delivery. A thin delivery layer only: it reuses
# the exact same build_public_view() + build_presentation() + render_product_html() already used
# and tested in N-4, and writes their output as PREBUILT static files under site/intelligence/,
# matching this project's existing static-site convention (every other page -- category archives,
# the editor, feeds -- is written the same way by briefing.py's build()). No new renderer, no
# request-time computation: this runs only at build time, same as the rest of the site.
import json
import re as _re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import report_engine as re_  # noqa: E402
import presentation_model as pm  # noqa: E402
import product_html as ph  # noqa: E402
import atomic_publish as apub  # noqa: E402
import source_registry as sreg  # noqa: E402

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
            # O-1E: a non-document provenance id (e.g. "event:evt_...") must not be shown as the
            # card's visible title in Public -- it is an internal reference, not reader-facing
            # text. Use a neutral label; the raw id is still available to Operator via the
            # canonical JSON, never altered here.
            title = ph._public_source_label(sid) if (sid or "").startswith(("event:", "claim_",
                "series_", "intel_", "hyp_", "evt_", "rel_")) else sid
            cards.append({"title": title, "publisher": "NON_DOCUMENT_PROVENANCE", "date": "UNKNOWN",
                          "access_status": "UNKNOWN", "rights_status": "UNKNOWN"})
    return cards


def discover_real_reports():
    """Section 19 -- the Public Intelligence Index is built from the real reports that already
    exist on disk, never a hardcoded list. No automatic mass exposure of future topics beyond
    what the Report Engine has actually produced (Section 27's no-mass-exposure rule)."""
    return sorted(REPORTS_DIR.glob("report_intel_*_v*.json"))


def build_index_card_summary(report):
    """Section 7 (O-3 revision) -- a short (3-5 sentence), Korean-first reader summary for the
    Public Intelligence Index card. Previously this was the raw CURRENT_STATE[0] content block --
    the full multi-thousand-character canonical synthesis paragraph, unsuitable as a card summary
    and exposing internal enum tags verbatim. This now composes a short summary ONLY from fields
    already derived by presentation_model.build_executive_card() (current_state sentence,
    key_signal, major_uncertainty) -- no new text is invented, no LLM paraphrase, nothing beyond
    what the Presentation Model already computes from the canonical Report JSON. Each component
    still goes through product_html's PUBLIC-view id-stripping + editorial translation layer, so
    the card never shows a raw enum/id/internal phrase either."""
    card = pm.build_executive_card(report)
    current_state = ph._strip_internal_ids(ph._narrative_text(card["current_state"]), "PUBLIC")
    key_signal_raw = ph._narrative_text(card["key_signal"])
    major_uncertainty = ph._strip_internal_ids(ph._narrative_text(card["major_uncertainty"]), "PUBLIC")

    def _first_sentences(text, n, max_chars):
        # Split on sentence-ending punctuation NOT immediately preceded/followed by a digit, so a
        # decimal number (e.g. "12393.4") or a numbered clause doesn't get mistaken for a
        # sentence break.
        parts = [p.strip() for p in _re.split(r"(?<![0-9])[.!?](?!\d)\s+", text) if p.strip()]
        out = " ".join(parts[:n]) if parts else text
        if len(out) > max_chars:
            out = out[:max_chars].rsplit(" ", 1)[0] + "..."
        return out

    sentences = [_first_sentences(current_state, 2, 220)]
    if card["key_signal_status"] == "KEY_SIGNAL_PRESENT":
        key_signal = ph._strip_internal_ids(key_signal_raw, "PUBLIC")
        sentences.append("현재 판단: " + _first_sentences(key_signal, 1, 160))
    else:
        sentences.append("현재 판단: 아직 확정적으로 뒷받침된 핵심 신호가 없습니다.")
    if major_uncertainty and major_uncertainty not in ("없음", "UNKNOWN"):
        sentences.append("아직 불확실한 점: " + _first_sentences(major_uncertainty, 1, 120))
    return " ".join(s for s in sentences if s).strip()


def build_intelligence_index_entry(report_path):
    r = json.loads(report_path.read_text(encoding="utf-8"))
    pdf_path = REPORTS_DIR / f"{report_path.stem}.pdf"
    summary = build_index_card_summary(r)
    # Priority 4 (O-2C reader-flow review): same presentation-only human-readable headline as the
    # detail page (pm.TOPIC_DISPLAY_TITLES) -- the Index listing is the first thing a reader sees,
    # so it must not show the raw topic_id either. r["topic"] itself is untouched.
    title = pm.TOPIC_DISPLAY_TITLES.get(r["topic"]) or f"{r['topic']} Intelligence Report"
    return {
        "report_id": r["report_id"],
        "intelligence_id": r["intelligence_id"],
        "topic": r["topic"],
        "title": title,
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


def latest_report_paths():
    """O-1D fix -- discover_real_reports() returns every version file ever produced for every
    intelligence_id (append-only, by design). The Public Intelligence Index must show the
    CURRENT state of each intelligence object, not one duplicate row per historical version, so
    this groups by intelligence_id (the report filename prefix before '_v{N}.json') and keeps
    only the highest version per topic. Older version files are untouched on disk and their
    detail pages are still generated (see build_public_intelligence_pages) -- this function only
    narrows what appears as the PRIMARY/listed entry on the index."""
    by_intel_id = {}
    for p in discover_real_reports():
        # filename is report_{intelligence_id}_v{N}.json
        stem = p.stem  # report_{intelligence_id}_v{N}
        prefix, _, vpart = stem.rpartition("_v")
        try:
            version = int(vpart)
        except ValueError:
            version = -1
        best = by_intel_id.get(prefix)
        if best is None or version > best[0]:
            by_intel_id[prefix] = (version, p)
    return sorted(path for _, path in by_intel_id.values())


def build_report_index():
    """Section 20 -- minimal Report Search/Index. No full-body duplication: just the fields a
    list/search view needs. Lists only the latest version per intelligence_id (see
    latest_report_paths) so the Public Index shows one current row per topic."""
    return [build_intelligence_index_entry(p) for p in latest_report_paths()]


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
    real_sources = sreg.build_sources_for_report(r)
    html_doc = ph.render_product_html(presentation, source_cards=cards, view="PUBLIC",
                                       real_sources=real_sources)
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
    # N-6 PRIORITY 1 -- every write below that can overwrite a previously-published, valid file
    # (detail page HTML, copied PDF, the index page, index.json) goes through atomic_publish's
    # temp-write + validate + os.replace. A failed validation or write leaves the existing file
    # untouched and is recorded in status["errors"] -- it never silently clobbers a good page with
    # a half-written one.
    documents_by_id = re_._load(re_.DOCUMENTS_PATH)
    status = {"pages_written": [], "errors": []}
    intel_dir = Path(site_dir) / "intelligence"
    try:
        intel_dir.mkdir(parents=True, exist_ok=True)
        index = build_report_index()
        # Detail pages are written for EVERY version on disk (historical pages stay reachable by
        # direct link/old bookmarks, per the brief's "old v1 links can stay as historical"), while
        # `index` (above) lists only the latest version per topic -- see latest_report_paths().
        all_entries = [build_intelligence_index_entry(p) for p in discover_real_reports()]
        for report_path, entry in zip(discover_real_reports(), all_entries):
            try:
                html_doc, pdf_exists = render_public_page_for_report(report_path, documents_by_id)
                page_dir = intel_dir / entry["report_id"]
                page_dir.mkdir(parents=True, exist_ok=True)
                html_result = apub.atomic_write(page_dir / "index.html", html_doc,
                                                 validator=apub.html_validator)
                if html_result["status"] != "PUBLISHED":
                    raise RuntimeError(f"detail page publish failed: {html_result['error']}")
                if pdf_exists:
                    pdf_src = REPORTS_DIR / f"{report_path.stem}.pdf"
                    pdf_result = apub.atomic_write(
                        page_dir / "report.pdf", pdf_src.read_bytes(),
                        validator=lambda p: p.stat().st_size > 0 and p.read_bytes()[:5] == b"%PDF-")
                    if pdf_result["status"] != "PUBLISHED":
                        raise RuntimeError(f"PDF copy publish failed: {pdf_result['error']}")
                status["pages_written"].append(entry["report_id"])
            except Exception as e:  # noqa: BLE001 -- one bad report must not block the others
                status["errors"].append({"report_id": entry.get("report_id"), "error": str(e)})

        index_html = _render_index_page(index)
        index_html_result = apub.atomic_write(intel_dir / "index.html", index_html,
                                               validator=apub.html_validator)
        if index_html_result["status"] != "PUBLISHED":
            status["errors"].append({"report_id": None, "error": index_html_result["error"]})
        index_json_result = apub.atomic_write(
            intel_dir / "index.json", json.dumps(index, ensure_ascii=False, indent=1),
            validator=apub.json_validator)
        if index_json_result["status"] != "PUBLISHED":
            status["errors"].append({"report_id": None, "error": index_json_result["error"]})
    except Exception as e:  # noqa: BLE001
        status["errors"].append({"report_id": None, "error": str(e)})
    return status


# O-3: Index card "evidence status" pill in Korean, a UI label over the existing report-level
# `readiness` enum (READY/CONDITIONALLY_READY/BLOCKED) -- never a new status, never recomputed.
_READINESS_KO = {
    "READY": "근거 충분",
    "CONDITIONALLY_READY": "조건부 근거 확인",
    "BLOCKED": "근거 부족",
}


def _render_index_page(index):
    import html as _html

    def _row(e):
        pdf_link = ""
        if e["available_formats"]["pdf"]:
            href = _html.escape(e["report_id"]) + "/report.pdf"
            pdf_link = f" <a class='pdf' href='{href}'>PDF</a>"
        # O-3: summary is now already a short, derived, PUBLIC-stripped card summary (see
        # build_index_card_summary) -- this defensive strip is kept in case of future callers that
        # pass a raw block, never relied on to do the shortening itself.
        summary = ph._strip_internal_ids(str(e["summary"]), "PUBLIC")
        readiness_ko = _READINESS_KO.get(e["readiness"], e["readiness"])
        return (
            f'<li><h2><a href="{_html.escape(e["report_id"])}/">{_html.escape(e["title"])}</a></h2>'
            f'<p>{_html.escape(summary)}</p>'
            f'<p class="pills">'
            f'<span class="badge">{_html.escape(e.get("topic", ""))}</span> '
            f'<span class="badge">근거 상태: {_html.escape(readiness_ko)}</span> '
            f'<span class="badge">v{_html.escape(str(e.get("version", "")))}</span> '
            f'<span class="meta">업데이트 {_html.escape(e["updated_at"][:10])}</span>{pdf_link}</p>'
            f'<p><a class="detail-link" href="{_html.escape(e["report_id"])}/">보고서 보기 →</a></p></li>'
        )

    rows = "".join(_row(e) for e in index)
    # Priority 2 (O-2C responsive measurement): this page had no stylesheet at all, so a long
    # unbroken token in a report's own summary text (e.g. a slash-joined internal section-type
    # list with no spaces) forced the whole page to a ~860px min-content width regardless of the
    # actual viewport, overflowing at 375/390/768px -- a real, Playwright-measured bug, not a
    # cosmetic one. Minimal CSS only (no visual redesign): the same overflow-wrap/word-break
    # affordance product_html.py's CSS already applies to report body text.
    css = (
        "html{overflow-x:hidden}*{box-sizing:border-box}"
        "body{font-family:'Pretendard Variable','Pretendard',-apple-system,BlinkMacSystemFont,"
        "'Malgun Gothic',sans-serif;max-width:760px;margin:0 auto;padding:32px 20px;"
        "line-height:1.6;overflow-wrap:break-word;word-break:break-word}"
        "a{overflow-wrap:anywhere;word-break:break-word}"
        "ul{padding-left:20px}"
        "a:focus-visible{outline:2px solid #3552c9;outline-offset:2px}"
        "@media (max-width:480px){body{padding:20px 14px}}"
    )
    return (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>Intelligence Reports</title><style>{css}</style></head><body>"
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
