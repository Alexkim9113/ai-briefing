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
sys.path.insert(0, str(HERE.parent / "global_source_network"))
import taxonomy as _taxonomy  # noqa: E402
import candidate_engine as _candidates  # noqa: E402
import coverage_matrix as _coverage  # noqa: E402

FONT_LINKS = (
    '<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>'
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Unbounded:wght@500;700;800&text=METAXIS&display=swap">'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@600;700&display=swap">'
    '<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">'
)

# O-3.6B: Public(metaxis.kr)과 같은 METAXIS 디자인 시스템(다크 테마, Pretendard/Noto Serif KR,
# cyan-blue-violet 그라데이션 포인트)을 Operator에 그대로 적용한다. briefing.py의 :root 다크
# 테마 변수와 동일한 값을 쓴다 -- 새 디자인을 만드는 것이 아니라 이미 있는 Public 디자인을 재사용.
CSS = """
:root{--bg:#07061a;--card:#0f0d26;--ink:#eceef6;--text:#d9dcea;--sub:#9097b3;--line:#1f1c40;--warn:#f3c969;--bad:#ff6b7a;--ok:#5fd394;
--accent:#9ab8ff;--soft:#16143a;--glow:#1a1340;--shadow:0 8px 24px rgba(0,0,0,.45);--grad:linear-gradient(90deg,#12e3ff,#3b7bff 55%,#8b2cff)}
html{overflow-x:hidden}
*{box-sizing:border-box}
body{font-family:'Pretendard Variable','Pretendard',-apple-system,sans-serif;color:var(--text);
background:radial-gradient(ellipse at 50% -10%,var(--glow) 0%,var(--bg) 55%) fixed,var(--bg);
margin:0;padding:0;line-height:1.65;font-size:15.5px;overflow-wrap:break-word;word-break:keep-all}
.mono{font-family:'Space Grotesk','Pretendard',monospace;overflow-wrap:anywhere;word-break:break-word}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
a:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
header{position:sticky;top:0;z-index:20;border-bottom:1px solid var(--line);padding:16px 24px;
background:rgba(6,5,13,.86);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px)}
header h1{font-family:'Noto Serif KR','Pretendard Variable',serif;letter-spacing:-.02em;font-size:1.15em;
font-weight:700;margin:0;overflow-wrap:break-word;color:var(--ink)}
header h1 .mx{font-family:Unbounded,'Pretendard Variable',sans-serif;font-weight:700;letter-spacing:.1em;
background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
nav{position:sticky;top:57px;z-index:19;display:flex;flex-wrap:wrap;gap:4px;padding:10px 24px;
border-bottom:1px solid var(--line);font-size:0.92em;font-weight:600;background:rgba(7,6,26,.92);
backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px)}
nav a{color:var(--sub);text-decoration:none;padding:6px 14px;border-radius:99px;transition:background .15s,color .15s}
nav a:hover{background:var(--soft);color:var(--ink);text-decoration:none}
nav a.active{background:linear-gradient(var(--soft),var(--soft)) padding-box,var(--grad) border-box;
border:1.5px solid transparent;color:var(--ink)}
main{max-width:1040px;margin:0 auto;padding:28px 24px 64px}
main h2{font-family:'Noto Serif KR','Pretendard Variable',serif;font-size:1.5em;font-weight:700;
color:var(--ink);letter-spacing:-.01em;margin:34px 0 14px}
main h2:first-child{margin-top:0}
main h2::before{content:"";display:inline-block;width:5px;height:.85em;border-radius:3px;
background:var(--grad);margin-right:10px;vertical-align:-.06em}
main p{color:var(--text)}
.table-wrap{overflow-x:auto;border-radius:14px;border:1px solid var(--line)}
table{border-collapse:collapse;width:100%;margin:0;font-size:0.92em;min-width:420px}
td,th{border-bottom:1px solid var(--line);border-right:none;border-left:none;border-top:none;padding:9px 14px;text-align:left;vertical-align:top}
th{background:var(--soft);font-weight:700;color:var(--ink)}
tr:last-child td{border-bottom:none}
tr:hover td{background:rgba(255,255,255,.02)}
.status{font-size:0.8em;font-weight:600;padding:2px 10px;border-radius:99px;border:1px solid var(--line);display:inline-block;max-width:100%;overflow-wrap:break-word}
.status-healthy,.status-ready{border-color:var(--ok);color:var(--ok)}
.status-blocked,.status-not_found,.status-pdf_failed{border-color:var(--bad);color:var(--bad)}
.status-degraded,.status-conditionally_ready,.status-auth_required{border-color:var(--warn);color:var(--warn)}
.status-not_instrumented,.status-unknown,.status-not_available{border-color:var(--sub);color:var(--sub)}
.empty{color:var(--sub);font-style:italic}
.kpi-row{display:flex;flex-wrap:wrap;gap:14px;margin:16px 0}
.kpi{border:1px solid var(--line);border-radius:16px;padding:16px 18px;box-sizing:border-box;background:var(--card);
box-shadow:var(--shadow);flex:0 0 calc(33.333% - 10px);max-width:calc(33.333% - 10px);min-width:0;overflow-wrap:break-word;
transition:border-color .15s,transform .15s}
.kpi:hover{border-color:var(--accent);transform:translateY(-1px)}
.kpi .n{font-family:'Space Grotesk',monospace;font-size:1.5em;font-weight:700;background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
.kpi .l{color:var(--sub);font-size:0.8em;text-transform:uppercase;letter-spacing:.04em;overflow-wrap:break-word;margin-top:4px}
footer{margin-top:56px;padding:20px 24px 40px;border-top:1px solid var(--line);font-size:13px;color:var(--sub);text-align:center}
@media (max-width: 480px){
  main{padding:18px 16px 48px}
  main h2{font-size:1.28em}
  header{padding:12px 16px}
  nav{padding:8px 16px;top:49px}
  .kpi-row{gap:10px}
  .kpi{flex:0 0 calc(50% - 5px);max-width:calc(50% - 5px);padding:12px 14px}
}
"""

