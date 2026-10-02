# N-5 Section 10-19, 63-65 -- Operator Workspace minimal UI. A static, read-only HTML build over
# operator_api.py's backend -- never a new backend, never a dashboard. Generated at build time
# only (never per-request), following N-4's own typography/visual contract (Pretendard body,
# Space Grotesk for numbers/ids) and its "a document to read" anti-dashboard principle: no
# gradients, no decorative icons, minimal cards, real data or an honest NOT_AVAILABLE/
# NOT_INSTRUMENTED label -- never a fabricated metric to fill a panel.
import html as _html
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import operator_api as op  # noqa: E402
import daily_discovery as dd  # noqa: E402
sys.path.insert(0, str(HERE.parent / "report_engine"))
import atomic_publish as apub  # noqa: E402
import report_engine as re_  # noqa: E402
# Section 33F -- Operator reuses source_registry's read-only derivation (the SAME underlying
# logic as Public/Print/PDF, per 33G), never product_html.py: Operator must keep full internal
# provenance (claim_id, evidence_independence, claim_type) that Public deliberately withholds.
import source_registry as sreg  # noqa: E402
sys.path.insert(0, str(HERE.parent / "daily_taxonomy"))
sys.path.insert(0, str(HERE.parent / "intelligence_candidate"))
sys.path.insert(0, str(HERE.parent / "ai_relevance_gate"))
import taxonomy as _taxonomy  # noqa: E402
import candidate_engine as _candidates  # noqa: E402

CSS = """
:root{--ink:#1a1a1a;--sub:#5a5a5a;--line:#e3e6f0;--bg:#ffffff;--warn:#8a5a00;--bad:#b3261e;--ok:#1e5c3a;--accent:#3552c9;--soft:#eef1fb}
html{overflow-x:hidden}
*{box-sizing:border-box}
body{font-family:'Pretendard Variable','Pretendard',-apple-system,sans-serif;color:var(--ink);background:var(--bg);
margin:0;padding:0;line-height:1.6;font-size:15px;overflow-wrap:break-word}
.mono{font-family:'Space Grotesk','Pretendard',monospace;overflow-wrap:anywhere;word-break:break-word}
header{border-bottom:1px solid var(--line);padding:16px 24px}
header h1{font-family:'Noto Serif KR','Pretendard Variable',serif;letter-spacing:-.02em;font-size:1.1em;margin:0;overflow-wrap:break-word}
nav{display:flex;flex-wrap:wrap;gap:4px;padding:10px 24px;border-bottom:1px solid var(--line);font-size:0.85em}
nav a{color:var(--sub);text-decoration:none;padding:4px 10px;border-radius:99px}
nav a:hover,nav a.active{background:var(--soft);color:var(--accent)}
main{max-width:980px;margin:0 auto;padding:24px}
.table-wrap{overflow-x:auto}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:0.92em;min-width:420px}
td,th{border:1px solid var(--line);padding:6px 10px;text-align:left;vertical-align:top}
th{background:var(--soft);font-weight:600}
.status{font-size:0.8em;padding:1px 8px;border-radius:99px;border:1px solid var(--line)}
.status-healthy,.status-ready{border-color:var(--ok);color:var(--ok)}
.status-blocked,.status-not_found,.status-pdf_failed{border-color:var(--bad);color:var(--bad)}
.status-degraded,.status-conditionally_ready,.status-auth_required{border-color:var(--warn);color:var(--warn)}
.status-not_instrumented,.status-unknown,.status-not_available{border-color:var(--sub);color:var(--sub)}
.empty{color:var(--sub);font-style:italic}
.kpi-row{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0}
.kpi{border:1px solid var(--line);border-radius:12px;padding:10px 14px;box-sizing:border-box;
flex:0 0 calc(33.333% - 7px);max-width:calc(33.333% - 7px);min-width:0;overflow-wrap:break-word}
.kpi .n{font-family:'Space Grotesk',monospace;font-size:1.4em}
.kpi .l{color:var(--sub);font-size:0.78em;text-transform:uppercase;overflow-wrap:break-word}
a:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.status{overflow-wrap:break-word;display:inline-block;max-width:100%}
@media (max-width: 480px){
  main{padding:14px}
  header{padding:12px 14px}
  nav{padding:8px 14px}
  .kpi-row{grid-template-columns:repeat(2, 1fr)}
}
"""

NAV_ITEMS = ("overview", "daily_discovery", "emerging_issues", "research_queue",
             "intelligence_index", "reports", "gaps", "rights", "sources", "source_health")

# Korean-first labels (Te's O-2C mapping). Presentation text only -- never changes route slugs,
# internal IDs, or data. English kept as a small secondary label alongside the Korean primary.
KO_LABELS = {
    "overview": "운영 현황",
    "daily_discovery": "데일리 디스커버리",
    "emerging_issues": "이머징 이슈",
    "research_queue": "리서치",
    "intelligence_index": "인텔리전스 포트폴리오",
    "reports": "보고서",
    "gaps": "미해결 쟁점",
    "rights": "권리·사용 범위",
    "sources": "출처",
    "source_health": "출처 상태",
    "counterevidence": "반증 자료",
    "evidence": "근거",
}


def _ko(slug, fallback=None):
    return KO_LABELS.get(slug, fallback or slug.replace("_", " ").title())


def _nav_label(slug):
    return f'{_esc(_ko(slug))} <span style="opacity:.6;font-size:.85em">({_esc(slug.upper())})</span>'


def _esc(x):
    return _html.escape(str(x)) if x is not None else ""


def _status(value):
    slug = str(value).lower()
    return f'<span class="status status-{_esc(slug)}">{_esc(value)}</span>'


# Section 11/O-2E -- allow only http/https source links anywhere a dynamic URL is rendered;
# anything else (javascript:, data:, mailto:, a bare NOT_VERIFIED token, etc.) is shown as plain
# escaped text instead of an <a href>, never as a clickable link.
def _safe_link(url, label=None):
    label = _esc(label if label is not None else url)
    if isinstance(url, str) and (url.startswith("http://") or url.startswith("https://")):
        return f'<a href="{_esc(url)}" target="_blank" rel="noopener noreferrer">{label}</a>'
    return f'<span class="mono">{label}</span>'


def _priority_badge(level, reason):
    """Section 3 -- Operator-only editorial priority label. Structurally separate from evidence
    status: this never appears in the same field as Evidence Status, and never on Public."""
    return (f'<span class="status status-{_esc(level.lower())}" title="{_esc(reason)}">'
            f'{_esc(level)} 우선순위</span> <span class="empty">({_esc(reason)})</span>')


def _nav(active, depth=1):
    up = "../" * depth
    links = "".join(
        f'<a href="{up}{n}/" class="{"active" if n == active else ""}">{_nav_label(n)}</a>'
        for n in NAV_ITEMS
    )
    return f"<nav aria-label='Operator navigation'>{links}</nav>"


def _shell(title, active, body, depth=1):
    return (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>Operator -- {_esc(title)}</title><style>{CSS}</style></head><body>"
        "<header><h1>METAXIS Intelligence Workbench (Operator)</h1></header>"
        f"{_nav(active, depth)}<main aria-label='Operator workspace'>{body}</main></body></html>"
    )


