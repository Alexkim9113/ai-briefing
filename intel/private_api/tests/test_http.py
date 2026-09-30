# STAGE 7 PHASE L — proves the thin stdlib HTTP wrapper over a real local socket: auth
# (no token -> 401, right token -> 200, wrong token -> 401) and a couple of route mappings.
# No pytest/unittest. The test-only bearer token is set via env var in this test process only
# and is never written to any file.
import json
import os
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import server  # noqa: E402

_TEST_TOKEN = "test-only-token-never-committed-3f8a91"


def _with_server(fn):
    old_token = os.environ.get("METAXIS_OPERATOR_TOKEN")
    os.environ["METAXIS_OPERATOR_TOKEN"] = _TEST_TOKEN
    httpd = server.make_server("127.0.0.1", 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{httpd.server_port}{server.API_PREFIX}"
        fn(base)
    finally:
        httpd.shutdown()
        httpd.server_close()
        if old_token is None:
            os.environ.pop("METAXIS_OPERATOR_TOKEN", None)
        else:
            os.environ["METAXIS_OPERATOR_TOKEN"] = old_token


def _get(url, token=None):
    req = urllib.request.Request(url)
    if token is not None:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def test_no_token_is_rejected_with_401():
    def run(base):
        status, body = _get(f"{base}/health")
        assert status == 401
        assert body["error"]["code"] == "UNAUTHORIZED"
    _with_server(run)


def test_wrong_token_is_rejected_with_401():
    def run(base):
        status, body = _get(f"{base}/health", token="definitely-wrong-token")
        assert status == 401
        assert body["error"]["code"] == "UNAUTHORIZED"
    _with_server(run)


def test_correct_token_is_accepted_with_200():
    def run(base):
        status, body = _get(f"{base}/health", token=_TEST_TOKEN)
        assert status == 200
        assert body["status"] in ("OK", "DEGRADED")
    _with_server(run)


def test_status_route_over_http():
    def run(base):
        status, body = _get(f"{base}/status", token=_TEST_TOKEN)
        assert status == 200
        assert isinstance(body["documents_count"], int)
    _with_server(run)


def test_unknown_route_is_404_without_a_stack_trace():
    def run(base):
        status, body = _get(f"{base}/nope-not-a-route", token=_TEST_TOKEN)
        assert status == 404
        assert "error" in body
        assert "Traceback" not in json.dumps(body)
    _with_server(run)


def test_query_post_route_over_http():
    def run(base):
        req = urllib.request.Request(
            f"{base}/query", data=json.dumps({"question": "AI"}).encode("utf-8"), method="POST")
        req.add_header("Authorization", f"Bearer {_TEST_TOKEN}")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        assert "intent" in body
    _with_server(run)