NAV_ITEMS = ("overview", "daily_discovery", "emerging_issues", "research_queue",
             "intelligence_index", "reports", "gaps", "rights", "sources", "source_health")

# METAXIS OPERATOR -- NAVIGATION FINAL RESTRUCTURE (2026-10-03), STEP 1 ONLY: supersedes earlier
# nav attempts same day. Top-level Navigation is now exactly these 5 user-facing areas, with "오늘"
# as the default landing page (operator/index.html already renders render_overview(), see
# build_operator_pages). Every slug/route/backend object above is unchanged (nothing deleted,
# nothing renamed, nothing rebuilt this step). research_queue/gaps/rights/sources/source_health
# stay reachable at their existing URLs but are deliberately NOT linked from the top nav -- that is
# later-STEP work (STEP 2 = Report 구조/생성 방식 개편, per Te's instruction).
TOP_NAV = (
    ("오늘", "overview"),
    ("수집정보", "daily_discovery"),
    ("이슈", "emerging_issues"),
    ("인텔리전스", "intelligence_index"),
    ("보고서", "reports"),
)

# Korean-first labels (Te's O-2C mapping). Presentation text only -- never changes route slugs,
# internal IDs, or data. English kept as a small secondary label alongside the Korean primary.
KO_LABELS = {
    "overview": "오늘",
    "daily_discovery": "수집정보",
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
        f'<a href="{up}{slug}/" class="{"active" if slug == active else ""}">{_esc(label)}</a>'
        for label, slug in TOP_NAV
    )
    return f"<nav aria-label='Operator navigation'>{links}</nav>"


def _shell(title, active, body, depth=1, extra_body_attrs=""):
    return (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>Operator -- {_esc(title)}</title>{FONT_LINKS}<style>{CSS}</style></head>"
        f"<body{extra_body_attrs}>"
        "<header><h1><span class='mx'>METAXIS</span> Intelligence Workbench (Operator)</h1></header>"
        f"{_nav(active, depth)}<main aria-label='Operator workspace'>{body}</main>"
        "<footer>METAXIS Operator &middot; Private Workspace</footer></body></html>"
    )