PUBLIC_SAFE_BANNER = (
    '<div style="border:1px solid var(--line);background:var(--soft);padding:10px 14px;'
    'margin-bottom:16px;font-size:0.85em">'
    '<strong>METAXIS OPERATOR / PRIVATE WORKSPACE</strong><br>'
    'Since O-3A this workspace is built only into intel_private/ on this repository\'s private '
    'main branch -- it is no longer published to the public gh-pages site/metaxis.kr. It is '
    'reachable only to GitHub accounts with repository access (git clone/pull), not via a '
    'client-side password gate. A browsable, logged-in web Operator is a separate, not-yet-built '
    'Authentication Phase (O-3 section 34). See '
    '<code>intel/operator_workspace/operator_boundary_contract.json</code> for the full boundary.'
    '</div>'
)


def _portfolio_rows():
    """Reuses op.intelligence_index() + op.hypotheses_for_topic() -- no new fields invented,
    just a decision-oriented rollup of data the backend already exposes (Te's home-page ask)."""
    rows = []
    for row in op.intelligence_index():
        hyps = op.hypotheses_for_topic(row["topic"])
        has_counterev = any((h.get("contradicting_evidence") or []) for h in hyps)
        rows.append({**row, "has_counterevidence": has_counterev})
    return rows


def _portfolio_section_html():
    rows = op.portfolio_summary()
    cards = "".join(
        f'<div class="kpi" style="flex:0 0 calc(50% - 7px);max-width:calc(50% - 7px)">'
        f'<div class="l">{_esc(r["topic_ko"])} <span class="empty">({_esc(r["topic"])})</span></div>'
        f'<div>{_status(r["readiness"])} &middot; IO v{_esc(r["io_version"])} '
        f'&middot; Report v{_esc(r["latest_report_version"])} &middot; updated {_esc(r["updated"])}</div>'
        f'<div>핵심 판단(Core judgment): {_esc(r["core_judgment"])} {_status(r["core_judgment_status"])}</div>'
        f'<div>핵심 근거(Key evidence): {_esc(r["key_evidence_count"])} &middot; '
        f'핵심 반증(Key counterevidence): {_esc(r["key_counterevidence_count"])} &middot; '
        f'미해결 쟁점(Known gaps): {_esc(r["known_gap_count"])}</div>'
        f'<div>{_index_detail_link(r)}</div></div>'
        for r in rows
    )
    return f'<h2>Intelligence Portfolio / 인텔리전스 포트폴리오</h2><div class="kpi-row">{cards}</div>'


def _key_signals_section_html():
    """Section 2 -- '오늘의 핵심 신호'. Real claim-derived cards from op.today_key_signals(), or
    the honest NO_CHANGE empty state. Never a firehose, never an invented score."""
    signals = op.today_key_signals()
    if not signals:
        return (
            '<h2>오늘의 핵심 신호 / Today\'s Key Signals</h2>'
            '<p class="empty">오늘 기존 Intelligence 판단을 변경할 정도의 새로운 신호는 확인되지 않았습니다. '
            '(No new evidence wired into an existing hypothesis since each topic\'s latest published '
            'Report -- this is a normal, expected result, not a missing feature.)</p>'
        )
    cards = []
    for s in signals:
        obs_ko = op.OBSERVATION_FORECAST_KO.get(
            str(s["observation_or_forecast"]).split(" ")[0].upper(), s["observation_or_forecast"])
        role_label = "지지 근거 (SUPPORTING)" if s["role"] == "SUPPORTING" else "반증 (CONTRADICTING)"
        cards.append(
            '<div class="kpi" style="flex:0 0 100%;max-width:100%">'
            f'<div><strong>{_esc(s["claim_text"])}</strong></div>'
            f'<div>{_esc(s["topic_ko"])} <span class="empty">({_esc(s["topic"])})</span> &middot; '
            f'가설(Hypothesis) {_esc(s["hypothesis_code"])}: {_esc(s["hypothesis_statement"])}</div>'
            f'<div>역할(Role): {_esc(role_label)} &middot; 왜 중요한가(Why it matters): {_esc(s["why_it_matters"])}</div>'
            f'<div>출처(Source): {_esc(s["institution"])} ({_esc(s["year"])}) &middot; {_esc(obs_ko)} '
            f'<span class="empty">({_esc(s["observation_or_forecast"])})</span></div>'
            f'<div>{_safe_link(s["url"])}</div>'
            f'<div class="mono">claim_id={_esc(s["claim_id"])}</div>'
            '</div>'
        )
    return (
        f'<h2>오늘의 핵심 신호 / Today\'s Key Signals ({len(signals)})</h2>'
        f'<div class="kpi-row">{"".join(cards)}</div>'
    )


def _daily_discovery_section_html(items):
    """O-2F (scoped) -- '오늘의 핵심 Discovery'. Reads daily_discovery.daily_discovery_items()'s
    plain dicts over the raw day's Feed (data/*.json), never claims.json. Structurally separate
    from '오늘의 핵심 신호' (today_key_signals, which is wired-into-hypothesis Claim data): every
    card here carries its own DISCOVERY_ONLY evidence_status banner so it is never mistaken for a
    Claim. Honest empty state when no item passes the deterministic filter."""
    if not items:
        return (
            '<h2>오늘의 핵심 Discovery / Today\'s Key Discovery</h2>'
            '<p class="empty">오늘 중요한 Discovery 항목이 확인되지 않았습니다.</p>'
        )
    cards = []
    for it in items:
        sources = it.get("sources") or [{"institution": it.get("source"), "url": it.get("url")}]
        sources_html = "".join(
            f'<li>{_esc(s.get("institution"))}: {_safe_link(s.get("url"))}</li>' for s in sources
        ) if len(sources) > 1 else ""
        field = it.get("field")
        country = it.get("country")
        tags = " &middot; ".join(x for x in (
            f'분야(Field): {_esc(field)}' if field else "",
            f'지역(Region): {_esc(country)}' if country else "",
        ) if x)
        cards.append(
            '<div class="kpi" style="flex:0 0 100%;max-width:100%">'
            f'<div><strong>{_esc(it["title_ko"])}</strong></div>'
            f'<div>출처(Source): {_esc(it["source"])} (Tier {_esc(it["source_tier"])}) &middot; '
            f'날짜(Date): {_esc(it["date"])}</div>'
            + (f'<div>{tags}</div>' if tags else "")
            + f'<div>왜 중요한가(Why it matters): {_esc(it["why_it_matters"])}</div>'
            f'<div>연관 Intelligence: {_esc(it["related_intelligence"])}</div>'
            f'<div>{_safe_link(it["url"])}</div>'
            + (f'<div>병합된 출처(Merged sources, {len(sources)}): <ul>{sources_html}</ul></div>'
               if sources_html else "")
            + f'<div class="empty">{_esc(it["evidence_status"])}</div>'
            '</div>'
        )
    return (
        f'<h2>오늘의 핵심 Discovery / Today\'s Key Discovery ({len(items)})</h2>'
        '<p class="empty">결정론적(non-LLM) 중요도 필터: Tier 1 출처 또는 정책/규제 키워드 일치. '
        'claims.json에 기록되지 않는 Discovery 전용 항목입니다. 같은 사건을 보도한 근접 중복 '
        '기사는 event_service.cluster_events()로 하나의 카드로 병합되며(해당 시 아래 카드의 '
        '출처 목록에 모두 표시), 보수적 병합 기준에 맞지 않으면 분리된 카드로 남습니다.</p>'
        f'<div class="kpi-row">{"".join(cards)}</div>'
    )


