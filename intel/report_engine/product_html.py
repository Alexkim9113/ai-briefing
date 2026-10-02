# N-4 -- Report UX / HTML Productization. Renders a Presentation Model (presentation_model.py)
# into reader-facing HTML. This module NEVER computes facts: every value it prints comes from the
# Presentation Model, which itself only re-arranges the N-3 canonical Report JSON. No new claim,
# evidence, status, chart value, or source is invented here.
#
# Design intent (N-4 Section 50-51): a document to read, not an "automated report" -- minimal
# chrome, no gradients, no decorative badges beyond the existing Evidence Status vocabulary, no
# invented icons. Typography: Pretendard for body text, Space Grotesk for numbers/metadata, with a
# system-font fallback chain so a missing font embed never breaks the page.
import html as _html
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import presentation_model as pm  # noqa: E402

CSS = """
:root{--ink:#1a1a1a;--sub:#5a5a5a;--line:#dcdcdc;--bg:#ffffff;--accent-red:#b3261e;
--accent-amber:#8a5a00;--accent-violet:#4b3f8a;--good:#1e5c3a}
html{overflow-x:hidden}
*{box-sizing:border-box}
body{font-family:'Pretendard',-apple-system,BlinkMacSystemFont,'Malgun Gothic',sans-serif;
color:var(--ink);background:var(--bg);max-width:760px;margin:0 auto;padding:32px 20px;
line-height:1.65;font-size:16px;overflow-wrap:break-word}
.mono,.meta,.chart-row td:nth-child(n+2){font-family:'Space Grotesk','Pretendard',monospace;
overflow-wrap:anywhere;word-break:break-word}
h1{font-size:1.6em;margin-bottom:4px;overflow-wrap:break-word}
.chart-table-wrap{overflow-x:auto}
@media (max-width: 480px){
  body{padding:20px 14px;font-size:15px}
  h1{font-size:1.3em}
}
h2{font-size:1.15em;border-top:1px solid var(--line);padding-top:18px;margin-top:28px}
.meta{color:var(--sub);font-size:0.85em;margin-bottom:24px}
.badge{display:inline-block;border:1px solid var(--line);border-radius:3px;padding:1px 8px;
font-size:0.75em;letter-spacing:.03em;margin-left:6px;max-width:100%;overflow-wrap:break-word;
word-break:break-word;white-space:normal}
.badge-ready,.badge-supported{border-color:var(--good);color:var(--good)}
.badge-conditionally_ready,.badge-partially_supported{border-color:var(--accent-amber);color:var(--accent-amber)}
.badge-insufficient_evidence,.badge-contested{border-color:var(--accent-violet);color:var(--accent-violet)}
.badge-blocked,.badge-rejected{border-color:var(--accent-red);color:var(--accent-red)}
.exec-card{border:1px solid var(--line);border-radius:4px;padding:16px 18px;margin:18px 0 28px}
.exec-card dt{color:var(--sub);font-size:0.78em;text-transform:uppercase;letter-spacing:.04em;margin-top:10px}
.exec-card dt:first-child{margin-top:0}
.exec-card dd{margin:2px 0 0}
section.hidden{display:none}
ul{padding-left:20px}
.chart-table{border-collapse:collapse;width:100%;margin:8px 0}
.chart-table td,.chart-table th{border:1px solid var(--line);padding:4px 8px;font-size:0.9em;text-align:left}
.cite{font-size:0.8em;vertical-align:super;color:var(--accent-violet)}
.sources li{font-size:0.9em}
.axis-note{color:var(--sub);font-size:0.78em}
footer{margin-top:40px;color:var(--sub);font-size:0.78em;border-top:1px solid var(--line);padding-top:12px}
a:focus-visible,button:focus-visible{outline:2px solid var(--accent-violet);outline-offset:2px}
"""


def _esc(x):
    return _html.escape(str(x)) if x is not None else ""


def _badge(value):
    slug = str(value).lower()
    return f'<span class="badge badge-{_esc(slug)}">{_esc(value)}</span>'


def render_executive_card(card):
    return (
        '<section aria-label="Executive Intelligence" class="exec-card">'
        f'<dl><dt>Current State</dt><dd>{_esc(card["current_state"])}</dd>'
        f'<dt>Key Signal</dt><dd>{_esc(card["key_signal"])} {_badge(card["key_signal_status"])}</dd>'
        f'<dt>Evidence Status</dt><dd>{_badge(card["evidence_status"])}</dd>'
        f'<dt>Major Uncertainty</dt><dd>{_esc(card["major_uncertainty"])}</dd>'
        f'<dt>What To Watch</dt><dd><ul>{"".join(f"<li>{_esc(w)}</li>" for w in card["what_to_watch"])}</ul></dd>'
        '</dl></section>'
    )


