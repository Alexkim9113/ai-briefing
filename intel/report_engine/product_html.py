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
:root{--ink:#1a1a1a;--sub:#5a5a5a;--line:#e3e6f0;--bg:#ffffff;--accent-red:#b3261e;
--accent-amber:#8a5a00;--accent-violet:#3552c9;--good:#1e5c3a}
html{overflow-x:hidden}
*{box-sizing:border-box}
body{font-family:'Pretendard Variable','Pretendard',-apple-system,BlinkMacSystemFont,'Malgun Gothic',sans-serif;
color:var(--ink);background:var(--bg);max-width:760px;margin:0 auto;padding:32px 20px;
line-height:1.65;font-size:16px;overflow-wrap:break-word}
.mono,.meta,.chart-row td:nth-child(n+2){font-family:'Space Grotesk','Pretendard',monospace;
overflow-wrap:anywhere;word-break:break-word}
h1{font-family:'Noto Serif KR','Pretendard Variable',serif;letter-spacing:-.02em;font-weight:700;
font-size:1.6em;margin-bottom:4px;overflow-wrap:break-word}
.chart-table-wrap{overflow-x:auto}
@media (max-width: 480px){
  body{padding:20px 14px;font-size:15px}
  h1{font-size:1.3em}
}
h2{font-size:1.15em;border-top:1px solid var(--line);padding-top:18px;margin-top:28px}
.meta{color:var(--sub);font-size:0.85em;margin-bottom:24px}
.badge{display:inline-block;border:1px solid var(--line);border-radius:99px;padding:1px 10px;
font-size:0.75em;letter-spacing:.03em;margin-left:6px;max-width:100%;overflow-wrap:break-word;
word-break:break-word;white-space:normal}
.badge-ready,.badge-supported{border-color:var(--good);color:var(--good)}
.badge-conditionally_ready,.badge-partially_supported{border-color:var(--accent-amber);color:var(--accent-amber)}
.badge-insufficient_evidence,.badge-contested{border-color:var(--accent-violet);color:var(--accent-violet)}
.badge-blocked,.badge-rejected{border-color:var(--accent-red);color:var(--accent-red)}
.exec-card{border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:18px 0 28px}
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


# Priority 2 (O-2C, Te section 6-7): Public-facing readers should see plain-language status, not
# internal enum codes. Korean primary label, English code kept only as a small secondary tag so
# Operator/traceability is not lost. This is presentation-only -- the underlying status value
# (SUPPORTED/WEAKENED/etc, already computed by determine_canonical_status()) is never altered.
_STATUS_KO = {
    "PARTIALLY_SUPPORTED": "부분적으로 뒷받침됨",
    "WEAKENED": "반대 근거로 인해 약화됨",
    "CONTESTED": "상충하는 증거가 존재함",
    "INSUFFICIENT_EVIDENCE": "판단하기에 근거가 부족함",
}


def _badge(value, view="OPERATOR"):
    slug = str(value).lower()
    label = _esc(value)
    if view == "PUBLIC":
        ko = _STATUS_KO.get(str(value))
        if ko:
            label = f'{_esc(ko)} <span class="mono">({_esc(value)})</span>'
    return f'<span class="badge badge-{_esc(slug)}">{label}</span>'


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


def render_executive_card(card, view="OPERATOR"):
    # O-1F: these free-text narrative fields (current_state/key_signal/major_uncertainty/
    # what_to_watch) can themselves embed internal ids/repo file paths (same family as the
    # content_block narrative fields below) -- stripped the same way, meaning preserved.
    current_state = _strip_internal_ids(_narrative_text(card["current_state"]), view)
    key_signal = _strip_internal_ids(_narrative_text(card["key_signal"]), view)
    major_uncertainty = _strip_internal_ids(_narrative_text(card["major_uncertainty"]), view)
    what_to_watch = [_strip_internal_ids(_narrative_text(w), view) for w in card["what_to_watch"]]
    return (
        '<section aria-label="Executive Intelligence" class="exec-card">'
        f'<dl><dt>Current State</dt><dd>{_esc(current_state)}</dd>'
        f'<dt>Key Signal</dt><dd>{_esc(key_signal)} {_badge(card["key_signal_status"], view)}</dd>'
        f'<dt>Evidence Status</dt><dd>{_badge(card["evidence_status"], view)}</dd>'
        f'<dt>Major Uncertainty</dt><dd>{_esc(major_uncertainty)}</dd>'
        f'<dt>What To Watch</dt><dd><ul>{"".join(f"<li>{_esc(w)}</li>" for w in what_to_watch)}</ul></dd>'
        '</dl></section>'
    )


def _render_chart(chart, view="OPERATOR"):
    rows = (
        f"<tr><td>Indicator</td><td>{_esc(chart['indicator'])}</td></tr>"
        f"<tr><td>Geography</td><td>{_esc(chart['geography'])}</td></tr>"
        f"<tr><td>Period</td><td>{_esc(chart['period'])}</td></tr>"
        f"<tr><td>Source</td><td>{_esc(chart['source'])}</td></tr>"
        f"<tr><td>Trend</td><td>{_badge(chart['trend_status'], view)}</td></tr>"
    )
    caption = (f"Statistical series: {_esc(chart['indicator'])} "
               f"({_esc(chart['geography'])}, {_esc(chart['period'])}) -- "
               f"chart type {_esc(chart['visualization_type'])}, no forecast line, "
               f"no AI-attribution overlay.")
    return (f'<div class="chart-table-wrap"><table class="chart-table" role="table" aria-label="{caption}">'
            f'<caption class="axis-note">{caption}</caption>{rows}</table></div>'
            f'<p class="axis-note">{_esc(chart["axis_note"])}</p>')


# O-1G: ALTERNATIVE_EXPLANATIONS content blocks are bare internal enum codes in canonical data
# (e.g. "GENERAL_CLOUD_COMPUTING_GROWTH") with no human-readable description anywhere in the
# object -- found during the first-time-reader audit as a readability problem (a first-time
# reader cannot tell what these codes mean). This is a presentation-only label map: it only
# changes how the existing code is displayed (the code itself is kept, in parentheses, for
# traceability back to canonical data), never the underlying list or its meaning.
_ALT_EXPLANATION_LABELS = {
    "GENERAL_CLOUD_COMPUTING_GROWTH": "General cloud-computing growth (not AI-specific)",
    "MANUFACTURING_RESHORING": "Manufacturing/industrial reshoring driving power demand",
    "EV_ELECTRIFICATION": "EV and broader electrification of the grid",
    "WEATHER_PEAK_LOAD": "Weather-driven peak-load demand spikes",
    "POPULATION_GROWTH": "Population growth",
    "DC_GROWTH_WITHOUT_POWER_PROBLEMS_REGIONS": "Regions with data-center growth but no power problems",
    "CLIMATE_POLICY_DECARBONIZATION_LOAD_SHIFT": "Climate-policy/decarbonization load shift",
    "CRYPTO_MINING_LOAD": "Cryptocurrency-mining electricity load",
}


def _humanize_alt_explanation(code):
    label = _ALT_EXPLANATION_LABELS.get(code)
    if label:
        return f"{label} ({code})"
    return code.replace("_", " ").title() + f" ({code})"


def _render_block(block, section_type, view="OPERATOR", topic=None):
    if isinstance(block, str):
        # O-1F: bare-string content_blocks (e.g. SOURCE_PROVENANCE's source_ids) can themselves be
        # internal repo file paths (e.g. "intel/hypothesis/hypotheses.json#...") rather than a real
        # URL -- strip the same way structural fields are stripped elsewhere on this page.
        if section_type == "ALTERNATIVE_EXPLANATIONS":
            return f"<li>{_esc(_humanize_alt_explanation(block))}</li>"
        text = _mark_citations(_strip_internal_ids(block, view), topic)
        return f"<li>{_esc(text)}</li>"
    if not isinstance(block, dict):
        return f"<li>{_esc(block)}</li>"
    if "text" in block:
        status = block.get("claim_status")
        extra = f" {_badge(status, view)}" if status else ""
        text = _mark_citations(_strip_internal_ids(str(block["text"]), view), topic)
        return f"<li>{_esc(text)}{extra}</li>"
    if "indicator" in block:
        return f"<li>{_render_chart(pm.build_statistics_chart_spec(block), view)}</li>"
    if "title" in block:
        return (f"<li>{_esc(block.get('title'))} "
                f"({_esc(block.get('identity_type'))}: {_esc(block.get('identity_value'))})</li>")
    if "policy" in block and "status" in block:
        # POLICY_CONTEXT content blocks ({'policy':..., 'status':..., 'detail':...}).
        policy = _esc(block.get("policy"))
        detail = _esc(block.get("detail", ""))
        return (f"<li><strong>{policy}</strong> {_badge(block['status'], view)}"
                f"{': ' + detail if detail else ''}</li>")
    if "direction" in block and "status" in block:
        # COUNTEREVIDENCE / ALTERNATIVE_EXPLANATIONS content blocks
        # ({'direction':..., 'status':..., 'source' or 'note':...}).
        direction = _esc(block.get("direction"))
        extra = _strip_internal_ids(str(block.get("source") or block.get("note") or ""), view)
        return (f"<li>{direction} {_badge(block['status'], view)}"
                f"{': ' + _esc(extra) if extra else ''}</li>")
    if "cause" in block and "detail" in block:
        # UNCERTAINTIES content blocks ({'cause': ..., 'detail': ...}) -- same dict-repr-fallback
        # bug family as the other structural fields here (O-1G); render as a readable sentence.
        detail = _strip_internal_ids(str(block.get("detail", "")), view)
        return f"<li>{_esc(detail)} ({_esc(block['cause'])})</li>"
    if "node_type" in block:
        # EVIDENCE_MAP entries carry internal graph node references ({'node_type': ..., 'id': ...}).
        # Priority 3 (O-2C, Te section 8): for a CLAIM node we have a real, honest chain available
        # (claim text + the source actually cited for it, via source_registry's existing
        # derivation) -- render 주장→근거→출처→역할 instead of a bare placeholder. For node types
        # with no such lookup (STATISTIC/EVIDENCE_RELATION/INTELLIGENCE_OBJECT -- internal graph
        # bookkeeping ids with no equivalent human-readable record), keep the neutral withheld
        # label rather than inventing one (Public/Operator boundary, O-1D/O-1E precedent).
        node_type = block.get("node_type")
        if node_type == "CLAIM":
            chain = _evidence_map_claim_chain(block.get("id"))
            if chain:
                return f"<li>{chain}</li>"
        label = str(node_type or "").replace("_", " ").title() or "Evidence item"
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
        scope = _strip_internal_ids(str(block.get("scope", "")), view)
        basis = _strip_internal_ids(str(block.get("basis", "")), view)
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
            reason = _strip_internal_ids(str(block.get("reason", "")), view)
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


# Priority 2 (O-2C, Te section 6-7): dev-phase/internal-process annotations that were written
# straight into canonical narrative text during earlier build rounds (e.g. "[O-1C round-4
# update]", "[O-2 round 4 update]"). These are pure process noise for a reader -- they name an
# internal build phase, not a fact about the subject matter -- so they are removed here, at the
# presentation layer only; the canonical Report/IO JSON text is never rewritten. The sentence
# that follows the tag already stands on its own (it is itself a complete statement), so removing
# the bracket and the single trailing space leaves the surrounding meaning intact.
_DEV_PHASE_TAG_RE = _re.compile(r"\[O-\d[A-Za-z0-9]*(?:\s+round[-\s]?\d+)?\s+update\]\s*")
# Same family, shorter form actually found in canonical text ("[v3 update]", "[v4 update]").
_DEV_PHASE_TAG_RE_SHORT = _re.compile(r"\[v\d+\s+update\]\s*")
# Bare, unbracketed internal round/phase references used as prose subjects, e.g.
# "O-1B added a deterministic Evidence Evaluation Contract...". Same reasoning as
# _DEV_PHASE_TAG_RE: this names an internal build phase, not a fact about the subject matter.
_BARE_ROUND_REF_RE = _re.compile(r"\bO-\d[A-Za-z0-9]*(?:\s+round(?:[-\s]?\d+)?)?\b")


def _clean_dev_phase_language(text):
    """Public-view-only: strips internal build-phase/round annotations from narrative text. Never
    touches canonical JSON -- this only changes what is rendered."""
    text = _DEV_PHASE_TAG_RE.sub("", text)
    text = _DEV_PHASE_TAG_RE_SHORT.sub("", text)
    return text


# Priority 1 (O-2D, Te sections 3-6): Editorial Translation Layer. These are internal engineering
# terms -- pipeline/implementation vocabulary for how a judgment was computed or re-checked --
# that were written straight into canonical narrative text (CURRENT_STATE/UNCERTAINTIES) during
# earlier build rounds. This maps each one to a plain-language equivalent that preserves the exact
# same meaning (what was checked, what the result was, what remains uncertain) without naming the
# internal mechanism by its engineering name. It is intentionally NOT a rewrite of the surrounding
# sentence -- only these phrases are substituted -- so no judgment, uncertainty, attribution limit,
# or evidence-gap content is added, removed, or reworded beyond the phrase itself. Longer phrases
# are listed first so a specific phrase is matched before a shorter one it contains.
_EDITORIAL_TRANSLATIONS = [
    # O-3: structural enum markers embedded in canonical narrative text (e.g.
    # "AI_ATTRIBUTION=PARTIAL", bare "FORECAST"/"OBSERVED" labels) translated into natural Korean
    # clauses instead of a bare inline enum swap -- PUBLIC view only, same substitution-only
    # contract as the rest of this list (meaning preserved, nothing added/removed beyond the
    # phrase itself). Longer/more specific phrases listed first.
    ("AI_ATTRIBUTION=PARTIAL", "(AI의 영향이 일부 확인되지만 다른 요인도 함께 작용함)"),
    ("AI_ATTRIBUTION=INDIRECT", "(AI의 영향이 간접적으로만 추정되며 직접 인과관계는 확인되지 않음)"),
    ("AI_ATTRIBUTION=DIRECT", "(AI의 직접적인 영향으로 확인됨)"),
    ("AI_ATTRIBUTION=NONE", "(AI의 영향으로 확인되지 않음)"),
    ("AI_ATTRIBUTION=UNKNOWN", "(AI 귀속 여부가 아직 확인되지 않음)"),
    ("Evidence Evaluation Contract", "근거 평가 기준"),
    ("canonical_status_diagnostics field", "현재 판단의 근거 정보"),
    ("canonical_status_diagnostics", "현재 판단의 근거"),
    ("guard_trail", "검증 과정"),
    ("unresolved evidence reference", "출처를 완전히 확인하지 못한 초기 근거"),
    ("unresolved evidence", "충분히 확인되지 않은 근거"),
    ("resolved/unresolved evidence", "확인된/미확인된 근거"),
    ("4 sufficiency guards", "4가지 근거 충분성 점검"),
    ("sufficiency guards", "근거 충분성 점검"),
    ("sufficiency guard", "근거 충분성 점검"),
    ("UNKNOWN-tier guard fires", "출처 신뢰등급 미확인 점검이 작동함"),
    ("UNKNOWN-source-tier guard", "출처 신뢰등급 미확인 점검"),
    ("UNKNOWN-tier guard", "출처 신뢰등급 미확인 점검"),
    ("generalization guard", "일반화 방지 점검"),
    ("source-tier not yet classified", "출처 신뢰등급이 아직 분류되지 않음"),
    ("source-tier", "출처 신뢰등급"),
    ("source tier", "출처 신뢰등급"),
    ("canonical write path", "공식 판단 갱신 절차"),
    ("canonical Claims", "공식 확인된 주장"),
    ("canonical claim", "공식 확인된 주장"),
    ("canonical status", "공식 판단"),
    ("canonical stored statuses", "공식 기록된 판단"),
    ("write path", "판단 갱신 절차"),
    ("SEARCH_NOT_RUN", "아직 조사하지 않은 방향"),
]


def _apply_editorial_translations(text):
    """Public-view-only. Substitutes internal engineering vocabulary with a plain-language
    equivalent (see _EDITORIAL_TRANSLATIONS above), and removes bare build-round references used
    as prose subjects (e.g. "O-1B added..."). Operator view never calls this -- it keeps the
    original technical text, same as before this round."""
    for phrase, replacement in _EDITORIAL_TRANSLATIONS:
        text = text.replace(phrase, replacement)
    text = _BARE_ROUND_REF_RE.sub("This round", text)
    return text


def _strip_internal_ids(text, view="OPERATOR"):
    """Replaces any bare internal id token embedded inside an otherwise human-readable
    structural-field string with a neutral placeholder, without altering the surrounding
    sentence/meaning. Also strips dev-phase/process annotations. The additional Editorial
    Translation Layer (jargon -> plain language) applies ONLY when view=="PUBLIC" -- Operator
    keeps the original technical text."""
    text = _clean_dev_phase_language(text)
    if view == "PUBLIC":
        text = _apply_editorial_translations(text)
    text = _INTERNAL_ID_RE.sub("[internal id withheld in Public view]", text)
    text = _INTERNAL_PATH_RE.sub("[internal reference withheld in Public view]", text)
    return text


# Priority 3 (O-2C, Te section 8): Evidence Map real chain for CLAIM nodes. Reuses the same
# claims.json + source_registry curated metadata already used by the mandatory Sources section
# (source_registry.py) -- no new data, no invented facts, read-only lookups.
_claims_cache = None


def _claim_by_id(claim_id):
    global _claims_cache
    if _claims_cache is None:
        import source_registry as _sr
        _claims_cache = _sr._load_claims()
    return _claims_cache.get(claim_id)


def _evidence_map_claim_chain(claim_id):
    import source_registry as _sr
    claim = _claim_by_id(claim_id)
    if not claim:
        return None
    claim_text = _strip_internal_ids(str(claim.get("claim_text", "")))
    summary = (claim_text[:160] + "...") if len(claim_text) > 160 else claim_text
    meta = _sr._SOURCE_META.get(claim_id, {})
    institution = meta.get("institution") or "출처 미상 (institution not recorded)"
    obs = meta.get("observation_or_forecast", "")
    if "FORECAST" in obs.upper():
        role = "전망(예측) 근거"
    elif "OBSERVATION" in obs.upper():
        role = "관측 근거"
    else:
        role = "근거 자료"
    return (f"<strong>주장</strong>: {_esc(summary)} "
            f"&mdash; <strong>출처</strong>: {_esc(institution)} "
            f"&mdash; <strong>역할</strong>: {_esc(role)}")


def _public_source_label(source):
    """Public-view-only: a 'source' / 'source_id' value that is itself an internal id (not a
    real document URL/path) is replaced with a neutral label. Real URLs/paths pass through
    unchanged -- this never invents or alters any fact, it only withholds an internal id."""
    s = str(source) if source is not None else ""
    if any(s.startswith(p) for p in _INTERNAL_ID_PREFIXES) or s.startswith("intel/"):
        return "internal data series/event reference (id withheld in Public view)"
    return source


# Priority 6 (O-2C): no canonical mapping exists anywhere (confirmed again this round, same as
# the prior round's finding) from a STATISTIC (series_)/EVIDENCE_RELATION (rel_)/
# INTELLIGENCE_OBJECT (intel_) Evidence Map node id to any human-readable record -- only CLAIM
# nodes have a real, derivable chain (via _evidence_map_claim_chain, reusing source_registry).
# Previously every non-CLAIM node repeated its own "reference (internal id withheld in Public
# view)" <li>, which for a typical report means the same honest-but-empty sentence 8-12+ times in
# a row. This renders each CLAIM node's real chain individually (unchanged), then collapses every
# non-CLAIM node into ONE consolidated, honest sentence per section instead of one per node --
# same meaning (no connection info is publicly available for these node types), stated once.
def _render_evidence_map_body(blocks, view, topic):
    claim_items = []
    withheld_counts = {}
    for b in blocks:
        if isinstance(b, dict) and b.get("node_type") == "CLAIM":
            claim_items.append(_render_block(b, "EVIDENCE_MAP", view, topic))
        elif isinstance(b, dict) and "node_type" in b:
            label = str(b.get("node_type") or "").replace("_", " ").title() or "Evidence item"
            withheld_counts[label] = withheld_counts.get(label, 0) + 1
        else:
            claim_items.append(_render_block(b, "EVIDENCE_MAP", view, topic))
    html_parts = [f"<ul>{''.join(claim_items)}</ul>"] if claim_items else []
    if withheld_counts:
        breakdown = ", ".join(f"{label} x{n}" for label, n in withheld_counts.items())
        html_parts.append(
            "<p class='axis-note'>현재 공개 가능한 연결 정보가 없습니다 "
            f"({_esc(breakdown)}).</p>"
        )
    return "".join(html_parts) if html_parts else "<p class='axis-note'>현재 공개 가능한 연결 정보가 없습니다.</p>"


def render_section(entry, view="OPERATOR", topic=None):
    section = entry["section"]
    hidden_cls = " hidden" if entry["visibility"] == "HIDDEN" else ""
    note = (f"<p class='search-note'>{_esc(section['search_outcome_note'])}</p>"
            if "search_outcome_note" in section else "")
    if section["status"] == "INSUFFICIENT_EVIDENCE" and not section.get("content_blocks"):
        body = "<p class='axis-note'>Insufficient evidence in the current search scope.</p>"
    elif entry["section_type"] == "EVIDENCE_MAP":
        body = _render_evidence_map_body(section.get("content_blocks", []), view, topic)
    else:
        body = f"<ul>{''.join(_render_block(b, entry['section_type'], view, topic) for b in section.get('content_blocks', []))}</ul>"
    return (
        f'<section class="report-section{hidden_cls}" id="{_esc(entry["section_type"].lower())}" '
        f'aria-labelledby="{_esc(entry["section_type"].lower())}-h">'
        f'<h2 id="{_esc(entry["section_type"].lower())}-h">{_esc(entry["display_title"])} '
        f'{_badge(section["status"], view)}</h2>{note}{body}</section>'
    )


# Priority 5 (O-2C, Te section on inline citations): a small, hand-curated map of (exact
# substring already present in a report's own canonical text) -> (the real claim_id that
# genuinely backs that specific sentence, per claims.json / source_registry._SOURCE_META -- the
# same registry already used for the mandatory Sources section and the Evidence Map claim chain).
# This is a templating addition only -- it never invents a citation, never attaches a source to a
# sentence it doesn't actually support, and matches on text that already exists verbatim in the
# canonical Report JSON (CURRENT_STATE's own numbered-facts narrative). A substring not found in
# a given render is simply not cited (never a silent guess).
_INLINE_CITATIONS = {
    "AI_ENERGY_INFRA": [
        ("~415 TWh in 2024", "claim_afe7cc7b19317ee0"),
        # claim_1d9458f4e7e2cf69 (the FORECAST-labeled claim) and claim_afe7cc7b19317ee0 (the
        # OBSERVATION-labeled claim) both cite the exact same IEA "Energy and AI" page (per
        # source_registry._SOURCE_META's own verification notes, that single page states both the
        # 415 TWh 2024 observation and the 945/1200 TWh 2030/2035 projections) -- and
        # build_sources_for_report() dedupes by URL, so only one of the two claim_ids survives
        # into this report's real_sources. Cite the one that is actually present there, rather
        # than a claim_id that would silently drop (never a fabricated link).
        ("~945 TWh by 2030", "claim_afe7cc7b19317ee0"),
        ("a Jevons-paradox dynamic in general cloud computing", "claim_d170f52f567053e9"),
        ("~130 GW stuck in PJM's interconnection queue with ~$3.5B estimated forgone savings",
         "claim_5787125ab5f0110b"),
    ],
    "AI_LABOR": [
        ("OECD AI Exposure Measure methodology", "claim_b9370aa7d219d791"),
        ("US BLS JOLTS Aug 2026 aggregate labor-flow data", "claim_4731da53eae6b843"),
        ("NBER w31161 field experiment: generative-AI assistant raised customer-support "
         "productivity 14% on average", "claim_fe878b52922b46a4"),
        ("Stanford SIEPR 'Canaries in the Coal Mine': 13% relative employment decline for "
         "early-career (22-25) US workers", "claim_8fd5da8f27c9fc2b"),
        ("ETLA/Finland peer-reviewed population-level study found NO statistically significant "
         "wage/employment divergence", "claim_8e305d0c30d23514"),
        ("Fed FEDS Note: US firm/worker AI-adoption rates", "claim_0da20db21fe1463a"),
        ("KDI Korea macro FORECAST (not observed): +3.5% TFP over 10 years", "claim_30fdf98bc1a9c818"),
    ],
}

_CITE_MARKER_RE = _re.compile(r"@@CITE:(claim_[a-f0-9]+)@@")


def _mark_citations(text, topic):
    """Inserts a plain-ASCII marker token (no HTML-special characters, so it survives _esc()
    unchanged) right after each known, real-source-backed substring. Resolved to an actual
    citation anchor by _resolve_citations() once the full page's real Sources list (and its
    anchor numbering) is known."""
    if not topic:
        return text
    for substring, claim_id in _INLINE_CITATIONS.get(topic, []):
        if substring in text:
            text = text.replace(substring, f"{substring}@@CITE:{claim_id}@@", 1)
    return text


def _resolve_citations(html_doc, real_sources):
    """Replaces every @@CITE:claim_id@@ marker left by _mark_citations() with a real, clickable
    '(Institution, Year)' citation linked to that exact source's existing #source-N anchor in the
    rendered Sources section (33G). A marker whose claim_id is not actually present in this
    report's own real_sources (i.e. not really cited by this report) is stripped rather than
    linked -- never a fabricated or misattributed citation."""
    by_claim = {}
    for i, s in enumerate(real_sources or [], 1):
        if s.get("claim_id"):
            by_claim[s["claim_id"]] = (i, s.get("institution"), s.get("year"))

    def _sub(m):
        claim_id = m.group(1)
        entry = by_claim.get(claim_id)
        if not entry:
            return ""
        idx, institution, year = entry
        year_match = _re.search(r"\d{4}", str(year) or "")
        year_label = year_match.group(0) if year_match else _esc(year)
        return (f' <sup class="cite"><a href="#source-{idx}">'
                f'{_esc(institution)}, {year_label}</a></sup>')

    return _CITE_MARKER_RE.sub(_sub, html_doc)


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


# Section 33A-33I -- "출처 / Sources" section, reader-facing. Built from source_registry's
# read-only derivation (real report SOURCE_PROVENANCE.source_ids x claims.json), never from
# internal Claim/Evidence/Hypothesis ids (33C). Public/Print/PDF all go through this one function
# (33G); it never shows a bare claim_/intel_/hyp_/evt_ id, only a human-readable institution,
# title, year, document type, tier, and a real clickable <a href> to the original URL.
def render_real_sources(sources, report_topic=None, show_internal_ids=False):
    if not sources:
        return (
            '<section aria-label="시출 / Sources"><h2>시출 / Sources</h2>'
            '<p class="axis-note">No independently-cited sources were recorded for this report '
            'version (SOURCE_TRACEABILITY: NOT_READY).</p></section>'
        )
    items = []
    for i, s in enumerate(sources, 1):
        url = s.get("url") or ""
        institution = _esc(s.get("institution"))
        title = _esc(s.get("title"))
        year = _esc(s.get("year"))
        doc_type = _esc(s.get("doc_type"))
        tier = _esc(s.get("tier"))
        access = _esc(s.get("access_status"))
        obs = _esc(s.get("observation_or_forecast"))
        # Real clickable anchor -- never a raw internal id anywhere near it (33C/33H check 8).
        link = (f'<a href="{_esc(url)}" rel="noopener noreferrer" target="_blank">{_esc(url)}</a>'
                if url else "")
        # show_internal_ids is Operator-view-only (33F): the chain claim -> evidence -> real
        # source is shown explicitly there, retaining full provenance depth; Public/Print/PDF
        # (show_internal_ids=False, the default) never render a bare claim_/evidence_ id (33C/33H
        # check 8) -- they get only the plain-language 주장->근거->실제출처 relationship.
        provenance_line = ""
        if show_internal_ids and s.get("claim_id"):
            provenance_line = (f'<br><span class="mono axis-note">claim_id={_esc(s["claim_id"])} '
                                f'claim_type={_esc(s.get("claim_type"))} '
                                f'evidence_independence={_esc(s.get("evidence_independence"))} '
                                f'verification={_esc(s.get("verification"))}</span>')
        items.append(
            f'<li id="source-{i}"><span class="cite">[{i}]</span> '
            f'<strong>{institution}</strong>. <em>{title}</em>. {year}. {doc_type}. '
            f'<span class="badge">{tier}</span> <span class="badge">{access}</span> '
            f'<span class="axis-note">{obs}</span><br>{link}{provenance_line}</li>'
        )
    heading_note = (
        '<p class="axis-note">Each source below was actually used as Evidence for a claim in this '
        'report (주장→근거→실제출처: claim → evidence → '
        'real source). Access status: ORIGINAL_SOURCE / OFFICIAL_DATA_PAGE / DOI / WORKING_PAPER / '
        'SECONDARY_SOURCE / ACCESS_BLOCKED.</p>'
    )
    return (
        '<section aria-label="시출 / Sources" id="sources">'
        '<h2 id="sources-h">시출 / Sources</h2>'
        f'{heading_note}<ol class="sources">{"".join(items)}</ol></section>'
    )


def render_product_html(presentation, source_cards=None, view="PUBLIC", real_sources=None):
    topic = presentation.get("topic")
    sections_html = "".join(render_section(e, view, topic) for e in presentation["sections"])
    sources_html = render_sources(source_cards) if source_cards else ""
    # Section 33A/33G -- the reader-facing "출처 / Sources" section, independent of the older
    # document-registry render_sources() above (kept for NON_DOCUMENT_PROVENANCE internal cards).
    # real_sources is None (not just empty) is treated as "caller did not pass it" and renders
    # nothing extra, so this never breaks a caller that hasn't been updated yet.
    real_sources_html = (render_real_sources(real_sources, show_internal_ids=(view != "PUBLIC"))
                         if real_sources is not None else "")
    doc = (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{_esc(presentation['display_title'])}</title><style>{CSS}</style></head><body>"
        f"<main aria-label='Intelligence Report'>"
        f"<h1>{_esc(presentation['display_title'])} {_badge(presentation['readiness'])}</h1>"
        f"<p class='meta'>report_id={_esc(presentation['report_id'])} "
        f"version={_esc(presentation['version'])} view={_esc(view)}</p>"
        f"{render_executive_card(presentation['executive_card'], view)}"
        f"{sections_html}"
        f"{sources_html}"
        f"{real_sources_html}"
        f"<footer>METAXIS Intelligence Observatory -- structured evidence, not editorial conclusions.</footer>"
        f"</main></body></html>"
    )
    # Priority 5 (O-2C): resolve any @@CITE:claim_id@@ markers left by _mark_citations() into real
    # clickable (Institution, Year) citations anchored to this report's own Sources section, now
    # that real_sources (and its #source-N anchor numbering) is known.
    return _resolve_citations(doc, real_sources)