def _change_watch_section_html():
    """Section 4 -- Intelligence 변화 가능성 (Change Watch). Section 27 -- counterevidence is now
    its own clearly identifiable subsection/card-group (previously folded invisibly into this
    section in Round 1), reusing the SAME contradicting_evidence data -- no new engine."""
    watch = op.intelligence_change_watch()
    contested = watch["contested_hypotheses"]
    if contested:
        rows = "".join(
            f'<div class="kpi" style="flex:0 0 100%;max-width:100%">'
            f'<div><strong>{_esc(c["hypothesis_code"])}</strong> ({_esc(c["topic_ko"])}): {_esc(c["statement"])}</div>'
            f'<div>현재 상태(Current status): {_status(c["status"])} &middot; '
            f'반증 건수(Contradicting evidence): {_esc(c["contradicting_evidence_count"])}</div>'
            f'</div>'
            for c in contested
        )
        contested_block = f'<div class="kpi-row">{rows}</div>'
    else:
        contested_block = '<p class="empty">현재 반증이 연결된 가설이 없습니다 (no hypothesis currently carries contradicting_evidence).</p>'
    return (
        '<h2>Intelligence 변화 가능성 / Judgment-Change Watch</h2>'
        f'<h3 id="counterevidence">반증 자료 (Counterevidence) <span class="empty">'
        f'({len(contested)}개 가설에 연결됨)</span></h3>{contested_block}'
    )


def _emerging_issues_section_html(result):
    """Section 13-16 -- '새롭게 떠오르는 이슈'. Honest NOT_ENOUGH_HISTORY empty state when fewer
    than daily_discovery.MIN_HISTORY_DAYS real data/*.json files exist -- never a fabricated
    trend from a single day."""
    if result["status"] == dd.NOT_ENOUGH_HISTORY:
        return (
            '<h2>새롭게 떠오르는 이슈 / Emerging Issues</h2>'
            f'<p class="empty">충분한 실제 이력 데이터가 없습니다 (NOT_ENOUGH_HISTORY: '
            f'{_esc(result["days_available"])}/{_esc(result["days_required"])}일 확보됨). '
            '추세를 조작하지 않고 정직하게 비워둡니다.</p>'
        )
    issues = result["issues"]
    if not issues:
        return (
            '<h2>새롭게 떠오르는 이슈 / Emerging Issues</h2>'
            f'<p class="empty">{_esc(result["days_available"])}일 이력 확인됨, 반복 등장하는 이슈는 '
            '아직 확인되지 않았습니다.</p>'
        )
    cards = "".join(
        '<div class="kpi" style="flex:0 0 100%;max-width:100%">'
        f'<div><strong>{_esc(i["issue_name"])}</strong> &middot; {_esc(i["field"])} &middot; '
        f'{_esc(i["region"])} &middot; {_status(i["status"])}</div>'
        f'<div>관련 이벤트(Related events): {_esc(i["related_event_count"])} &middot; '
        f'독립 출처(Independent sources): {_esc(i["independent_source_count"])} &middot; '
        f'반복 일수(Recurring days): {_esc(i["recurring_days"])}</div>'
        f'<div>관련 Intelligence 토픽: {_esc(i["related_intelligence_topic"] or "없음")}</div>'
        f'<div class="empty">{_esc(i["claim_status"])}</div>'
        '</div>'
        for i in issues
    )
    return (
        f'<h2>새롭게 떠오르는 이슈 / Emerging Issues ({len(issues)}, '
        f'{_esc(result["days_available"])}일 이력 기반)</h2>'
        f'<div class="kpi-row">{cards}</div>'
    )


def _editorial_queue_section_html(buckets):
    """Section 17-18 -- '편집 검토 대기열'. Read-only categorization over already-computed
    Discovery + Change Watch data (see daily_discovery.editorial_queue -- no mutating function
    exists anywhere in this module or that one). EDITORIAL_PRIORITY and EVIDENCE_QUALITY are
    always shown as two separate labels, never merged into one score."""
    parts = []
    for bucket in dd.EDITORIAL_BUCKETS:
        rows = buckets.get(bucket) or []
        if not rows:
            continue
        items = "".join(
            f'<li>{_esc(r["label"])} -- {_esc(r["detail"])} &middot; '
            f'<span class="status">PRIORITY: {_esc(r["editorial_priority"])}</span> '
            f'<span class="status">EVIDENCE: {_esc(r["evidence_quality"])}</span></li>'
            for r in rows
        )
        parts.append(f'<h3>{_esc(bucket)} <span class="empty">({len(rows)})</span></h3><ul>{items}</ul>')
    body = "".join(parts) if parts else '<p class="empty">현재 편집 검토 대기열에 항목이 없습니다.</p>'
    return f'<h2>편집 검토 대기열 / Editorial Queue</h2>{body}'


def _gap_categories_section_html():
    """Section 6 -- categorized Known Gaps, display-layer only."""
    buckets = op.gaps_by_category()
    if not buckets:
        return '<h2>조사 필요 항목 / Gap Categories</h2><p class="empty">No known gaps recorded.</p>'
    parts = []
    for cat, rows in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
        label = op.GAP_CATEGORY_KO.get(cat, cat)
        items = "".join(
            f'<li>{_esc(g["topic"])} &middot; {_esc(g["gap_type"])}: {_esc(g["description"])}</li>'
            for g in rows
        )
        parts.append(f'<h3>{_esc(label)} <span class="empty">({_esc(cat)}, {len(rows)})</span></h3><ul>{items}</ul>')
    return '<h2>조사 필요 항목 / Gap Categories</h2>' + "".join(parts)


