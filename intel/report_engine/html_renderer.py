# N-3 Section 25 -- minimal Report JSON -> HTML renderer. Deliberately plain (no design pass):
# verifies heading/section/status-badge/claim/evidence/statistics/research/uncertainty/gap/source
# all render, nothing more. The HTML is a VIEW of the JSON -- it is never a second source of truth,
# so this renderer reads fields only, never recomputes section content.
import html as _html


def _esc(x):
    return _html.escape(str(x)) if x is not None else ""


def _badge(status):
    return f'<span class="status-badge status-{status.lower()}">{_esc(status)}</span>'


def _render_block(block):
    if isinstance(block, str):
        return f"<li>{_esc(block)}</li>"
    if isinstance(block, dict):
        if "text" in block:
            extra = f' ({_esc(block.get("claim_status"))})' if "claim_status" in block else ""
            return f"<li>{_esc(block['text'])}{extra}</li>"
        if "indicator" in block:
            return (f"<li>{_esc(block['indicator'])} -- {_esc(block['source'])} "
                    f"({_esc(block['geography'])}, {_esc(block['period'])}): "
                    f"{_esc(block['observation_count'])}건, 추세={_esc(block['trend_status'])}</li>")
        if "title" in block:
            return f"<li>{_esc(block.get('title'))} ({_esc(block.get('identity_type'))}: {_esc(block.get('identity_value'))})</li>"
        return f"<li>{_esc(block)}</li>"
    return f"<li>{_esc(block)}</li>"


def render_section_html(section):
    blocks_html = "".join(_render_block(b) for b in section.get("content_blocks", []))
    note = f"<p class='search-note'>{_esc(section['search_outcome_note'])}</p>" if "search_outcome_note" in section else ""
    return (f'<section class="report-section" id="{_esc(section.get("section_id") or section.get("section_type"))}">'
            f'<h2>{_esc(section["section_type"])} {_badge(section["status"])}</h2>'
            f'{note}<ul>{blocks_html}</ul></section>')


def render_report_html(view_report):
    sections_html = "".join(render_section_html(s) for s in view_report["sections"].values())
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{_esc(view_report['topic'])} Intelligence Report</title></head><body>"
        f"<h1>{_esc(view_report['topic'])} {_badge(view_report['readiness'])}</h1>"
        f"<p>report_id={_esc(view_report['report_id'])} version={_esc(view_report['version'])} "
        f"view={_esc(view_report.get('view', 'UNKNOWN'))}</p>"
        f"{sections_html}</body></html>"
    )
