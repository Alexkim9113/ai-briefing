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


def _narrative_text(value):
    # O-1G: a narrative field can be a structured {"cause": ..., "detail": ...} block
    # (e.g. an UNCERTAINTIES content block) rather than a plain string. str() on a dict
    # leaks a raw Python repr ("{'cause': ...}") into Public HTML -- render it as a
    # readable sentence instead, preserving the same meaning, not inventing new content.
    if isinstance(value, dict):
        cause = value.get("cause")
        detail = value.get("detail")
        if cause and detail:
            return f"{detail} ({cause})"
        if detail:
            return str(detail)
        if cause:
            return str(cause)
        return ", ".join(f"{k}: {v}" for k, v in value.items())
    return str(value)


def render_executive_card(card):
    # O-1F: these free-text narrative fields (current_state/key_signal/major_uncertainty/
    # what_to_watch) can themselves embed internal ids/repo file paths (same family as the
    # content_block narrative fields below) -- stripped the same way, meaning preserved.
    current_state = _strip_internal_ids(_narrative_text(card["current_state"]))
    key_signal = _strip_internal_ids(_narrative_text(card["key_signal"]))
    major_uncertainty = _strip_internal_ids(_narrative_text(card["major_uncertainty"]))
    what_to_watch = [_strip_internal_ids(_narrative_text(w)) for w in card["what_to_watch"]]
    return (
        '<section aria-label="Executive Intelligence" class="exec-card">'
        f'<dl><dt>Current State</dt><dd>{_esc(current_state)}</dd>'
        f'<dt>Key Signal</dt><dd>{_esc(key_signal)} {_badge(card["key_signal_status"])}</dd>'
        f'<dt>Evidence Status</dt><dd>{_badge(card["evidence_status"])}</dd>'
        f'<dt>Major Uncertainty</dt><dd>{_esc(major_uncertainty)}</dd>'
        f'<dt>What To Watch</dt><dd><ul>{"".join(f"<li>{_esc(w)}</li>" for w in what_to_watch)}</ul></dd>'
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
        # O-1F: bare-string content_blocks (e.g. SOURCE_PROVENANCE's source_ids) can themselves be
        # internal repo file paths (e.g. "intel/hypothesis/hypotheses.json#...") rather than a real
        # URL -- strip the same way structural fields are stripped elsewhere on this page.
        return f"<li>{_esc(_strip_internal_ids(block))}</li>"
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
    if "policy" in block and "status" in block:
        # POLICY_CONTEXT content blocks ({'policy':..., 'status':..., 'detail':...}).
        policy = _esc(block.get("policy"))
        detail = _esc(block.get("detail", ""))
        return (f"<li><strong>{policy}</strong> {_badge(block['status'])}"
                f"{': ' + detail if detail else ''}</li>")
    if "direction" in block and "status" in block:
        # COUNTEREVIDENCE / ALTERNATIVE_EXPLANATIONS content blocks
        # ({'direction':..., 'status':..., 'source' or 'note':...}).
        direction = _esc(block.get("direction"))
        extra = block.get("source") or block.get("note") or ""
        return (f"<li>{direction} {_badge(block['status'])}"
                f"{': ' + _esc(extra) if extra else ''}</li>")
    if "cause" in block and "detail" in block:
        # UNCERTAINTIES content blocks ({'cause': ..., 'detail': ...}) -- same dict-repr-fallback
        # bug family as the other structural fields here (O-1G); render as a readable sentence.
        return f"<li>{_esc(block['detail'])} ({_esc(block['cause'])})</li>"
    if "node_type" in block:
        # EVIDENCE_MAP entries carry internal graph node references ({'node_type': ..., 'id': ...}).
        # Per the Public/Operator boundary (never expose internal Claim/Evidence/Hypothesis IDs in
        # Public), render a neutral, human-readable label instead of the raw dict repr / internal ID.
        label = str(block.get("node_type", "")).replace("_", " ").title() or "Evidence item"
        return f"<li>{_esc(label)} reference (internal id withheld in Public view)</li>"
    if "period_start" in block or "period_end" in block:
        # TEMPORAL_CONTEXT entries ({'period_start':..., 'period_end':..., 'source': <series_/evt_
        # id or a real document path>, 'note': ...}). The 'source' field is internal provenance,
        # not reader-facing text -- a bare series_/evt_/claim_/intel_/hyp_ id must never be shown
        # (O-1E: this fell through to the raw dict-repr fallback below and leaked series_/evt_ IDs).
        source = block.get("source")
        source_label = _public_source_label(source)
        text = f"{_esc(block.get('period_start'))} - {_esc(block.get('period_end'))} ({_esc(source_label)})"
        if block.get("note"):
            text += f" -- {_esc(block['note'])}"
        return f"<li>{text}</li>"
    if "geography" in block and "basis" in block:
        # GEOGRAPHIC_CONTEXT entries ({'geography':..., 'basis':..., 'scope': <free text that may
        # itself mention an internal evt_/claim_/series_ id>}). Structural provenance data, same
        # dict-repr-fallback bug family as EVIDENCE_MAP/TEMPORAL_CONTEXT (O-1E).
        scope = _strip_internal_ids(str(block.get("scope", "")))
        basis = _strip_internal_ids(str(block.get("basis", "")))
        return (f"<li>{_esc(block.get('geography'))} ({_esc(basis)})"
                f"{': ' + _esc(scope) if scope else ''}</li>")
    if "source_id" in block:
        # SOURCE_PROVENANCE entries ({'source_id': <url, or 'event:evt_...'>, 'note': ...}). A real
        # URL is reader-facing provenance and is shown as-is; an internal id reference (e.g.
        # 'event:evt_...') is replaced with a neutral label (O-1E).
        source_label = _public_source_label(block.get("source_id"))
        text = _esc(source_label)
        if block.get("note"):
            text += f" -- {_esc(block['note'])}"
        return f"<li>{text}</li>"
    if "reason" in block and "gap_type" in block:
        # KNOWN_GAPS / EVIDENCE_GAPS entries ({'gap_type':..., 'reason': <free-text narrative that
        # may itself reference internal claim_/hyp_/intel_/series_ ids, e.g. "migrated to canonical
        # Claims claim_a11c5.../claim_f584...">, 'status':...}). This previously fell through to the
        # raw dict-repr fallback below, which is how O-1F found bare claim_/intel_...json ids baked
        # into the AI_ENERGY_INFRA Report v4 narrative text leaking onto the Public page. The ids
        # here are threaded through dense, multi-paragraph internal engineering narrative (file
        # paths, numbered audit conditions) without a single clean referent, so -- consistent with
        # the O-1D/O-1E precedent of not forcing an unsafe substitution -- we withhold the bare id
        # tokens with the same neutral placeholder used for structural fields elsewhere on this
        # page, rather than inventing a human label we cannot derive with confidence. This never
        # changes the sentence's meaning, only withholds the internal identifier substrings.
        gap_type_raw = block.get("gap_type")
        if gap_type_raw == "HYPOTHESIS_MODEL_QUALITY_WEIGHTING_GAP":
            # O-1G: this gap's canonical 'reason' is dense internal audit prose (a multi-paragraph
            # engineering changelog) that survives ID-stripping as a wall of jargon. Canonical text
            # (intelligence_objects.json) is left untouched; this is a presentation-only, reader-
            # facing summary of the same meaning: some supporting evidence for these hypotheses was
            # not yet verified against a traceable source and so was excluded or downweighted when
            # the hypotheses were evaluated; it has since been reconnected to a source wherever that
            # could be confirmed, but one combined evidence-quality score for every hypothesis does
            # not exist yet, so the underlying evaluation logic can still revert a hypothesis to its
            # plain evidence-count status the next time its evidence list changes.
            reason = (
                "Some of the evidence behind these hypotheses had not yet been verified against a "
                "traceable source, so it was excluded or given less weight when the hypotheses were "
                "evaluated. Where that evidence could later be confirmed against a real source, it was "
                "reconnected. There is still no single combined evidence-quality score across all "
                "hypotheses, so this remains a partial fix rather than a complete one."
            )
        else:
            reason = _strip_internal_ids(str(block.get("reason", "")))
        gap_type = _esc(gap_type_raw)
        status = block.get("status")
        extra = f" {_badge(status)}" if status else ""
        return f"<li><strong>{gap_type}</strong>: {_esc(reason)}{extra}</li>"
    return f"<li>{_esc(block)}</li>"


_INTERNAL_ID_PREFIXES = ("claim_", "series_", "intel_", "hyp_", "evt_", "rel_", "event:evt_")


import re as _re

_INTERNAL_ID_RE = _re.compile(
    r"\b(?:claim_|series_|intel_|hyp_|evt_|rel_|event:evt_)[a-zA-Z0-9_]*"
)

# O-1F: the EVIDENCE_WEIGHTING_GAP known_gaps 'reason' narrative also threads in bare repo file
# paths/filenames (e.g. "intel/hypothesis/hypothesis_model.py", "o1b_contradiction_resolution.json")
# and internal function names (e.g. "evaluate_hypothesis_sufficiency()") alongside the canonical
# ids above. These are mechanical, low-risk substitutions -- a filename or path token withheld in
# place leaves the surrounding sentence's meaning intact -- unlike the dense multi-condition prose
# around them, which we do not attempt to rewrite (see the EVIDENCE_WEIGHTING_GAP branch above).
_INTERNAL_PATH_RE = _re.compile(
    r"\b(?:intel/[a-zA-Z0-9_./-]+|[a-zA-Z_][a-zA-Z0-9_]*\.(?:json|py))\b"
    r"|\b[a-zA-Z_][a-zA-Z0-9_]*\(\)"
)


def _strip_internal_ids(text):
    """Public-view-only: replaces any bare internal id token embedded inside an otherwise
    human-readable structural-field string with a neutral placeholder, without altering the
    surrounding sentence/meaning."""
    text = _INTERNAL_ID_RE.sub("[internal id withheld in Public view]", text)
    text = _INTERNAL_PATH_RE.sub("[internal reference withheld in Public view]", text)
    return text


def _public_source_label(source):
    """Public-view-only: a 'source' / 'source_id' value that is itself an internal id (not a
    real document URL/path) is replaced with a neutral label. Real URLs/paths pass through
    unchanged -- this never invents or alters any fact, it only withholds an internal id."""
    s = str(source) if source is not None else ""
    if any(s.startswith(p) for p in _INTERNAL_ID_PREFIXES) or s.startswith("intel/"):
        return "internal data series/event reference (id withheld in Public view)"
    return source


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