def render_overview():
    """Section 1 -- information hierarchy per Te's O-2E spec, reordered so Intelligence content
    always comes before system/pipeline status:
    1 Today's Key Signals, 2 Change Watch, 3 Open Issues/Gaps, 4 Portfolio, 5 latest Reports
    pointer, 6 Gap Categories, 7 (counterevidence is embedded in Change Watch/portfolio),
    8 Source Health, 9 System/Pipeline Health (last)."""
    o = op.overview()
    gaps = op.gap_inspector()
    open_gaps = [g for g in gaps if str(g.get("status", "")).upper() not in ("RESOLVED", "CLOSED")]
    gaps_section = (
        '<h2>열린 쟁점 / Evidence Gap</h2>'
        + (f'<p>{len(open_gaps)} open of {len(gaps)} recorded. See '
           f'<a href="../gaps/">{_ko("gaps")} / Gaps</a> for the full list.</p>'
           if gaps else '<p class="empty">No known gaps recorded.</p>')
    )
    reports_section = (
        f'<h2>최신 Evidence / Latest Reports</h2>'
        f'<p>See <a href="../reports/">{_ko("reports")} / Reports</a> and '
        f'<a href="../intelligence_index/">{_ko("intelligence_index")}</a> for per-topic detail.</p>'
    )
    source_health_section = (
        '<h2>Source Health</h2>'
        f'<p>Source Health (minimal contract): {_status(o["source_health"])}. '
        f'See <a href="../source_health/">{_ko("source_health")} / Source Health</a>.</p>'
    )

    live = op.live_run_status()
    live_kpis = "".join(
        f'<div class="kpi"><div class="n">{_esc(v)}</div><div class="l">{_esc(k.replace("_", " "))}</div></div>'
        for k, v in live.items() if k not in ("run_id", "head_sha", "completed_at", "environment")
    )
    kpis = "".join(
        f'<div class="kpi"><div class="n">{_esc(v)}</div><div class="l">{_esc(k.replace("_", " "))}</div></div>'
        for k, v in o.items() if k != "source_health"
    )
    system_health_section = (
        '<h2>Pipeline / System Health</h2>'
        f'<div class="kpi-row">{kpis}</div>'
        f'<h3>최근 라이브 수집 / Last Live Acquisition</h3>'
        f'<p class="mono">RUN_ID={_esc(live["run_id"])} HEAD_SHA={_esc(live["head_sha"])} '
        f'COMPLETED_AT={_esc(live["completed_at"])} ENVIRONMENT={_esc(live["environment"])}</p>'
        f'<div class="kpi-row">{live_kpis}</div>'
    )

    discovery_items = dd.daily_discovery_items(data_dir=str(op.ROOT / "data"))
    emerging = dd.emerging_issues(data_dir=str(op.ROOT / "data"))
    watch = op.intelligence_change_watch()
    editorial_buckets = dd.editorial_queue(discovery_items, watch["contested_hypotheses"])

    # Section 26 reorder: 오늘의 핵심 Discovery -> Emerging Issues -> Change Watch (incl. its own
    # Counterevidence subsection, section 27) -> Editorial Queue -> 열린 쟁점 -> Portfolio ->
    # 최신 보고서 -> (반대근거/대안설명 already live inside Change Watch's Counterevidence
    # subsection -- not duplicated as a second section) -> Source Health -> System 상태 (last).
    return _shell(f"{_ko('overview')} / Overview", "overview", (
        f'{PUBLIC_SAFE_BANNER}'
        f'{_daily_discovery_section_html(discovery_items)}'
        f'{_key_signals_section_html()}'
        f'{_emerging_issues_section_html(emerging)}'
        f'{_change_watch_section_html()}'
        f'{_editorial_queue_section_html(editorial_buckets)}'
        f'{gaps_section}'
        f'{_portfolio_section_html()}'
        f'{reports_section}'
        f'{_gap_categories_section_html()}'
        f'{source_health_section}'
        f'{system_health_section}'
    ))


def render_reports():
    rows = op.list_reports()
    body_rows = "".join(
        f'<tr><td><a href="../../intelligence/{_esc(r["report_id"])}/">{_esc(r["report_id"])}</a></td>'
        f'<td>{_esc(r["topic"])}</td><td>{_esc(r["version"])}</td>'
        f'<td>{_status(r["readiness"])}</td><td class="mono">{_esc(r["generated_at"])}</td>'
        f'<td>{_status(r["html_status"])}</td><td>{_status(r["pdf_status"])}</td></tr>'
        for r in rows
    )
    table = ('<div class="table-wrap">' + f'<table><tr><th>Report</th><th>Topic</th><th>Version</th><th>Readiness</th>'
            f'<th>Generated</th><th>HTML</th><th>PDF</th></tr>{body_rows}</table></div>')
    if not rows:
        table = '<p class="empty">No reports built yet.</p>'
    return _shell(f"{_ko('reports')} / Reports", "reports", table)


def render_gaps():
    rows = op.gap_inspector()
    if not rows:
        return _shell(f"{_ko('gaps')} / Gaps", "gaps", '<p class="empty">No known gaps recorded.</p>')
    body_rows = "".join(
        f'<tr><td class="mono">{_esc(g["gap_id"])}</td><td>{_esc(g["topic"])}</td>'
        f'<td>{_esc(g["gap_type"])}</td><td>{_status(g["status"])}</td>'
        f'<td>{_esc(g["description"])}</td><td>{_esc(g["next_possible_action"])}</td></tr>'
        for g in rows
    )
    table = ('<div class="table-wrap">' + f'<table><tr><th>Gap ID</th><th>Topic</th><th>Type</th><th>Status</th>'
            f'<th>Description</th><th>Next Possible Action</th></tr>{body_rows}</table></div>')
    return _shell(f"{_ko('gaps')} / Gaps", "gaps", f"<p>{len(rows)} known gap(s) -- none hidden.</p>{table}")


def render_rights():
    rows = op.rights_inspector()
    body_rows = "".join(
        f'<tr><td class="mono">{_esc(r["source"])[:60]}</td><td>{_status(r["rights_status"])}</td>'
        f'<td>{_status(r["access_status"])}</td><td>{_esc(r["public_allowed"])}</td>'
        f'<td>{_esc(r["fulltext_allowed"])}</td><td>{_esc(r["private_only"])}</td></tr>'
        for r in rows
    )
    table = ('<div class="table-wrap">' + f'<table><tr><th>Source</th><th>Rights</th><th>Access</th>'
            f'<th>Public Allowed</th><th>Fulltext Allowed</th><th>Private Only</th></tr>{body_rows}</table></div>')
    if not rows:
        table = '<p class="empty">No rights-tracked sources referenced by any report yet.</p>'
    return _shell(f"{_ko('rights')} / Rights", "rights", table)


def render_sources():
    rows = op.source_inspector()
    # Section 37 -- never dump 299 rows as the first thing rendered; show counts, then a capped
    # sample table (the full list is still in source_inspector()'s JSON for anyone who needs it).
    by_type = {}
    for r in rows:
        by_type[r["source_type"]] = by_type.get(r["source_type"], 0) + 1
    kpis = "".join(
        f'<div class="kpi"><div class="n">{_esc(v)}</div><div class="l">{_esc(k)}</div></div>'
        for k, v in sorted(by_type.items())
    )
    sample = rows[:25]
    body_rows = "".join(
        f'<tr><td class="mono">{_esc(r["source_id"])}</td><td>{_esc(r["name"])}</td>'
        f'<td>{_esc(r["source_type"])}</td><td>{_status(r["health_status"])}</td></tr>'
        for r in sample
    )
    table = '<div class="table-wrap">' + f'<table><tr><th>Source ID</th><th>Name</th><th>Type</th><th>Health</th></tr>{body_rows}</table></div>'
    return _shell(f"{_ko('sources')} / Sources", "sources", (
        f'<p>{len(rows)} registered sources.</p><div class="kpi-row">{kpis}</div>'
        f'<p>Showing first {len(sample)} (see index.json for the full registry).</p>{table}'
    ))


