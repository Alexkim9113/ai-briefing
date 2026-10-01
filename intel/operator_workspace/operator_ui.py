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

CSS = """
:root{--ink:#1a1a1a;--sub:#5a5a5a;--line:#dcdcdc;--bg:#ffffff;--warn:#8a5a00;--bad:#b3261e;--ok:#1e5c3a}
*{box-sizing:border-box}
body{font-family:'Pretendard',-apple-system,sans-serif;color:var(--ink);background:var(--bg);
margin:0;padding:0;line-height:1.6;font-size:15px}
.mono{font-family:'Space Grotesk','Pretendard',monospace}
header{border-bottom:1px solid var(--line);padding:16px 24px}
header h1{font-size:1.1em;margin:0}
nav{display:flex;flex-wrap:wrap;gap:4px;padding:10px 24px;border-bottom:1px solid var(--line);font-size:0.85em}
nav a{color:var(--sub);text-decoration:none;padding:4px 8px;border-radius:3px}
nav a:hover,nav a.active{background:#f2f2f2;color:var(--ink)}
main{max-width:980px;margin:0 auto;padding:24px}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:0.92em}
td,th{border:1px solid var(--line);padding:6px 10px;text-align:left;vertical-align:top}
th{background:#fafafa;font-weight:600}
.status{font-size:0.8em;padding:1px 6px;border-radius:3px;border:1px solid var(--line)}
.status-healthy,.status-ready{border-color:var(--ok);color:var(--ok)}
.status-blocked,.status-not_found,.status-pdf_failed{border-color:var(--bad);color:var(--bad)}
.status-degraded,.status-conditionally_ready,.status-auth_required{border-color:var(--warn);color:var(--warn)}
.status-not_instrumented,.status-unknown,.status-not_available{border-color:var(--sub);color:var(--sub)}
.empty{color:var(--sub);font-style:italic}
.kpi-row{display:flex;flex-wrap:wrap;gap:12px;margin:16px 0}
.kpi{border:1px solid var(--line);border-radius:4px;padding:10px 14px;min-width:120px}
.kpi .n{font-family:'Space Grotesk',monospace;font-size:1.4em}
.kpi .l{color:var(--sub);font-size:0.78em;text-transform:uppercase}
a:focus-visible{outline:2px solid #4b3f8a;outline-offset:2px}
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


def render_overview():
    o = op.overview()
    kpis = "".join(
        f'<div class="kpi"><div class="n">{_esc(v)}</div><div class="l">{_esc(k.replace("_", " "))}</div></div>'
        for k, v in o.items() if k != "source_health"
    )
    return _shell("Overview", "overview", (
        f'<div class="kpi-row">{kpis}</div>'
        f'<p>Source Health (minimal contract): {_status(o["source_health"])}</p>'
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
    table = (f'<table><tr><th>Report</th><th>Topic</th><th>Version</th><th>Readiness</th>'
            f'<th>Generated</th><th>HTML</th><th>PDF</th></tr>{body_rows}</table>')
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
    table = (f'<table><tr><th>Gap ID</th><th>Topic</th><th>Type</th><th>Status</th>'
            f'<th>Description</th><th>Next Possible Action</th></tr>{body_rows}</table>')
    return _shell("Gaps", "gaps", f"<p>{len(rows)} known gap(s) -- none hidden.</p>{table}")


def render_rights():
    rows = op.rights_inspector()
    body_rows = "".join(
        f'<tr><td class="mono">{_esc(r["source"])[:60]}</td><td>{_status(r["rights_status"])}</td>'
        f'<td>{_status(r["access_status"])}</td><td>{_esc(r["public_allowed"])}</td>'
        f'<td>{_esc(r["fulltext_allowed"])}</td><td>{_esc(r["private_only"])}</td></tr>'
        for r in rows
    )
    table = (f'<table><tr><th>Source</th><th>Rights</th><th>Access</th>'
            f'<th>Public Allowed</th><th>Fulltext Allowed</th><th>Private Only</th></tr>{body_rows}</table>')
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
    table = f'<table><tr><th>Source ID</th><th>Name</th><th>Type</th><th>Health</th></tr>{body_rows}</table>'
    return _shell("Sources", "sources", (
        f'<p>{len(rows)} registered sources.</p><div class="kpi-row">{kpis}</div>'
        f'<p>Showing first {len(sample)} (see index.json for the full registry).</p>{table}'
    ))


def render_source_health():
    summary = op.source_health_pilot_summary()
    if not summary["pilot_run"]:
        return _shell("Source Health", "source_health",
                      '<p class="empty">No Source Health pilot has been run yet (NOT_INSTRUMENTED).</p>')
    kpis = "".join(
        f'<div class="kpi"><div class="n">{_esc(v)}</div><div class="l">{_esc(k)}</div></div>'
        for k, v in summary["counts"].items()
    )
    body_rows = "".join(
        f'<tr><td class="mono">{_esc(s["source_id"])}</td><td>{_status(s["status"])}</td>'
        f'<td>{_esc(s["last_checked"])}</td><td>{_esc(s["is_stale"])}</td>'
        f'<td>{_esc(s["known_limitation"])}</td></tr>'
        for s in summary["sources"]
    )
    table = (f'<table><tr><th>Source</th><th>Status</th><th>Last Checked</th>'
            f'<th>Stale?</th><th>Known Limitation</th></tr>{body_rows}</table>')
    return _shell("Source Health", "source_health", (
        f'<p>Last pilot run: {_esc(summary["checked_at"])}</p>'
        f'<div class="kpi-row">{kpis}</div>{table}'
    ))


PAGES = {
    "overview": render_overview, "reports": render_reports, "gaps": render_gaps,
    "rights": render_rights, "sources": render_sources, "source_health": render_source_health,
}


def build_operator_pages(site_dir):
    """Writes site/operator/{page}/index.html for each page. Never raises -- Failure Isolation
    applies here too: one page's error is recorded, the others still build."""
    operator_dir = Path(site_dir) / "operator"
    status = {"pages_written": [], "errors": []}
    try:
        operator_dir.mkdir(parents=True, exist_ok=True)
        for name, renderer in PAGES.items():
            try:
                page_dir = operator_dir / name
                page_dir.mkdir(parents=True, exist_ok=True)
                (page_dir / "index.html").write_text(renderer(), encoding="utf-8")
                status["pages_written"].append(name)
            except Exception as e:  # noqa: BLE001
                status["errors"].append({"page": name, "error": str(e)})
        (operator_dir / "index.html").write_text(render_overview(), encoding="utf-8")
        (operator_dir / "sources_full.json").write_text(
            json.dumps(op.source_inspector(), ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        status["errors"].append({"page": None, "error": str(e)})
    return status


if __name__ == "__main__":
    site_dir = sys.argv[1] if len(sys.argv) > 1 else str(op.ROOT / "site")
    result = build_operator_pages(site_dir)
    print(json.dumps(result, ensure_ascii=False))
