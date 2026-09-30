# STAGE 7 PHASE L — thin stdlib-only HTTP wrapper, LOCAL/TEST PROOF ONLY (Te spec section 60:
# "first prove API locally / in test environment" - hosting/deployment is explicitly deferred,
# not decided here). This file is never wired into daily.yml, GitHub Pages, or any other
# deployment; it exists so the service functions in service.py can be proven to work over real
# HTTP with `python3 -m private_api.server` binding 127.0.0.1 on a test port. It uses only
# http.server from the stdlib (matching briefing.py's project-wide "stdlib only" convention) -
# no flask/fastapi/uvicorn anywhere in this repo.
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import service  # noqa: E402
from errors import ApiError  # noqa: E402

API_PREFIX = "/api/private/v1"

_ROUTES_GET = [
    (re.compile(r"^/health$"), lambda m, qs: service.health()),
    (re.compile(r"^/status$"), lambda m, qs: service.status()),
    (re.compile(r"^/search$"), lambda m, qs: service.search(
        q=_first(qs, "q"), type=_first(qs, "type"),
        limit=_first(qs, "limit", 20), offset=_first(qs, "offset", 0))),
    (re.compile(r"^/documents/([^/]+)$"), lambda m, qs: service.get_document(m.group(1))),
    (re.compile(r"^/notes/([^/]+)/related$"), lambda m, qs: service.related_notes(m.group(1))),
    (re.compile(r"^/notes/([^/]+)$"), lambda m, qs: service.get_note(m.group(1))),
    (re.compile(r"^/trace/([^/]+)$"), lambda m, qs: service.trace(m.group(1))),
    (re.compile(r"^/evidence/([^/]+)$"), lambda m, qs: service.evidence(m.group(1))),
    (re.compile(r"^/timeline$"), lambda m, qs: service.timeline(
        q=_first(qs, "q"), date_from=_first(qs, "date_from"), date_to=_first(qs, "date_to"))),
    (re.compile(r"^/export/obsidian/([^/]+)$"),
     lambda m, qs: service.export_obsidian_note(m.group(1))),
    (re.compile(r"^/export/json$"), lambda m, qs: service.export_json(
        note_type=_first(qs, "note_type"),
        note_ids=(qs.get("note_ids")[0].split(",") if qs.get("note_ids") else None),
        limit=_first(qs, "limit", 100))),
    (re.compile(r"^/contradictions$"), lambda m, qs: service.contradictions()),
    (re.compile(r"^/view-revisions$"), lambda m, qs: service.view_revisions(
        status=_first(qs, "status"))),
    # STAGE 7 PHASE M additions.
    (re.compile(r"^/coverage$"), lambda m, qs: service.coverage()),
    (re.compile(r"^/knowledge-gaps$"), lambda m, qs: service.knowledge_gaps()),
    (re.compile(r"^/cross-domain-connections$"), lambda m, qs: service.cross_domain_connections()),
    (re.compile(r"^/historical-analogies$"), lambda m, qs: service.historical_analogies(
        topic=_first(qs, "topic"))),
    (re.compile(r"^/intelligence-package$"), lambda m, qs: service.intelligence_package(
        topic=_first(qs, "topic"))),
]

_ROUTES_POST = [
    (re.compile(r"^/query$"), lambda m, qs, body: service.query(body)),
    (re.compile(r"^/export/obsidian$"), lambda m, qs, body: service.export_obsidian_bulk(
        note_ids=body.get("note_ids"), note_type=body.get("note_type"),
        out_dir=body.get("out_dir"))),
]


def _first(qs, key, default=None):
    values = qs.get(key)
    return values[0] if values else default


def _check_auth(headers):
    """Shared-secret bearer token from METAXIS_OPERATOR_TOKEN (env var only - never
    hardcoded, never a working default). In a real deployment this would be a GitHub
    Actions/hosting secret; this process never commits or logs the token value."""
    expected = os.environ.get("METAXIS_OPERATOR_TOKEN")
    if not expected:
        # No token configured on the server side at all -> nobody can authenticate; refuse
        # rather than silently accepting anything (never a working "default" token).
        return False
    auth = headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return False
    return auth[len("Bearer "):] == expected


class Handler(BaseHTTPRequestHandler):
    server_version = "MetaxisPrivateAPI/1.0"

    def _send_json(self, status_code, payload):
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _dispatch(self, method):
        parsed = urlparse(self.path)
        path = parsed.path
        if not path.startswith(API_PREFIX):
            self._send_json(404, ApiError("NOT_FOUND", "unknown path").to_dict())
            return
        sub_path = path[len(API_PREFIX):] or "/"
        if not _check_auth(self.headers):
            self._send_json(401, ApiError("UNAUTHORIZED", "missing or invalid bearer token").to_dict())
            return

        qs = parse_qs(parsed.query)
        routes = _ROUTES_GET if method == "GET" else _ROUTES_POST
        for pattern, fn in routes:
            m = pattern.match(sub_path)
            if not m:
                continue
            try:
                if method == "GET":
                    result = fn(m, qs)
                else:
                    length = int(self.headers.get("Content-Length") or 0)
                    raw = self.rfile.read(length) if length else b""
                    try:
                        body = json.loads(raw.decode("utf-8")) if raw else {}
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        raise ApiError("INVALID_QUERY", "request body must be valid JSON")
                    result = fn(m, qs, body)
                self._send_json(200, result)
            except ApiError as e:
                self._send_json(e.http_status(), e.to_dict())
            except Exception:
                # Never leak a raw stack trace over HTTP.
                self._send_json(500, {"error": {"code": "DATA_UNAVAILABLE",
                                                 "message": "internal error"}})
            return
        self._send_json(404, ApiError("NOT_FOUND", "no such route").to_dict())

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def log_message(self, format, *args):  # noqa: A002 - stdlib signature
        pass  # keep test output quiet; not a production logging story


def make_server(host="127.0.0.1", port=0):
    return ThreadingHTTPServer((host, port), Handler)


if __name__ == "__main__":
    port = int(os.environ.get("METAXIS_PRIVATE_API_PORT", "8765"))
    httpd = make_server("127.0.0.1", port)
    print(f"METAXIS private API (local/test only) listening on http://127.0.0.1:{httpd.server_port}{API_PREFIX}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