def render_source_health():
    summary = op.source_health_pilot_summary()
    live = op.source_health_live_summary()
    if not summary["pilot_run"]:
        sandbox_block = '<p class="empty">No Source Health sandbox pilot has been run yet (NOT_INSTRUMENTED).</p>'
    else:
        kpis = "".join(
            f'<div class="kpi"><div class="n">{_esc(v)}</div><div class="l">{_esc(k)}</div></div>'
            for k, v in summary["counts"].items()
        )
        body_rows = "".join(
            f'<tr><td class="mono">{_esc(s["source_id"])}</td>'
            f'<td>{_status(s.get("environment", "SANDBOX"))}</td>'
            f'<td>{_status(s.get("environment_status", "UNKNOWN"))}</td>'
            f'<td>{_status(s.get("source_status", s["status"]))}</td>'
            f'<td>{_esc(s["last_checked"])}</td>'
            f'<td>{_esc(s["known_limitation"])}</td></tr>'
            for s in summary["sources"]
        )
        table = ('<div class="table-wrap">' + f'<table><tr><th>Source</th><th>Environment</th>'
                f'<th>Environment Status</th><th>Source Status</th><th>Last Checked</th>'
                f'<th>Known Limitation</th></tr>{body_rows}</table></div>')
        sandbox_block = (
            f'<h2>Sandbox check (orchestration/local validation only)</h2>'
            f'<p>Last sandbox run: {_esc(summary["checked_at"])}</p>'
            f'<div class="kpi-row">{kpis}</div>{table}'
        )

    if not live["pilot_run"]:
        live_block = (
            '<h2>GitHub Actions live check</h2>'
            '<p class="empty">No GitHub Actions live source-health run has produced a result yet '
            '(NOT_INSTRUMENTED -- wired in .github/workflows/daily.yml job n7_live_acquisition, '
            'not yet observed from this session; see intel/phase_n7 report, Section H).</p>'
        )
    else:
        live_rows = "".join(
            f'<tr><td class="mono">{_esc(s["source_id"])}</td>'
            f'<td>{_status(s.get("source_status", s["status"]))}</td>'
            f'<td>{_esc(s["last_checked"])}</td>'
            f'<td>{_esc(s["known_limitation"])}</td></tr>'
            for s in live["sources"]
        )
        live_block = (
            '<h2>GitHub Actions live check</h2>'
            f'<p>Last live run: {_esc(live["checked_at"])} (environment: {_esc(live["environment"])})</p>'
            '<div class="table-wrap"><table><tr><th>Source</th><th>Live Status</th>'
            f'<th>Last Checked</th><th>Known Limitation</th></tr>{live_rows}</table></div>'
        )

    return _shell(f"{_ko('source_health')} / Source Health", "source_health", sandbox_block + live_block)


# O-3D sections 23-26 -- dedicated 데일리 디스커버리 page, with real field/region filter tabs
# wired to O-3C's actual 11-field taxonomy output (daily_taxonomy_result.json), not a hardcoded
# count or a decorative button. Tabs are plain anchor-linked <details>/<section> groups (no JS
# framework, matching this workspace's static-HTML-only contract) so every count is whatever the
# last real pipeline run computed.
def _daily_taxonomy_live():
    """Best-effort read of the real daily_taxonomy_result.json sidecar. Never raises -- an
    honest NOT_AVAILABLE state when the taxonomy pipeline hasn't run yet is correct, not an
    error to hide."""
    path = HERE.parent / "daily_taxonomy" / "daily_taxonomy_result.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def render_daily_discovery():
    result = _daily_taxonomy_live()
    if not result:
        return _shell(f"{_ko('daily_discovery')} / Daily Discovery", "daily_discovery",
                       '<h2>데일리 디스커버리</h2>'
                       '<p class="empty">NOT_AVAILABLE -- daily_taxonomy 파이프라인이 아직 실행되지 '
                       '않았습니다.</p>')

    field_counts = result["field_counts_any"]
    region_counts = result["region_counts"]
    total = result["total_pass_documents"]

    region_order = ["KR", "US", "CN", "EU", "JP", "IN", "UNKNOWN"]
    region_pills = "".join(
        f'<span class="badge">{_esc(r)}: {_esc(region_counts.get(r, 0))}</span> '
        for r in region_order if r in region_counts or r != "UNKNOWN"
    )
    other_regions = {k: v for k, v in region_counts.items() if k not in region_order}
    if other_regions:
        region_pills += "".join(f'<span class="badge">{_esc(k)}: {_esc(v)}</span> '
                                  for k, v in other_regions.items())

    sections = []
    for field in _taxonomy.FIELDS:
        docs = [d for d in result["per_document"].values()
                if field in ([d["primary_field"]] if d["primary_field"] else []) + d["secondary_fields"]]
        rows = "".join(
            f'<li>{_esc(d["title"])} &middot; {_esc(d["country"])} &middot; '
            f'{_esc(d["ai_relevance"]["gate"])}</li>'
            for d in docs[:20]
        )
        sections.append(
            f'<details><summary><strong>{_esc(field)}</strong> ({len(docs)}건)</summary>'
            + (f'<ul>{rows}</ul>' if rows else '<p class="empty">실제 corpus에 이 분야 항목이 없습니다 '
                                                 '(NO_DISCOVERY_IN_CURRENT_CORPUS).</p>')
            + (f'<p class="empty">상위 20건만 표시, 전체 {len(docs)}건</p>' if len(docs) > 20 else "")
            + '</details>'
        )

    return _shell(f"{_ko('daily_discovery')} / Daily Discovery", "daily_discovery", (
        f'<h2>오늘의 AI Intelligence Discovery</h2>'
        f'<p>AI Relevance Gate PASS {total}건 기준 (전체 {_esc(_ai_gate_total())}건 중). '
        '분야는 복수 라벨 가능(primary+secondary 합산 표시), 지역은 추측 없이 실제 출처 메타데이터 기반.</p>'
        f'<h3>지역 필터</h3><p>{region_pills}</p>'
        f'<h3>분야별</h3>{"".join(sections)}'
    ))


def _ai_gate_total():
    path = HERE.parent / "ai_relevance_gate" / "ai_relevance_gate_result.json"
    if not path.exists():
        return "N/A"
    try:
        return json.loads(path.read_text(encoding="utf-8"))["document_count"]
    except Exception:
        return "N/A"


# O-3D section 28 -- dedicated 이머징 이슈 page (full list; overview keeps only a summary).
def render_emerging_issues():
    emerging = dd.emerging_issues(data_dir=str(op.ROOT / "data"))
    body = _emerging_issues_section_html(emerging)
    return _shell(f"{_ko('emerging_issues')} / Emerging Issues", "emerging_issues", body)


# O-3D sections 14-18, 29 -- 리서치(Research Queue) page. Shows the real research_queue.json
# the Candidate Engine maintains, grouped into Te's 4 buckets. Hermes is explicitly not
# connected yet (section 17/29) -- said plainly, never implied otherwise.
_RESEARCH_BUCKETS = (
    ("RESEARCH_PENDING", "지금 확인할 것"),
    ("RESEARCH_IN_PROGRESS", "계속 추적"),
    ("RESEARCH_BLOCKED", "대기"),
    ("RESEARCH_DONE", "완료"),
    ("RESEARCH_FAILED", "실패"),
)