PUBLIC_SAFE_BANNER = (
    '<div style="border:1px solid var(--line);background:var(--soft);padding:10px 14px;'
    'margin-bottom:16px;font-size:0.85em">'
    '<strong>METAXIS OPERATOR / PRIVATE WORKSPACE</strong><br>'
    'This workspace is built from intel_private/ on this repository\'s private main branch, and '
    '(since O-3.6B) deployed as a separate, access-controlled site -- never published to the '
    'public gh-pages site/metaxis.kr. Real-identity-verified login only (Cloudflare Access + '
    'email one-time PIN), never a client-side password gate. See '
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


# METAXIS OPERATOR -- TODAY BRIEFING REBUILD (2026-10-03), scoped to the "오늘" page only.
# Deterministic-only (section 12 of the directive allows an LLM synthesis step for the narrative
# sentences, but does not require one this STEP, and this environment has no model key configured
# -- so every sentence below is built only from fields daily_discovery.daily_discovery_items()
# already computes from real, already-collected items: title, source, sources[], field, country,
# why_it_matters, evidence_status. Nothing here invents a fact not present in that data.
_FIELD_WATCHPOINTS = {
    "기술": ("관련 기업의 신제품·기술 발표", "경쟁사 대응 동향", "특허·기술표준 동향"),
    "산업·경제": ("투자·M&A 동향", "실적 발표", "공급망 변화"),
    "노동·고용": ("고용·채용 지표 변화", "노동조합·정책 대응", "기업 인력 재배치"),
    "법·제도": ("관련 법안 발의·통과 여부", "규제기관의 추가 조치", "법원 판결"),
    "정책·국제질서": ("정부·국제기구의 후속 조치", "주요국 정책 비교", "외교적 대응"),
    "의료·헬스케어": ("임상·규제 승인 여부", "의료기관 도입 현황", "안전성 이슈"),
    "에너지·환경": ("전력 계약 및 인프라 투자", "에너지 정책·규제 변화", "환경영향 평가"),
    "국방·안보": ("주요국 군사·안보 대응", "수출통제 조치", "기술 유출 이슈"),
    "교육·사회": ("교육기관 도입 현황", "여론 반응", "사회적 논쟁 확산 여부"),
    "문화·예술": ("창작자·업계 반응", "저작권 관련 논의", "대중 수용도"),
    "미디어·콘텐츠": ("플랫폼 정책 변화", "콘텐츠 유통 구조 변화", "규제당국 대응"),
}


def _why_it_matters_sentence(why_it_matters):
    """Expands daily_discovery.py's terse why_it_matters code into a one-sentence explanation,
    without adding any fact that code didn't already encode."""
    w = why_it_matters or ""
    if w.startswith("정책 키워드:"):
        kw = w.split(":", 1)[1].strip()
        return f"'{kw}' 관련 정책·규제 키워드가 포함되어 있어, 법·제도 변화로 이어질 가능성을 시사한다."
    if w == "Tier 1 출처":
        return "공신력 있는 Tier 1 출처에서 보도되어 신뢰도가 높은 사안이다."
    return None  # honest: no fabricated interpretation when the signal itself is unclear


def _today_briefing_card(item):
    sources = item.get("sources") or [{"institution": item.get("source"), "url": item.get("url")}]
    why = _why_it_matters_sentence(item.get("why_it_matters"))
    if why is None:
        return None  # section 7: never show an interpretation that wasn't actually derived
    title = _esc(item["title_ko"])
    fact = title
    if len(sources) > 1:
        fact += f" 관련 보도가 {len(sources)}개 독립 출처에서 확인됐다."
    field = item.get("field")
    watch = _FIELD_WATCHPOINTS.get(field, ())
    watch_html = "".join(f"<li>{_esc(w)}</li>" for w in watch) if watch else ""
    tags = " &middot; ".join(x for x in (_esc(field) if field else "", _esc(item.get("country")) if item.get("country") else "") if x)
    sources_list_html = "".join(
        f'<li>{_esc(s.get("institution"))}: {_safe_link(s.get("url"))}</li>' for s in sources
    )
    return (
        '<div class="kpi" style="flex:0 0 100%;max-width:100%">'
        f'<div><strong>{title}</strong></div>'
        + (f'<div class="empty">{tags}</div>' if tags else "")
        + f'<div><b>무슨 일이 있었나</b><br>{fact}</div>'
        f'<div><b>왜 중요한가</b><br>{_esc(why)}</div>'
        + (f'<div><b>무엇을 봐야 하나</b><ul>{watch_html}</ul></div>' if watch_html else "")
        + f'<div class="empty">Sources {len(sources)}<ul>{sources_list_html}</ul></div>'
        '</div>'
    )


def _today_briefing_section_html(discovery_items, top_n=10):
    """The '오늘' landing page per the TODAY BRIEFING REBUILD directive: Issue/Event-level cards
    with 무슨 일이 있었나/왜 중요한가/무엇을 봐야 하나, never raw internal fields (DISCOVERY_ONLY,
    Claim 아님, GLOBAL/UNKNOWN, candidate/event/source counts, long RSS URLs). Built from
    daily_discovery_items() -- already event-clustered across sources, already real sources/urls
    -- never claims.json, never a fabricated example. Honestly empty when nothing passes."""
    cards = [c for c in (_today_briefing_card(it) for it in discovery_items[:top_n]) if c]
    raw_date = discovery_items[0].get("date") if discovery_items else None
    date_str = raw_date[:10] if isinstance(raw_date, str) and len(raw_date) >= 10 else None
    subtitle = f'{date_str.replace("-", ".")} &middot; Daily Intelligence Briefing' if date_str else "Daily Intelligence Briefing"
    if not cards:
        return (
            f'<p class="empty">{subtitle}</p>'
            '<h2>오늘의 핵심 변화</h2>'
            '<p class="empty">오늘 운영자가 읽을 만한 핵심 변화가 확인되지 않았습니다 '
            '(정직한 결과이며, 조작된 예시를 넣지 않습니다). 전체 수집 자료는 '
            f'<a href="../daily_discovery/">정보</a>에서 확인할 수 있습니다.</p>'
        )
    return (
        f'<p class="empty">{subtitle}</p>'
        f'<h2>오늘의 핵심 변화 ({len(cards)})</h2>'
        f'<div class="kpi-row">{"".join(cards)}</div>'
        f'<p class="empty">전체 수집 자료는 <a href="../daily_discovery/">정보</a>에서 확인할 수 있습니다.</p>'
    )


_MX_FILTER_CSS = """
.mx-filters{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}
.mx-filters select{background:var(--soft);color:var(--ink);border:1px solid var(--line);
border-radius:8px;padding:6px 10px;font-family:inherit;font-size:0.9em}
.mx-item{border:1px solid var(--line);border-radius:12px;padding:12px 14px;background:var(--card);
margin-bottom:10px}
.mx-item h3{margin:0 0 6px 0;font-size:1em}
.mx-item h3 a{color:var(--ink);text-decoration:none}
.mx-item h3 a:hover{color:var(--accent)}
.mx-item p{margin:6px 0;color:var(--ink);font-size:0.92em}
.mx-meta{color:var(--sub);font-size:0.8em}
.mx-meta span{margin-right:10px}
"""


def _raw_item_card_html(row):
    """One real collected item, exactly as briefing.py stored it -- title (linked to the real
    original URL), a readable 2-3 line summary, field/region/source/published time. Never a raw
    internal code, never a synthesized Issue -- per the FRONTEND FIRST directive (2026-10-03),
    every collected item must be individually readable, not filtered down to an 'important' few."""
    title = _esc(row["title"])
    link = _safe_link(row["url"], title) if row.get("url") else f'<span>{title}</span>'
    summary = _esc(row["summary"]) if row.get("summary") else '<span class="empty">요약 없음</span>'
    return (
        f'<div class="mx-item" data-field="{_esc(row["field"])}" data-region="{_esc(row["region"])}" '
        f'data-source="{_esc(row["source"])}" data-date="{_esc(row.get("date") or "")}">'
        f'<h3>{link}</h3>'
        f'<p>{summary}</p>'
        f'<div class="mx-meta"><span>{_esc(row["field"])}</span><span>{_esc(row["region"])}</span>'
        f'<span>{_esc(row["source"])}</span><span>{_esc(row["published"])}</span></div>'
        '</div>'
    )


_MX_FILTER_JS = """
<script>
function mxFilter(){
  var f=document.getElementById('mx-f-field'); f=f?f.value:'';
  var r=document.getElementById('mx-f-region'); r=r?r.value:'';
  var s=document.getElementById('mx-f-source'); s=s?s.value:'';
  var d=document.getElementById('mx-f-date'); d=d?d.value:'';
  var items=document.querySelectorAll('#mx-list .mx-item');
  var shown=0;
  items.forEach(function(el){
    var ok=(!f||el.dataset.field===f)&&(!r||el.dataset.region===r)&&(!s||el.dataset.source===s)&&(!d||el.dataset.date===d);
    el.style.display=ok?'':'none';
    if(ok){shown++;}
  });
  var cnt=document.getElementById('mx-count');
  if(cnt){cnt.textContent=shown;}
}
</script>
"""


def _mx_select(id_, label, options, selected_all_label, onchange="mxFilter()"):
    opts = f'<option value="">{_esc(selected_all_label)}</option>' + "".join(
        f'<option value="{_esc(o)}">{_esc(o)}</option>' for o in options
    )
    return f'<select id="{id_}" onchange="{_esc(onchange)}" aria-label="{_esc(label)}">{opts}</select>'


def _event_card_to_row(card):
    """Adapts a daily_discovery._build_card() event dict to the same row shape
    _raw_item_card_html() renders -- so '오늘의 주요 정보' cards look identical in structure to
    '수집정보' cards (제목/핵심 내용/분야/지역/Source/날짜/원문 URL), per directive section 13.C."""
    return {
        "title": card["title_ko"], "summary": card.get("summary") or "",
        "field": card["field"], "region": card["country"],
        "source": card["source"], "published": card["date"], "url": card["url"],
        "date": None,
    }


def _issue_card_html(issue):
    watch = _FIELD_WATCHPOINTS.get(issue["field"], ())
    watch_html = "".join(f"<li>{_esc(w)}</li>" for w in watch) if watch else ""
    events_html = "".join(f"<li>{_esc(t)}</li>" for t in issue["event_titles"])
    sources_html = "".join(
        f'<li>{_esc(s["institution"])}: {_safe_link(s["url"])}</li>' for s in issue["sources"]
    )
    return (
        '<div class="kpi" style="flex:0 0 100%;max-width:100%">'
        f'<div><strong>{_esc(issue["field"])} &middot; \'{_esc(issue["matched_keyword"])}\'</strong></div>'
        f'<div><b>무슨 일이 있었나</b><ul>{events_html}</ul></div>'
        f'<div><b>왜 중요한가</b><br>{_esc(issue["why_it_matters"])}</div>'
        f'<div><b>무엇이 변하고 있는가</b><br>{_esc(issue["whats_changing"])}</div>'
        + (f'<div><b>앞으로 볼 것</b><ul>{watch_html}</ul></div>' if watch_html else "")
        + f'<div class="empty">Sources {len(issue["sources"])}<ul>{sources_html}</ul></div>'
        '</div>'
    )


def render_overview():
    """METAXIS -- DAILY IMPORTANCE SELECTION DIRECTIVE (2026-10-03): '오늘' is built in three
    layers over real, already-collected data (never re-crawled, never sample/hardcoded):
      A. 오늘의 관측 -- one honest, factual line (count of qualifying Issues/Events). No LLM is
         available in this session, so no interpretive narrative is generated here; forcing one
         without real synthesis would be fabrication, which section 0 explicitly forbids.
      B. 오늘의 핵심 Issue -- today_core_issues(): only emitted when >=2 Importance-Gate-qualifying
         Events genuinely share a field + matched keyword (directive section 12). Honestly empty
         most days.
      C. 오늘의 주요 정보 -- today_important_events(): event-level (not raw article count), scored
         by the 6-factor Importance Gate and cut to the highest scorers (~5-10, never padded).
    '수집정보' (render_daily_discovery) is unchanged and still carries every raw collected item --
    the Importance Gate only decides what surfaces here, nothing is ever deleted."""
    important = dd.today_important_events(data_dir=str(op.ROOT / "data"))
    issues = dd.today_core_issues(important)
    _rows, date_str = dd.raw_items_for_day(data_dir=str(op.ROOT / "data"))
    subtitle = f'{date_str.replace("-", ".")}' if date_str else "오늘"

    if not important:
        return _shell(f"{_ko('overview')} / Today", "overview", (
            f'{PUBLIC_SAFE_BANNER}<p class="empty">{_esc(subtitle)}</p>'
            '<h2>오늘의 관측</h2>'
            '<p class="empty">오늘 Importance Gate를 통과한 주요 사건이 확인되지 않았습니다 '
            '(정직한 결과이며, 예시를 넣지 않습니다). 전체 수집 자료는 '
            f'<a href="../daily_discovery/">수집정보</a>에서 확인할 수 있습니다.</p>'
        ))

    observation = (
        f'오늘 Importance Gate를 통과한 사건 {len(important)}건'
        + (f', 그중 핵심 Issue {len(issues)}건이 확인됐습니다.' if issues else '이 확인됐습니다. 오늘은 여러 사건을 묶을 만한 뚜렷한 Issue는 없었습니다.')
    )

    issue_section = ""
    if issues:
        issue_section = (
            f'<h2>오늘의 핵심 Issue ({len(issues)})</h2>'
            f'<div class="kpi-row">{"".join(_issue_card_html(i) for i in issues)}</div>'
        )

    fields_present = sorted({ev["field"] for ev in important})
    info_cards = "".join(_raw_item_card_html(_event_card_to_row(ev)) for ev in important)
    info_section = (
        f'<h2>오늘의 주요 정보 ({len(important)})</h2>'
        f'<div class="mx-filters">{_mx_select("mx-f-field", "분야", fields_present, "분야 전체")}</div>'
        f'<div id="mx-list">{info_cards}</div>'
        f'{_MX_FILTER_JS}'
    )

    return _shell(f"{_ko('overview')} / Today", "overview", (
        f'{PUBLIC_SAFE_BANNER}<style>{_MX_FILTER_CSS}</style>'
        f'<p class="empty">{_esc(subtitle)}</p>'
        f'<h2>오늘의 관측</h2><p>{_esc(observation)}</p>'
        f'{issue_section}{info_section}'
        f'<p class="empty">전체 수집 자료는 <a href="../daily_discovery/">수집정보</a>에서 확인할 수 있습니다.</p>'
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
        f'{_render_coverage_section()}'
    ))


def _render_coverage_section():
    """Section 37/38: 관측 범위(Global Source Coverage) -- folded into the existing 출처 page
    rather than a new nav item (section 50: UI 확장 금지). Honest NOT_AVAILABLE when the sidecar
    hasn't been produced yet; never a fabricated number."""
    if not _coverage.OUT_PATH.exists():
        return (
            '<h2>관측 범위 (Global Source Coverage)</h2>'
            '<p class="empty">아직 Coverage Matrix 결과가 없습니다 (NOT_AVAILABLE).</p>'
        )
    result = json.loads(_coverage.OUT_PATH.read_text(encoding="utf-8"))
    core = ("KR", "US", "CN", "EU", "JP", "IN")
    reg = result.get("registered_by_country", {})
    act = result.get("active_source_count_by_country", {})
    rows = "".join(
        f'<tr><td>{_esc(c)}</td><td>{_esc(reg.get(c, 0))}</td><td>{_esc(act.get(c, 0))}</td></tr>'
        for c in core
    )
    return (
        '<h2>관측 범위 (Global Source Coverage)</h2>'
        f'<p>생성 시각: {_esc(result.get("generated_at", "UNKNOWN"))} '
        f'(등록 미분류 {_esc(result.get("registered_uncounted", 0))}건)</p>'
        '<div class="table-wrap"><table>'
        '<tr><th>국가</th><th>등록 Source</th><th>최근 관측 Source</th></tr>'
        f'{rows}</table></div>'
        f'<p class="empty">{_esc(result.get("matrix_row_note", ""))}</p>'
    )


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
    """METAXIS OPERATOR -- FRONTEND FIRST (2026-10-03): '수집정보' is now a human-browsable archive
    of every item METAXIS has ever collected (reads data/*.json directly, the same source-of-truth
    briefing.py writes -- never the AI Relevance Gate/daily_taxonomy_result.json sidecar, which
    only covers gate-PASSed items from whenever that separate pipeline last ran). Filters: 날짜,
    분야, 지역, Source. The old gate-based summary view (_daily_taxonomy_live) is NOT deleted, just
    no longer rendered here."""
    rows = dd.archive_items(data_dir=str(op.ROOT / "data"))
    if not rows:
        return _shell(f"{_ko('daily_discovery')} / Archive", "daily_discovery",
                       '<h2>수집정보</h2>'
                       '<p class="empty">아직 수집된 데이터가 없습니다.</p>')

    dates = sorted({r["date"] for r in rows if r.get("date")}, reverse=True)
    fields_present = sorted({r["field"] for r in rows})
    regions_present = sorted({r["region"] for r in rows})
    sources_present = sorted({r["source"] for r in rows})
    cards = "".join(_raw_item_card_html(r) for r in rows)
    body = (
        f'<p class="empty">전체 수집 <span id="mx-count">{len(rows)}</span>건</p>'
        '<h2>수집정보</h2>'
        '<div class="mx-filters">'
        f'{_mx_select("mx-f-date", "날짜", dates, "날짜 전체")}'
        f'{_mx_select("mx-f-field", "분야", fields_present, "분야 전체")}'
        f'{_mx_select("mx-f-region", "지역", regions_present, "지역 전체")}'
        f'{_mx_select("mx-f-source", "Source", sources_present, "Source 전체")}'
        '</div>'
        f'<div id="mx-list">{cards}</div>'
        f'{_MX_FILTER_JS}'
    )
    return _shell(f"{_ko('daily_discovery')} / Archive", "daily_discovery", (
        f'<style>{_MX_FILTER_CSS}</style>{body}'
    ))


def _ai_gate_total():
    path = HERE.parent / "ai_relevance_gate" / "ai_relevance_gate_result.json"
    if not path.exists():
        return "N/A"
    try:
        return json.loads(path.read_text(encoding="utf-8"))["document_count"]
    except Exception:
        return "N/A"


# METAXIS OPERATOR -- ISSUE KNOWLEDGE LAYER (2026-10-03). '이슈' is now a persistent,
# cross-day knowledge layer built from dd.issue_knowledge_candidates() over the FULL real archive
# -- not the single-day dd.emerging_issues() this page used to show (that function and its
# section HTML are NOT deleted, just no longer linked from this page).
_ISSUE_STATUS_KO = {
    "NEW": "신규", "DEVELOPING": "진행 중", "STABLE": "안정",
    "ACCELERATING": "강화 중", "WEAKENING": "약화 중",
}

_ISSUE_FILTER_JS = """
<script>
function mxIssueFilter(){
  var f=document.getElementById('mx-if-field'); f=f?f.value:'';
  var r=document.getElementById('mx-if-region'); r=r?r.value:'';
  var p=document.getElementById('mx-if-period'); p=p?parseInt(p.value||'0',10):0;
  var maxDate=new Date(document.body.getAttribute('data-dataset-max'));
  var cutoff=null;
  if(p){ cutoff=new Date(maxDate); cutoff.setDate(cutoff.getDate()-p); }
  var items=document.querySelectorAll('#mx-issue-list .mx-item');
  items.forEach(function(el){
    var ok=(!f||el.dataset.field===f)&&(!r||el.dataset.region===r);
    if(ok && cutoff){
      var last=new Date(el.dataset.lastObserved);
      ok = last >= cutoff;
    }
    el.style.display=ok?'':'none';
  });
}
</script>
"""


def _issue_card_summary_html(issue):
    status = issue.get("status")
    status_html = f'<span class="status status-ready">{_esc(_ISSUE_STATUS_KO.get(status, status))}</span>' if status else ""
    return (
        f'<div class="mx-item" data-field="{_esc(issue["field"])}" data-region="{_esc(issue["region"])}" '
        f'data-last-observed="{_esc(issue["last_observed"] or "")}">'
        f'<h3><a href="../issue/{_esc(issue["id"])}/">{_esc(issue["title"])}</a></h3>'
        f'<p>{_esc(issue["summary"])}</p>'
        f'<div class="mx-meta"><span>{_esc(issue["field"])}</span><span>{_esc(issue["region"])}</span>'
        f'<span>최초 관측 {_esc(issue["first_observed"])}</span><span>최근 관측 {_esc(issue["last_observed"])}</span>'
        f'<span>관련 Event {issue["related_event_count"]}건</span>'
        f'<span>Sources {issue["independent_source_count"]}곳</span>{status_html}</div>'
        '</div>'
    )


def render_emerging_issues():
    issues = dd.issue_knowledge_candidates(data_dir=str(op.ROOT / "data"))
    dataset_max = issues[0]["data_period"]["end"] if issues else ""
    if not issues:
        body = (
            '<h2>이슈</h2>'
            '<p class="empty">현재 데이터에서 복수 Event + 복수 Source로 뒷받침되는 Issue가 아직 확인되지 '
            '않았습니다 (정직한 결과이며, 예시를 넣지 않습니다). 개별 중요 사건은 '
            f'<a href="../overview/">오늘</a>의 \'오늘의 주요 정보\'에서 볼 수 있습니다.</p>'
        )
    else:
        fields_present = sorted({i["field"] for i in issues})
        regions_present = sorted({i["region"] for i in issues})
        cards = "".join(_issue_card_summary_html(i) for i in issues)
        body = (
            f'<p class="empty">지금 AI 세계에서 진행 중인 변화 {len(issues)}건 '
            f'(데이터 범위 {_esc(issues[0]["data_period"]["start"])} ~ {_esc(dataset_max)})</p>'
            '<h2>이슈</h2>'
            '<div class="mx-filters">'
            f'{_mx_select("mx-if-field", "분야", fields_present, "분야 전체", onchange="mxIssueFilter()")}'
            f'{_mx_select("mx-if-region", "지역", regions_present, "지역 전체", onchange="mxIssueFilter()")}'
            '<select id="mx-if-period" onchange="mxIssueFilter()" aria-label="기간">'
            '<option value="0">기간 전체</option><option value="7">최근 7일</option>'
            '<option value="30">최근 30일</option></select>'
            '</div>'
            f'<div id="mx-issue-list">{cards}</div>'
            f'{_ISSUE_FILTER_JS}'
        )
    return _shell(f"{_ko('emerging_issues')} / Issues", "emerging_issues", (
        f'<style>{_MX_FILTER_CSS}</style>{body}'
    ), extra_body_attrs=f' data-dataset-max="{_esc(dataset_max)}"')


def _issue_timeline_html(events):
    rows = []
    for ev in events:
        summary = _esc(ev.get("summary") or "")
        rows.append(
            '<div class="mx-item">'
            f'<div class="mx-meta"><span class="mono">{_esc(str(ev["date"])[:10])}</span>'
            f'<span>{_esc(ev["source"])}</span></div>'
            f'<h3>{_safe_link(ev["url"], ev["title_ko"])}</h3>'
            + (f'<p>{summary}</p>' if summary else '')
            + '</div>'
        )
    return "".join(rows)


def render_issue_detail(issue):
    status = issue.get("status")
    status_line = (
        f'<p><b>상태</b>: {_esc(_ISSUE_STATUS_KO.get(status, status))} '
        '<span class="empty">(실제 Event 발생 시점 기준 추정, 데이터로 판단 가능한 경우에만 표시)</span></p>'
        if status else ''
    )
    watch = _FIELD_WATCHPOINTS.get(issue["field"], ())
    watch_html = "".join(f"<li>{_esc(w)}</li>" for w in watch) if watch else '<li class="empty">분야별 기본 관찰 항목 없음</li>'
    sources_html = "".join(
        f'<li>{_esc(s["institution"])}: {_safe_link(s["url"])}</li>' for s in issue["sources"]
    )
    first_ev, last_ev = issue["events"][0], issue["events"][-1]
    whats_changing = (
        f'<p><b>기존</b>: {_esc(first_ev["title_ko"])} ({_esc(str(first_ev["date"])[:10])} 최초 관측)</p>'
        f'<p><b>현재 관측</b>: 이후 {issue["related_event_count"] - 1}건의 관련 사건이 이어졌으며, '
        f'가장 최근은 {_esc(last_ev["title_ko"])} ({_esc(str(last_ev["date"])[:10])})입니다.</p>'
        f'<p><b>해석</b>: 독립 출처 {issue["independent_source_count"]}곳에서 관련 사건이 반복 확인되고 있어, '
        f'{_esc(issue["field"])} 분야에서 \'{_esc(issue["matched_keyword"])}\' 관련 변화가 '
        f'{_esc(_ISSUE_STATUS_KO.get(status, "지속"))} 추세로 관찰됩니다.</p>'
    )
    body = (
        f'<p class="empty"><a href="../../emerging_issues/">&larr; 이슈 목록으로</a></p>'
        f'<h2>{_esc(issue["title"])}</h2>'
        f'<p>{_esc(issue["summary"])}</p>'
        f'{status_line}'
        '<h3>현재 상황</h3>' + whats_changing +
        '<h3>왜 중요한가</h3>'
        f'<p>{_esc(issue["field"])} 분야에서 서로 다른 날짜·독립 출처 {issue["independent_source_count"]}곳을 통해 '
        f'\'{_esc(issue["matched_keyword"])}\' 관련 사건이 반복적으로 확인되고 있어, 일회성 보도가 아닌 '
        '지속적인 변화 신호로 판단됩니다.</p>'
        '<h3>Timeline</h3>' + f'<div class="kpi-row" style="flex-direction:column">{_issue_timeline_html(issue["events"])}</div>'
        '<h3>Supporting Evidence</h3>'
        f'<div class="empty">Sources {len(issue["sources"])}<ul>{sources_html}</ul></div>'
        '<h3>반대 신호 / 불확실성</h3>'
        '<p class="empty">현재 데이터 기준으로 확인된 명시적 반대 신호는 없습니다. 반대 방향의 실제 자료가 '
        '확인되면 이 영역에 추가됩니다 (근거 없이 만들어내지 않습니다).</p>'
        '<h3>앞으로 볼 것</h3>'
        f'<ul>{watch_html}</ul>'
    )
    return _shell(f"이슈 / {issue['title'][:40]}", "emerging_issues", body, depth=2)


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

        # Issue Knowledge Layer detail pages -- one per real, qualifying Issue (never a
        # hardcoded/sample set). Stable id (keyed on the earliest member event) means the same
        # Issue keeps the same URL as new Events accumulate into it over time.
        issues = dd.issue_knowledge_candidates(data_dir=str(op.ROOT / "data"))
        for issue in issues:
            try:
                i_dir = operator_dir / "issue" / issue["id"]
                i_dir.mkdir(parents=True, exist_ok=True)
                res = apub.atomic_write(i_dir / "index.html", render_issue_detail(issue),
                                         validator=apub.html_validator)
                if res["status"] != "PUBLISHED":
                    raise RuntimeError(res["error"])
                status["pages_written"].append(f"issue/{issue['id']}")
            except Exception as e:  # noqa: BLE001
                status["errors"].append({"page": f"issue/{issue['id']}", "error": str(e)})
    except Exception as e:  # noqa: BLE001
        status["errors"].append({"page": None, "error": str(e)})
    return status


if __name__ == "__main__":
    site_dir = sys.argv[1] if len(sys.argv) > 1 else str(op.ROOT / "site")
    result = build_operator_pages(site_dir)
    print(json.dumps(result, ensure_ascii=False))