def _render_chart(chart):
    rows = (
        f"<tr><td>Indicator</td><td>{_esc(chart['indicator'])}</td></tr>"
        f"<tr><td>Geography</td><td>{_esc(chart['geography'])}</td></tr>"
        f"<tr><td>Period</td><td>{_esc(chart['period'])}</td></tr>"
        f"<tr><td>Source</td><td>{_esc(chart['source'])}</td></tr>"
        f"<tr><td>Trend</td><td>{_badge(chart['trend_status'])}</td></tr>"
    )
    caption = (f"Statistical series: {_esc(chart['indicator'])} "
               f"({_esc(chart['geography'])}, {_esc(chart['period'])}) -- "
               f"chart type {_esc(chart['visualization_type'])}, no forecast line, "
               f"no AI-attribution overlay.")
    return (f'<div class="chart-table-wrap"><table class="chart-table" role="table" aria-label="{caption}">'
            f'<caption class="axis-note">{caption}</caption>{rows}</table></div>'
            f'<p class="axis-note">{_esc(chart["axis_note"])}</p>')


def _render_block(block, section_type):
    if isinstance(block, str):
        return f"<li>{_esc(block)}</li>"
    if not isinstance(block, dict):
        return f"<li>{_esc(block)}</li>"
    if "text" in block:
        status = block.get("claim_status")
        extra = f" {_badge(status)}" if status else ""
        return f"<li>{_esc(block['text'])}{extra}</li>"
    if "indicator" in block:
        return f"<li>{_render_chart(pm.build_statistics_chart_spec(block))}</li>"
    if "title" in block:
        return (f"<li>{_esc(block.get('title'))} "
                f"({_esc(block.get('identity_type'))}: {_esc(block.get('identity_value'))})</li>")
    if "node_type" in block:
        # EVIDENCE_MAP entries carry internal graph node references ({'node_type': ..., 'id': ...}).
        # Per the Public/Operator boundary (never expose internal Claim/Evidence/Hypothesis IDs in
        # Public), render a neutral, human-readable label instead of the raw dict repr / internal ID.
        label = str(block.get("node_type", "")).replace("_", " ").title() or "Evidence item"
        return f"<li>{_esc(label)} reference (internal id withheld in Public view)</li>"
    return f"<li>{_esc(block)}</li>"


def render_section(entry):
    section = entry["section"]
    hidden_cls = " hidden" if entry["visibility"] == "HIDDEN" else ""
    note = (f"<p class='search-note'>{_esc(section['search_outcome_note'])}</p>"
            if "search_outcome_note" in section else "")
    if section["status"] == "INSUFFICIENT_EVIDENCE" and not section.get("content_blocks"):
        body = "<p class='axis-note'>Insufficient evidence in the current search scope.</p>"
    else:
        body = f"<ul>{''.join(_render_block(b, entry['section_type']) for b in section.get('content_blocks', []))}</ul>"
    return (
        f'<section class="report-section{hidden_cls}" id="{_esc(entry["section_type"].lower())}" '
        f'aria-labelledby="{_esc(entry["section_type"].lower())}-h">'
        f'<h2 id="{_esc(entry["section_type"].lower())}-h">{_esc(entry["display_title"])} '
        f'{_badge(section["status"])}</h2>{note}{body}</section>'
    )


def render_sources(source_cards):
    items = []
    for i, card in enumerate(source_cards, 1):
        items.append(
            f'<li id="src-{i}"><span class="cite">[{i}]</span> '
            f'{_esc(card.get("title"))} -- {_esc(card.get("publisher") or card.get("source_id"))} '
            f'({_esc(card.get("date"))}) '
            f'[{_esc(card.get("access_status", "UNKNOWN"))}/{_esc(card.get("rights_status", "UNKNOWN"))}]'
            f'{" DOI:" + _esc(card["doi"]) if card.get("doi") else ""}</li>'
        )
    return f'<section aria-label="Sources"><h2>Sources</h2><ol class="sources">{"".join(items)}</ol></section>'


def render_product_html(presentation, source_cards=None, view="PUBLIC"):
    sections_html = "".join(render_section(e) for e in presentation["sections"])
    sources_html = render_sources(source_cards) if source_cards else ""
    return (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{_esc(presentation['display_title'])}</title><style>{CSS}</style></head><body>"
        f"<main aria-label='Intelligence Report'>"
        f"<h1>{_esc(presentation['display_title'])} {_badge(presentation['readiness'])}</h1>"
        f"<p class='meta'>report_id={_esc(presentation['report_id'])} "
        f"version={_esc(presentation['version'])} view={_esc(view)}</p>"
        f"{render_executive_card(presentation['executive_card'])}"
        f"{sections_html}"
        f"{sources_html}"
        f"<footer>METAXIS Intelligence Observatory -- structured evidence, not editorial conclusions.</footer>"
        f"</main></body></html>"
    )