def render_research_queue():
    path = HERE.parent / "intelligence_candidate" / "research_queue.json"
    rows = []
    if path.exists():
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            rows = []

    by_status = {}
    for r in rows:
        by_status.setdefault(r.get("research_status", "RESEARCH_PENDING"), []).append(r)

    sections = []
    for status_key, ko_label in _RESEARCH_BUCKETS:
        bucket_rows = by_status.get(status_key, [])
        cards = "".join(
            '<div class="kpi" style="flex:0 0 100%;max-width:100%">'
            f'<div><strong>{_esc(r["title"])}</strong> &middot; {_esc(r["field"])} &middot; '
            f'{_esc(r["region"])}</div>'
            f'<div>{_esc(r["reason"])}</div>'
            f'<div>Priority: {_esc(r["priority"])} &middot; Evidence Quality: {_esc(r["evidence_quality"])} '
            '(별도 지표, 합산하지 않음)</div>'
            f'<div>관련 Event {_esc(r["related_events"])} &middot; 독립 출처 {_esc(r["sources"])} &middot; '
            f'Source Tier: {_esc(r["source_tiers"])}</div>'
            f'<div class="empty">최초 포착 {_esc(r["first_seen"][:10])} / 최근 갱신 {_esc(r["last_seen"][:10])}</div>'
            '</div>'
            for r in bucket_rows
        )
        sections.append(
            f'<h2>{ko_label} ({len(bucket_rows)})</h2>'
            + (f'<div class="kpi-row">{cards}</div>' if cards
               else '<p class="empty">해당 항목이 없습니다.</p>')
        )

    return _shell(f"{_ko('research_queue')} / Research Queue", "research_queue", (
        '<div style="border:1px solid var(--line);background:var(--soft);padding:10px 14px;'
        'margin-bottom:16px;font-size:0.85em"><strong>Hermes 미연결</strong> -- 이 Queue는 '
        'Research Worker Interface를 통해 향후 Hermes(또는 다른 Agent)가 읽을 수 있는 일반 '
        'schema이지만, 현재 세션에서 자동으로 조사를 수행하는 Agent는 연결되어 있지 않습니다.</div>'
        + "".join(sections)
    ))


def _index_detail_link(row):
    if row["latest_report_id"]:
        return f'<a href="../report/{_esc(row["latest_report_id"])}/">Inspect</a>'
    return '<span class="empty">no report built</span>'


def render_intelligence_index():
    rows = op.intelligence_index()
    body_rows = "".join(
        f'<tr><td>{_esc(row["topic"])}</td>'
        f'<td class="mono">{_esc(row["io_version"])}</td>'
        f'<td class="mono">{_esc(row["latest_report_version"])}</td>'
        f'<td>{_status(row["readiness"])}</td>'
        f'<td class="mono">{_esc(row["updated"])}</td>'
        f'<td>{_esc(row["claim_count"])}</td>'
        f'<td>{_esc(row["hypothesis_count"])}</td>'
        f'<td>{_esc(row["evidence_count"])}</td>'
        f'<td>{_esc(row["known_gap_count"])}</td>'
        f'<td>{_index_detail_link(row)}</td>'
        f'</tr>'
        for row in rows
    )
    table = ('<div class="table-wrap"><table><tr><th>Topic</th><th>IO Version</th>'
             '<th>Latest Report Version</th><th>Readiness</th><th>Updated</th>'
             '<th>Claims</th><th>Hypotheses</th><th>Evidence</th><th>Known Gaps</th>'
             f'<th>Detail</th></tr>{body_rows}</table></div>')
    note = ('<p class="empty">No overall quality score is shown here by design -- these are '
            'independent counts only, each traceable to its own backend field.</p>')

    # O-3D section 30 -- the Intelligence page is restructured around 확정 인텔리전스 (above) +
    # Candidates + Change Watch + 반대근거 + Known Gaps, so the two existing Intelligence Objects
    # are never presented as if they were METAXIS's entire scope (section AK/13).
    cand_path = HERE.parent / "intelligence_candidate" / "intelligence_candidates.json"
    candidates_html = '<p class="empty">NOT_AVAILABLE -- Candidate Engine이 아직 실행되지 않았습니다.</p>'
    if cand_path.exists():
        try:
            cand_result = json.loads(cand_path.read_text(encoding="utf-8"))
            cands = cand_result.get("candidates", [])
            if cand_result.get("status") != "OK":
                candidates_html = f'<p class="empty">{_esc(cand_result.get("status"))}</p>'
            elif not cands:
                candidates_html = '<p class="empty">현재 승격 조건을 충족하는 Candidate가 없습니다.</p>'
            else:
                candidates_html = '<div class="kpi-row">' + "".join(
                    '<div class="kpi" style="flex:0 0 100%;max-width:100%">'
                    f'<div><strong>{_esc(c["title"])}</strong> &middot; {_esc(c["field"])} &middot; '
                    f'{_esc(c["region"])}</div>'
                    f'<div>{_esc(c["reason"])}</div>'
                    f'<div class="empty">상태: {_esc(c["status"])} (Claim/IO 아님, Evidence Quality: '
                    f'{_esc(c["evidence_quality"])})</div>'
                    '</div>' for c in cands
                ) + '</div>'
        except Exception:
            pass

    return _shell(f"{_ko('intelligence_index')} / Intelligence Portfolio", "intelligence_index", (
        f'<h2>확정 인텔리전스 / Confirmed Intelligence</h2>{table}{note}'
        f'<h2>Intelligence Candidates</h2>'
        f'{candidates_html}'
        f'{_change_watch_section_html()}'
    ))


def _hyp_rows_html(hyps):
    if not hyps:
        return '<p class="empty">No hypotheses recorded for this topic.</p>'
    rows = "".join(
        f'<tr><td class="mono">{_esc(h.get("hypothesis_code", "H?"))}</td>'
        f'<td>{_esc(h.get("statement", "UNKNOWN"))}</td>'
        f'<td>{_status(h.get("status", "UNKNOWN"))}</td>'
        f'<td class="mono">{_esc(h.get("hypothesis_id"))}</td></tr>'
        for h in hyps
    )
    return ('<div class="table-wrap"><table><tr><th>Code</th><th>Statement</th>'
            f'<th>Canonical Status</th><th>ID</th></tr>{rows}</table></div>')


def render_report_sources(r):
    """Operator-only Sources rendering (33F): same source_registry derivation as Public/Print/PDF
    (33G), but keeps the full claim_id -> evidence_independence -> real-URL chain instead of
    stripping it -- Operator must never lose provenance depth that Public legitimately withholds."""
    sources = sreg.build_sources_for_report(r)
    if not sources:
        return '<h3>Sources (출처)</h3><p class="empty">No independently-cited real-URL sources recorded for this report version.</p>'
    rows = "".join(
        f'<tr><td class="mono">{_esc(s["claim_id"] or "UNMATCHED")}</td>'
        f'<td>{_esc(s["institution"])}</td><td>{_esc(s["title"])}</td><td>{_esc(s["year"])}</td>'
        f'<td>{_esc(s["tier"])}</td><td>{_esc(s["observation_or_forecast"])}</td>'
        f'<td>{_status(s["access_status"])}</td>'
        f'<td>{_safe_link(s["url"])}</td>'
        f'<td>{_esc(s["verification"])}</td></tr>'
        for s in sources
    )
    table = (
        '<div class="table-wrap"><table><tr><th>Claim ID</th><th>Institution</th><th>Title</th>'
        '<th>Year</th><th>Tier</th><th>Observation/Forecast</th><th>Access Status</th>'
        f'<th>Real URL</th><th>Link Verification</th></tr>{rows}</table></div>'
    )
    return f'<h3>Sources (출처) -- {len(sources)} actually used</h3>{table}'


