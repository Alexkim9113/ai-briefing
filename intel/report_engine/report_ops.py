# N-4B Sections 24-33 -- Report Operations: content-hash NO_CHANGE detection, incremental build
# (reusing find_affected_reports -> build_report, never a full corpus rebuild), and build-failure
# isolation across REPORT_JSON -> HTML -> PDF. This module ORCHESTRATES the existing, unmodified
# report_engine.py/product_html.py/pdf_pipeline.py functions -- it adds no new Report schema and
# no new PDF path.
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import report_engine as re_  # noqa: E402
import presentation_model as pm  # noqa: E402
import product_html as ph  # noqa: E402
import pdf_pipeline as pp  # noqa: E402

ARTIFACT_STATES = ("REPORT_JSON_READY", "HTML_READY", "PDF_READY", "PDF_FAILED", "NO_CHANGE")


def _content_signature(report):
    """Section 25 -- the three existing snapshot hashes together are the content identity of a
    Report's inputs. If all three match the latest saved version, nothing about the evidence
    graph that feeds this report has changed."""
    return (report["claim_snapshot"], report["evidence_snapshot"], report["source_snapshot"])


def _latest_saved_version(intelligence_id):
    versions = sorted(re_.REPORTS_DIR.glob(f"report_{intelligence_id}_v*.json"))
    if not versions:
        return None
    return re_._load(versions[-1])


def build_or_no_change(intelligence_id, **build_kwargs):
    """Section 26 -- rebuilding from an unchanged input signature returns NO_CHANGE instead of a
    spurious new version. build_report() itself always computes the next version number and never
    writes to disk on its own (save_report() does that) -- so NO_CHANGE here simply means: compute
    the candidate report, compare its content signature to the latest saved version, and skip
    save_report() if nothing changed."""
    latest = _latest_saved_version(intelligence_id)
    candidate = re_.build_report(intelligence_id, **build_kwargs)
    if candidate is None:
        return {"status": "NOT_FOUND", "intelligence_id": intelligence_id}
    if latest is not None and _content_signature(latest) == _content_signature(candidate):
        return {"status": "NO_CHANGE", "report_id": latest["report_id"], "intelligence_id": intelligence_id}
    path = re_.save_report(candidate)
    return {"status": "NEW_VERSION", "report_id": candidate["report_id"], "path": str(path),
            "report": candidate}


def rebuild_affected(new_evidence_topic, **build_kwargs):
    """Section 29-30 -- incremental build: only Intelligence Objects whose topic matches the new
    evidence are rebuilt. Reuses find_affected_reports(), which itself wraps the existing M.6
    incremental_update.find_affected_objects() -- no new incremental engine."""
    objects = re_._load(re_.ROOT / "intel" / "intelligence_objects" / "intelligence_objects.json")
    affected_ids = re_.find_affected_reports(new_evidence_topic, objects)
    results = {}
    for intelligence_id in affected_ids:
        results[intelligence_id] = build_or_no_change(intelligence_id, **build_kwargs)
    return results


def build_artifacts_with_failure_isolation(report, documents_by_id, view="PUBLIC"):
    """Section 31-33 -- each stage's failure is isolated: a PDF failure must never remove or
    invalidate the Report JSON or HTML that already succeeded. Returns one ARTIFACT_STATES value
    per stage; callers should treat REPORT_JSON_READY/HTML_READY as independently trustworthy even
    when PDF_FAILED."""
    status = {"report_json": "REPORT_JSON_READY"}  # report is already an in-memory dict at this point

    try:
        if view == "PUBLIC":
            view_report = re_.build_public_view(report)
        else:
            view_report = re_.build_operator_view(report)
        presentation = pm.build_presentation(view_report)
        prov_blocks = view_report["sections"]["SOURCE_PROVENANCE"].get("content_blocks", [])
        cards = []
        for b in prov_blocks:
            sid = b.get("source_id")
            if sid in documents_by_id:
                cards.append(re_.build_source_card(documents_by_id[sid]))
            else:
                cards.append({"title": sid, "publisher": "NON_DOCUMENT_PROVENANCE", "date": "UNKNOWN",
                              "access_status": "UNKNOWN", "rights_status": "UNKNOWN"})
        html_doc = ph.render_product_html(presentation, source_cards=cards, view=view)
        status["html"] = "HTML_READY"
        status["html_doc"] = html_doc
    except Exception as e:  # noqa: BLE001 -- an HTML failure must not raise past this point either
        status["html"] = "HTML_FAILED"
        status["html_error"] = str(e)
        return status  # no HTML means no print HTML to convert -- PDF stage cannot run

    tmp_html = re_.REPORTS_DIR / f"{report['report_id']}_tmp_print.html"
    tmp_pdf = re_.REPORTS_DIR / f"{report['report_id']}_tmp.pdf"
    try:
        print_html = pp.render_print_html(presentation, source_cards=cards, view=view)
        tmp_html.write_text(print_html, encoding="utf-8")
        pp.generate_pdf(tmp_html, tmp_pdf)
        validation = pp.validate_pdf(tmp_pdf)
        status["pdf"] = "PDF_READY" if validation["ok"] else "PDF_FAILED"
        status["pdf_validation"] = validation
    except Exception as e:  # noqa: BLE001 -- Section 32: PDF failure never blocks REPORT_JSON/HTML
        status["pdf"] = "PDF_FAILED"
        status["pdf_error"] = str(e)
    finally:
        tmp_html.unlink(missing_ok=True)
        tmp_pdf.unlink(missing_ok=True)

    return status
