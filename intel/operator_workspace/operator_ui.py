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
sys.path.insert(0, str(HERE.parent / "report_engine"))
import atomic_publish as apub  # noqa: E402

CSS = """
:root{--ink:#1a1a1a;--sub:#5a5a5a;--line:#dcdcdc;--bg:#ffffff;--warn:#8a5a00;--bad:#b3261e;--ok:#1e5c3a}
html{overflow-x:hidden}
*{box-sizing:border-box}
body{font-family:'Pretendard',-apple-system,sans-serif;color:var(--ink);background:var(--bg);
margin:0;padding:0;line-height:1.6;font-size:15px;overflow-wrap:break-word}
.mono{font-family:'Space Grotesk','Pretendard',monospace;overflow-wrap:anywhere;word-break:break-word}
header{border-bottom:1px solid var(--line);padding:16px 24px}
header h1{font-size:1.1em;margin:0;overflow-wrap:break-word}
nav{display:flex;flex-wrap:wrap;gap:4px;padding:10px 24px;border-bottom:1px solid var(--line);font-size:0.85em}
nav a{color:var(--sub);text-decoration:none;padding:4px 8px;border-radius:3px}
nav a:hover,nav a.active{background:#f2f2f2;color:var(--ink)}
main{max-width:980px;margin:0 auto;padding:24px}
.table-wrap{overflow-x:auto}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:0.92em;min-width:420px}
td,th{border:1px solid var(--line);padding:6px 10px;text-align:left;vertical-align:top}
th{background:#fafafa;font-weight:600}
.status{font-size:0.8em;padding:1px 6px;border-radius:3px;border:1px solid var(--line)}
.status-healthy,.status-ready{border-color:var(--ok);color:var(--ok)}
.status-blocked,.status-not_found,.status-pdf_failed{border-color:var(--bad);color:var(--bad)}
.status-degraded,.status-conditionally_ready,.status-auth_required{border-color:var(--warn);color:var(--warn)}
.status-not_instrumented,.status-unknown,.status-not_available{border-color:var(--sub);color:var(--sub)}
.empty{color:var(--sub);font-style:italic}
.kpi-row{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0}
.kpi{border:1px solid var(--line);border-radius:4px;padding:10px 14px;box-sizing:border-box;
flex:0 0 calc(33.333% - 7px);max-width:calc(33.333% - 7px);min-width:0;overflow-wrap:break-word}
.kpi .n{font-family:'Space Grotesk',monospace;font-size:1.4em}
.kpi .l{color:var(--sub);font-size:0.78em;text-transform:uppercase;overflow-wrap:break-word}
a:focus-visible{outline:2px solid #4b3f8a;outline-offset:2px}
.status{overflow-wrap:break-word;display:inline-block;max-width:100%}
@media (max-width: 480px){
  main{padding:14px}
  header{padding:12px 14px}
  nav{padding:8px 14px}
  .kpi-row{grid-template-columns:repeat(2, 1fr)}
}
"""

NAV_ITEMS = ("overview", "reports", "gaps", "rights", "sources", "source_health")


def _esc(x):
    return _html.escape(str(x)) if x is not None else ""


def _status(value):
    slug = str(value).lower()
    return f'<span class="status status-{_esc(slug)}">{_esc(value)}</span>'


def _nav(active):
    links = "".join(
        f'<a href="../{n}/" class="{"active" if n == active else ""}">{n.upper()}</a>'
        for n in NAV_ITEMS
    )
    return f"<nav aria-label='Operator navigation'>{links}</nav>"


def _shell(title, active, body):
    return (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>Operator -- {_esc(title)}</title><style>{CSS}</style></head><body>"
        "<header><h1>METAXIS Intelligence Workbench (Operator)</h1></header>"
        f"{_nav(active)}<main aria-label='Operator workspace'>{body}</main></body></html>"
    )


PUBLIC_SAFE_BANNER = (
    '<div style="border:1px solid var(--line);background:#fafafa;padding:10px 14px;'
    'margin-bottom:16px;font-size:0.85em">'
    '<strong>METAXIS OPERATOR / PUBLIC-SAFE OPERATIONS VIEW</strong><br>'
    'This workspace is deployed on GitHub Pages and has no login. It holds only '
    'public-safe diagnostics (report/claim/evidence status, known gaps, rights status, '
    'source health, corpus counts, provenance IDs). It never exposes Private Research full '
    'text, operator private notes, or restricted material. See '
    '<code>intel/operator_workspace/operator_boundary_contract.json</code> for the full boundary.'
    '</div>'
)


def render_overview():
    o = op.overview()
    kpis = "".join(
        f'<div class="kpi"><div class="n">{_esc(v)}</div><div class="l">{_esc(k.replace("_", " "))}</div></div>'
        for k, v in o.items() if k != "source_health"
    )
    live = op.live_run_status()
    live_kpis = "".join(
        f'<div class="kpi"><div class="n">{_esc(v)}</div><div class="l">{_esc(k.replace("_", " "))}</div></div>'
        for k, v in live.items() if k not in ("run_id", "head_sha", "completed_at", "environment")
    )
    live_section = (
        f'<h2>Last Live Acquisition</h2>'
        f'<p class="mono">RUN_ID={_esc(live["run_id"])} HEAD_SHA={_esc(live["head_sha"])} '
        f'COMPLETED_AT={_esc(live["completed_at"])} ENVIRONMENT={_esc(live["environment"])}</p>'
        f'<div class="kpi-row">{live_kpis}</div>'
    )
    return _shell("Overview", "overview", (
        f'{PUBLIC_SAFE_BANNER}'
        f'<div class="kpi-row">{kpis}</div>'
        f'<p>Source Health (minimal contract): {_status(o["source_health"])}</p>'
        f'{live_section}'
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
    return _shell("Reports", "reports", table)


def render_gaps():
    rows = op.gap_inspector()
    if not rows:
        return _shell("Gaps", "gaps", '<p class="empty">No known gaps recorded.</p>')
    body_rows = "".join(
        f'<tr><td class="mono">{_esc(g["gap_id"])}</td><td>{_esc(g["topic"])}</td>'
        f'<td>{_esc(g["gap_type"])}</td><td>{_status(g["status"])}</td>'
        f'<td>{_esc(g["description"])}</td><td>{_esc(g["next_possible_action"])}</td></tr>'
        for g in rows
    )
    table = ('<div class="table-wrap">' + f'<table><tr><th>Gap ID</th><th>Topic</th><th>Type</th><th>Status</th>'
            f'<th>Description</th><th>Next Possible Action</th></tr>{body_rows}</table></div>')
    return _shell("Gaps", "gaps", f"<p>{len(rows)} known gap(s) -- none hidden.</p>{table}")


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
    return _shell("Rights", "rights", table)


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
    return _shell("Sources", "sources", (
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

    return _shell("Source Health", "source_health", sandbox_block + live_block)


PAGES = {
    "overview": render_overview, "reports": render_reports, "gaps": render_gaps,
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
    except Exception as e:  # noqa: BLE001
        status["errors"].append({"page": None, "error": str(e)})
    return status


if __name__ == "__main__":
    site_dir = sys.argv[1] if len(sys.argv) > 1 else str(op.ROOT / "site")
    result = build_operator_pages(site_dir)
    print(json.dumps(result, ensure_ascii=False))