def render_report_inspector(report_id):
    insp = op.report_inspector(report_id)
    if insp["status"] != "FOUND":
        return _shell("Report Inspector", None, f'<p class="empty">Report {_esc(report_id)} NOT_FOUND.</p>', depth=2)
    r = insp["report"]
    objects = json.loads((Path(op.ROOT) / "intel" / "intelligence_objects" / "intelligence_objects.json").read_text(encoding="utf-8"))
    obj = objects.get(r["intelligence_id"]) or {}
    topic = obj.get("topic", "UNKNOWN")
    hyps = op.hypotheses_for_topic(topic)
    versions = op.report_versions_for_intelligence(r["intelligence_id"])
    diffs = op.report_version_diffs(r["intelligence_id"])

    header = (
        f'<h2>{_esc(r["topic"])} -- Report {_esc(r["report_id"])}</h2>'
        f'<p class="mono">version={_esc(r["version"])} readiness={_status(r["readiness"])} '
        f'generated_at={_esc(r["generated_at"])}</p>'
        f'<p>Intelligence Object: <span class="mono">{_esc(r["intelligence_id"])}</span> '
        f'(IO version {_esc(obj.get("version", "UNKNOWN"))}, readiness {_status(obj.get("readiness", "UNKNOWN"))})</p>'
        f'<p><a href="../../provenance/{_esc(report_id)}/">Provenance Inspector for this report &#8594;</a></p>'
    )

    def _section(title, section_key):
        s = r["sections"].get(section_key)
        if not s or not s.get("content_blocks"):
            return f'<h3>{_esc(title)}</h3><p class="empty">empty / NOT_AVAILABLE</p>'
        items = "".join(f'<li>{_esc(json.dumps(b, ensure_ascii=False)) if not isinstance(b, str) else _esc(b)}</li>'
                         for b in s["content_blocks"])
        return f'<h3>{_esc(title)} <span class="status">{_esc(s.get("status"))}</span></h3><ul>{items}</ul>'

    hyp_block = f'<h3>Hypotheses (canonical status)</h3>{_hyp_rows_html(hyps)}'
    claims_block = _section("Claims (Key Claims)", "KEY_CLAIMS")
    evidence_block = _section(f"{_ko('evidence')} / Research Evidence", "RESEARCH_EVIDENCE")
    stats_obs = r["sections"].get("STATISTICAL_CONTEXT", {})
    # Section 11 -- Observation and Forecast kept as two visually separated lists, never merged.
    obs_blocks = [b for b in stats_obs.get("content_blocks", []) if isinstance(b, dict) and b.get("temporal_type", "").upper() != "FORECAST"]
    fcst_blocks = [b for b in stats_obs.get("content_blocks", []) if isinstance(b, dict) and b.get("temporal_type", "").upper() == "FORECAST"]
    def _stat_list(blocks):
        if not blocks:
            return '<p class="empty">none</p>'
        return "<ul>" + "".join(f'<li>{_esc(json.dumps(b, ensure_ascii=False))}</li>' for b in blocks) + "</ul>"
    stats_block = (
        '<h3>Statistics</h3>'
        f'<h4>Observation</h4>{_stat_list(obs_blocks)}'
        f'<h4>Forecast</h4>{_stat_list(fcst_blocks)}'
    )
    counterev_block = _section(f"{_ko('counterevidence')} / Counterevidence", "COUNTEREVIDENCE")
    altexp_block = _section("Alternative Explanations", "ALTERNATIVE_EXPLANATIONS")
    geo_block = _section("Geographic Applicability", "GEOGRAPHIC_CONTEXT")
    temp_block = _section("Temporal Applicability", "TEMPORAL_CONTEXT")
    gaps_block = _section("Known Gaps", "EVIDENCE_GAPS")

    def _version_link(v):
        label = f'v{_esc(v["version"])}'
        if v["report_id"] != report_id:
            return f'<a href="../{_esc(v["report_id"])}/">{label}</a>'
        return f'<strong>{label} (this page)</strong>'

    version_rows = "".join(
        f'<tr><td>{_version_link(v)}</td>'
        f'<td>{_esc(v["generated_at"])}</td><td>{_status(v["readiness"])}</td>'
        f'<td>{_esc(v["source_count"])}</td><td>{_esc(v["claim_count"])}</td>'
        f'<td class="mono">{_esc(v["evidence_snapshot"])}</td>'
        f'<td>{"OK" if v["artifacts"]["json"] else "MISSING"}</td>'
        f'<td>{"OK" if v["artifacts"]["pdf"] else "MISSING"}</td>'
        f'<td>{"OK" if v["artifacts"]["operator_html"] else "MISSING"}</td>'
        f'<td>{"OK" if v["artifacts"]["print_html"] else "MISSING"}</td>'
        f'<td>{"OK" if v["artifacts"]["public_html"] else "MISSING"}</td></tr>'
        for v in versions
    )
    versions_block = (
        '<h3>Reports (version history)</h3>'
        '<div class="table-wrap"><table><tr><th>Version</th><th>Generated</th><th>Readiness</th>'
        '<th>Sources</th><th>Claims</th><th>Evidence Snapshot</th>'
        '<th>.json</th><th>.pdf</th><th>_operator.html</th><th>_print.html</th>'
        f'<th>_product_public.html</th></tr>{version_rows}</table></div>'
    )
    diff_rows = "".join(
        f'<tr><td>{_esc(d["from_version"]) if d["from_version"] is not None else "--"} &#8594; v{_esc(d["to_version"])}</td>'
        f'<td>{", ".join(_esc(x) for x in d["diff_types"])}</td></tr>'
        for d in diffs
    )
    diff_block = (
        '<h3>Version Diffs (via report_engine.diff_reports())</h3>'
        f'<div class="table-wrap"><table><tr><th>Transition</th><th>Diff Types</th></tr>{diff_rows}</table></div>'
    )
    provenance_block = (
        '<h3>Provenance</h3>'
        f'<p><a href="../../provenance/{_esc(report_id)}/">Full Report &#8594; IO &#8594; Hypothesis &#8594; '
        'Claim &#8594; Evidence &#8594; Source chain &#8594;</a></p>'
    )
    sources_block = render_report_sources(r)

    body = "".join([
        header, "<h3>Current State</h3>", _esc(obj.get("current_state", "UNKNOWN")),
        hyp_block, claims_block, evidence_block, stats_block, counterev_block, altexp_block,
        geo_block, temp_block, gaps_block, sources_block, versions_block, diff_block, provenance_block,
    ])
    return _shell(f"Report {report_id}", None, body, depth=2)


CONNECTIVITY_NOTE = (
    '<p class="empty">Connectivity vocabulary: CONNECTED (fully resolved), '
    'PARTIALLY_CONNECTED (some but not all legs resolved), NOT_CONNECTED (no edge exists in the '
    'data), UNRESOLVED_REFERENCE (an id is referenced but not found in any readable store). '
    'Never fabricated.</p>'
)


def render_provenance_inspector(report_id):
    chain = op.provenance_chain_full(report_id)
    if chain["status"] != "FOUND":
        return _shell("Provenance Inspector", None, f'<p class="empty">Report {_esc(report_id)} NOT_FOUND.</p>', depth=2)
    n = chain["nodes"]
    header = (
        f'<h2>Provenance -- {_esc(n["report"]["report_id"])}</h2>'
        f'<p>REPORT <span class="mono">{_esc(n["report"]["report_id"])}</span> '
        f'(v{_esc(n["report"]["version"])}, {_status(n["report"]["status"])}) &#8594; '
        f'INTELLIGENCE OBJECT <strong>{_esc(n["intelligence_object"]["topic"])}</strong> '
        f'<span class="mono">{_esc(n["intelligence_object"]["intelligence_id"])}</span> '
        f'(v{_esc(n["intelligence_object"]["version"])}, {_status(n["intelligence_object"]["readiness"])})</p>'
        f'{CONNECTIVITY_NOTE}'
    )

    def _ev_html(ev):
        return (
            f'<li><strong>{_esc(ev["evidence_type"])}</strong> '
            f'(temporal: {_esc(ev["temporal_type"])}, attribution: {_esc(ev["attribution"])}) '
            f'<span class="mono">{_esc(ev["evidence_id"])}</span> '
            f'&#8594; SOURCE <span class="mono">{_esc(ev["source_id"])}</span> '
            f'{_status(ev["connectivity"])}</li>'
        )

    hyp_blocks = []
    for h in chain["hypotheses"]:
        claim_items = []
        for c in h["claims"]:
            ev_items = "".join(_ev_html(e) for e in c["evidence"]) or '<li class="empty">no evidence resolved</li>'
            claim_items.append(
                f'<li><strong>{_esc(c["claim_text"])}</strong> '
                f'(type: {_esc(c["claim_type"])}, status: {_esc(c["claim_status"])}) '
                f'<span class="mono">{_esc(c["claim_id"])}</span> {_status(c["connectivity"])}'
                f'<ul>{ev_items}</ul></li>'
            )
        claim_list_html = "".join(claim_items) or '<li class="empty">no claims</li>'
        hyp_blocks.append(
            f'<li><strong>{_esc(h["label"])}</strong> (status: {_esc(h["status"])}) '
            f'<span class="mono">{_esc(h["hypothesis_id"])}</span> {_status(h["connectivity"])}'
            f'<ul>{claim_list_html}</ul></li>'
        )
    hyp_list_html = "".join(hyp_blocks) or '<li class="empty">no hypotheses for this topic</li>'
    hyp_section = (
        '<h3>Hypothesis &#8594; Claim &#8594; Evidence &#8594; Source chain</h3>'
        f'<ul>{hyp_list_html}</ul>'
    )

    stat_rows = "".join(
        f'<tr><td class="mono">{_esc(s["statistical_series_id"])}</td>'
        f'<td class="mono">{_esc(s["source_id"])}</td>'
        f'<td>{_status("CONNECTED" if s["source_id"] != "NOT_CONNECTED" else "NOT_CONNECTED")}</td></tr>'
        for s in chain["statistical_chain"]
    )
    stat_section = (
        '<h3>Claim &#8594; Statistical Series &#8594; Source</h3>'
        '<div class="table-wrap"><table><tr><th>Statistical Series</th><th>Source</th>'
        f'<th>Connectivity</th></tr>{stat_rows}</table></div>'
        if chain["statistical_chain"] else
        '<h3>Claim &#8594; Statistical Series &#8594; Source</h3><p class="empty">none for this report</p>'
    )
    return _shell(f"Provenance {report_id}", None, header + hyp_section + stat_section, depth=2)


PAGES = {
    "overview": render_overview,
    "daily_discovery": render_daily_discovery,
    "emerging_issues": render_emerging_issues,
    "research_queue": render_research_queue,
    "intelligence_index": render_intelligence_index,
    "reports": render_reports, "gaps": render_gaps,
    "rights": render_rights, "sources": render_sources, "source_health": render_source_health,
}


def build_operator_pages(site_dir):
    """Writes site/operator/{page}/index.html for each page. Never raises -- Failure Isolation
    applies here too: one page's error is recorded, the others still build."""
    # N-6 PRIORITY 1 -- Atomic Publish: each page write is temp-written, validated (non-empty,
    # well-formed-ish HTML / parseable JSON) then os.replace()'d into place. A bad render for one
    # page leaves that page's last-good file untouched and is recorded in status["errors"].
    operator_dir = Path(site_dir) / "operator"
    status = {"pages_written": [], "errors": []}
    try:
        operator_dir.mkdir(parents=True, exist_ok=True)
        for name, renderer in PAGES.items():
            try:
                page_dir = operator_dir / name
                page_dir.mkdir(parents=True, exist_ok=True)
                result = apub.atomic_write(page_dir / "index.html", renderer(),
                                            validator=apub.html_validator)
                if result["status"] != "PUBLISHED":
                    raise RuntimeError(result["error"])
                status["pages_written"].append(name)
            except Exception as e:  # noqa: BLE001
                status["errors"].append({"page": name, "error": str(e)})
        overview_result = apub.atomic_write(operator_dir / "index.html", render_overview(),
                                             validator=apub.html_validator)
        if overview_result["status"] != "PUBLISHED":
            status["errors"].append({"page": "index", "error": overview_result["error"]})
        sources_result = apub.atomic_write(
            operator_dir / "sources_full.json",
            json.dumps(op.source_inspector(), ensure_ascii=False, indent=1),
            validator=apub.json_validator)
        if sources_result["status"] != "PUBLISHED":
            status["errors"].append({"page": "sources_full.json", "error": sources_result["error"]})

        # Report Inspector + Provenance Inspector -- one pair of pages per real, on-disk report
        # version (Sections 11-17). Each report_id gets its own directory so every version is
        # independently reachable, matching report_versions_for_intelligence()'s file listing.
        report_paths = sorted(re_.REPORTS_DIR.glob("report_intel_*_v*.json"))
        for path in report_paths:
            report_id = path.stem
            try:
                r_dir = operator_dir / "report" / report_id
                r_dir.mkdir(parents=True, exist_ok=True)
                res = apub.atomic_write(r_dir / "index.html", render_report_inspector(report_id),
                                         validator=apub.html_validator)
                if res["status"] != "PUBLISHED":
                    raise RuntimeError(res["error"])
                status["pages_written"].append(f"report/{report_id}")
            except Exception as e:  # noqa: BLE001
                status["errors"].append({"page": f"report/{report_id}", "error": str(e)})
            try:
                p_dir = operator_dir / "provenance" / report_id
                p_dir.mkdir(parents=True, exist_ok=True)
                res = apub.atomic_write(p_dir / "index.html", render_provenance_inspector(report_id),
                                         validator=apub.html_validator)
                if res["status"] != "PUBLISHED":
                    raise RuntimeError(res["error"])
                status["pages_written"].append(f"provenance/{report_id}")
            except Exception as e:  # noqa: BLE001
                status["errors"].append({"page": f"provenance/{report_id}", "error": str(e)})
    except Exception as e:  # noqa: BLE001
        status["errors"].append({"page": None, "error": str(e)})
    return status


if __name__ == "__main__":
    site_dir = sys.argv[1] if len(sys.argv) > 1 else str(op.ROOT / "site")
    result = build_operator_pages(site_dir)
    print(json.dumps(result, ensure_ascii=False))
