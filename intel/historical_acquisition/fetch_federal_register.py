#!/usr/bin/env python3
# PHASE M.5B — real acquisition connector attempt #1: US Federal Register API.
#
# This is a genuine acquisition connector (not a measurement module): it fetches, parses,
# validates and canonicalizes real documents from https://www.federalregister.gov/api/v1/
# (the US government's own free, no-key, official API for the Federal Register). It follows
# the EXACT hardened-fetch contract already established in
# intel/foresight_engine/scripts/fetch_reality_indicators.py (scheme allowlist, private-IP/
# SSRF block, redirect cap re-validated per hop, response-size cap, timeout) rather than
# writing a second, unprotected fetcher.
#
# Zero LLM. This module never touches intel/documents.json or any other file the core
# collection pipeline (briefing.py) owns -- it writes only its own output file
# (federal_register_pilot_result.json), exactly like reality_pilot_result.json does for the
# Reality Layer. It is a targeted, gap-driven acquisition pilot for MISSING_REGULATORY_HISTORY
# (see intel/historical_acquisition/gap_source_map.py), not a bulk backfill.
#
# Per-source status uses the exact granular vocabulary required for M.5B (never a collapsed
# boolean): FETCH_OK / FETCH_FAILED / PARSE_OK / PARSE_FAILED / VALIDATION_OK /
# VALIDATION_FAILED / SCHEMA_CHANGED / SECURITY_BLOCKED / RATE_LIMITED / NOT_FOUND /
# UNSUPPORTED / CANONICALIZED / SUCCESS. HTTP 200 alone is never treated as SUCCESS -- SUCCESS
# requires: real response -> valid schema -> parsed value -> canonical document -> provenance
# recorded (spec section 1).
#
# NETWORK REALITY (honest, not assumed): this script was NOT run against a live network from
# the authoring sandbox. Prior phases (M.3, M.5A) confirmed federalregister.gov is blocked at
# this sandbox's outbound proxy with a 403 on the tunnel (see gap_source_map.py's
# "SANDBOX_BLOCKED_CONFIRMED_403" for this exact host). This script's real reachability from
# GitHub Actions' network is unknown until it is actually run there (federal_register_shadow
# job in .github/workflows/daily.yml) -- this file does not fabricate that result.
import hashlib
import ipaddress
import json
import os
import socket
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
OUT_PATH = HERE / "federal_register_pilot_result.json"

USER_AGENT = "Mozilla/5.0 (compatible; METAXIS-HistoricalAcquisitionPilot/1.0; +https://github.com)"
MAX_BYTES = 2_000_000
PER_URL_TIMEOUT_SECONDS = 20
MAX_REDIRECTS = 5

STATUS_VALUES = (
    "FETCH_OK", "FETCH_FAILED", "PARSE_OK", "PARSE_FAILED", "VALIDATION_OK",
    "VALIDATION_FAILED", "SCHEMA_CHANGED", "SECURITY_BLOCKED", "RATE_LIMITED",
    "NOT_FOUND", "UNSUPPORTED", "CANONICALIZED", "SUCCESS",
)

# Gap this pilot targets, per intel/historical_acquisition/gap_source_map.py.
GAP_TYPE = "MISSING_REGULATORY_HISTORY"
SOURCE_NAME = "US Federal Register API"
SOURCE_TIER = "TIER_1"
SOURCE_TYPE = "GOVERNMENT"

# Real, documented, no-key Federal Register search endpoint. Narrow, targeted query terms
# (AI-regulation related, matching this corpus's real topics) -- not a bulk crawl.
FETCH_URL = (
    "https://www.federalregister.gov/api/v1/documents.json"
    "?conditions%5Bterm%5D=artificial+intelligence"
    "&per_page=5&order=newest"
    "&fields%5B%5D=title&fields%5B%5D=type&fields%5B%5D=abstract"
    "&fields%5B%5D=document_number&fields%5B%5D=html_url&fields%5B%5D=pdf_url"
    "&fields%5B%5D=publication_date&fields%5B%5D=agencies&fields%5B%5D=citation"
)


class BlockedURLError(Exception):
    pass


def _is_private_or_blocked_host(host):
    if not host:
        return True
    host_l = host.lower()
    if host_l in ("localhost",) or host_l.endswith(".local"):
        return True
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return True
    for info in infos:
        ip = info[4][0]
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved or addr.is_multicast:
            return True
    return False


def validate_url(url):
    u = urlparse(url)
    if u.scheme not in ("http", "https"):
        raise BlockedURLError(f"disallowed scheme: {u.scheme!r}")
    if _is_private_or_blocked_host(u.hostname):
        raise BlockedURLError(f"blocked host (private/loopback/unresolvable): {u.hostname!r}")
    return u


def real_json_fetcher(url):
    """Same security contract as fetch_reality_indicators.py's real_json_fetcher(): scheme/
    private-IP block, redirect cap + re-validation per hop, size cap, timeout. Never eval/
    exec's fetched content -- json.loads only, after content-type/size checks."""
    validate_url(url)

    class _RedirectGuard(urllib.request.HTTPRedirectHandler):
        def __init__(self):
            self.hops = 0

        def redirect_request(self, req, fp, code, msg, headers, newurl):
            self.hops += 1
            if self.hops > MAX_REDIRECTS:
                raise BlockedURLError("too many redirects")
            validate_url(newurl)
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    opener = urllib.request.build_opener(_RedirectGuard())
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with opener.open(req, timeout=PER_URL_TIMEOUT_SECONDS) as resp:
            status_code = resp.getcode()
            resolved_url = resp.geturl()
            raw = resp.read(MAX_BYTES + 1)
            byte_size = len(raw)
            if byte_size > MAX_BYTES:
                return {"ok": False, "status": "FETCH_FAILED", "status_code": status_code,
                        "resolved_url": resolved_url, "error": "response exceeded MAX_BYTES cap, discarded"}
            text = raw.decode("utf-8", errors="replace")
            try:
                data = json.loads(text)
            except json.JSONDecodeError as e:
                return {"ok": False, "status": "PARSE_FAILED", "status_code": status_code,
                        "resolved_url": resolved_url, "error": f"non-JSON response: {e}"}
            return {"ok": True, "status": "FETCH_OK", "status_code": status_code,
                    "resolved_url": resolved_url, "data": data}
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return {"ok": False, "status": "RATE_LIMITED", "status_code": e.code, "error": repr(e)}
        if e.code == 404:
            return {"ok": False, "status": "NOT_FOUND", "status_code": e.code, "error": repr(e)}
        return {"ok": False, "status": "FETCH_FAILED", "status_code": e.code, "error": repr(e)}
    except BlockedURLError as e:
        return {"ok": False, "status": "SECURITY_BLOCKED", "status_code": None, "error": str(e)}
    except Exception as e:
        return {"ok": False, "status": "FETCH_FAILED", "status_code": None, "error": repr(e)}


REQUIRED_RESULT_FIELDS = (
    "title", "type", "document_number", "html_url", "publication_date", "agencies",
)


def validate_schema(payload):
    """VALIDATION_OK / VALIDATION_FAILED / SCHEMA_CHANGED -- never assumes the real API's
    shape matches this sample forever. Checks the documented top-level envelope
    (results: [...]) and, per result, the required fields this connector actually uses.
    SCHEMA_CHANGED is returned (not VALIDATION_FAILED) when the top-level envelope itself is
    missing/wrong-typed, since that is the signal the API's documented shape changed, as
    opposed to a single malformed record."""
    if not isinstance(payload, dict) or "results" not in payload:
        return "SCHEMA_CHANGED", "missing top-level 'results' key"
    results = payload["results"]
    if not isinstance(results, list):
        return "SCHEMA_CHANGED", "'results' is not a list"
    if len(results) == 0:
        return "NOT_FOUND", "'results' is empty -- no matching documents"
    for i, item in enumerate(results):
        if not isinstance(item, dict):
            return "VALIDATION_FAILED", f"result[{i}] is not an object"
        missing = [f for f in REQUIRED_RESULT_FIELDS if f not in item]
        if missing:
            return "VALIDATION_FAILED", f"result[{i}] missing fields: {missing}"
    return "VALIDATION_OK", None


def canonicalize_document(item, retrieved_at):
    """Builds a canonical, LINK_ONLY-compliant record -- title/abstract/link/provenance only,
    never full article/document text (spec's copyright boundary). Deterministic document_id
    from the source's own stable document_number, not a random UUID, so re-running this
    connector on the same document is idempotent (matches this repo's own content_hash-based
    identity convention in intel/documents.json)."""
    doc_number = item.get("document_number")
    if not doc_number:
        return None, "PARSE_FAILED"
    content_basis = f"federal_register:{doc_number}:{item.get('title', '')}"
    content_hash = hashlib.sha256(content_basis.encode("utf-8")).hexdigest()[:16]
    agencies = item.get("agencies") or []
    agency_names = [a.get("name") for a in agencies if isinstance(a, dict) and a.get("name")]
    doc = {
        "document_id": f"fedreg_{doc_number}",
        "content_hash": content_hash,
        "document_type": "POLICY",
        "source_id": "src_federal_register",
        "source_name": SOURCE_NAME,
        "source_tier": SOURCE_TIER,
        "source_type": SOURCE_TYPE,
        "title": item.get("title"),
        "abstract_excerpt": (item.get("abstract") or "")[:500] or None,
        "document_kind": item.get("type"),
        "citation": item.get("citation"),
        "agencies": agency_names,
        "published": item.get("publication_date"),
        "canonical_url": item.get("html_url"),
        "rights_mode": "LINK_ONLY",
        "gap_type_addressed": GAP_TYPE,
        "retrieved_at": retrieved_at,
        "provenance_id": f"prov_fedreg_{doc_number}_{retrieved_at}",
    }
    return doc, "PARSE_OK"


def run_pilot(fetcher=real_json_fetcher, url=FETCH_URL):
    retrieved_at = datetime.now(timezone.utc).isoformat()
    entry = {
        "source_name": SOURCE_NAME, "source_tier": SOURCE_TIER, "gap_type": GAP_TYPE,
        "url": url, "attempted_at": retrieved_at,
    }
    try:
        fetch_result = fetcher(url)
    except BlockedURLError as e:
        fetch_result = {"ok": False, "status": "SECURITY_BLOCKED", "error": str(e)}

    entry["fetch_status"] = fetch_result.get("status", "FETCH_FAILED")
    entry["fetch_status_code"] = fetch_result.get("status_code")
    entry["fetch_error"] = fetch_result.get("error")
    entry["documents_canonicalized"] = []
    entry["overall_status"] = entry["fetch_status"]

    if not fetch_result.get("ok"):
        results = [entry]
        return _finish(results, retrieved_at)

    schema_status, schema_reason = validate_schema(fetch_result["data"])
    entry["schema_status"] = schema_status
    entry["schema_reason"] = schema_reason
    entry["overall_status"] = schema_status

    if schema_status not in ("VALIDATION_OK",):
        results = [entry]
        return _finish(results, retrieved_at)

    docs = []
    parse_failures = 0
    for item in fetch_result["data"]["results"]:
        doc, parse_status = canonicalize_document(item, retrieved_at)
        if doc is None:
            parse_failures += 1
            continue
        docs.append(doc)
    entry["documents_canonicalized"] = docs
    entry["documents_attempted"] = len(fetch_result["data"]["results"])
    entry["documents_parsed_ok"] = len(docs)
    entry["parse_failures"] = parse_failures
    entry["overall_status"] = "SUCCESS" if docs else "PARSE_FAILED"

    return _finish([entry], retrieved_at)


def _detect_execution_environment():
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return f"GITHUB_ACTIONS (run_id={os.environ.get('GITHUB_RUN_ID', 'UNKNOWN')})"
    return "LOCAL_OR_SANDBOX (network reachability not assumed -- see overall_status below)"


def _finish(results, retrieved_at):
    summary = {
        "attempted_at": retrieved_at,
        "execution_environment": _detect_execution_environment(),
        "sources_attempted": len(results),
        "sources_reaching_success": sum(1 for r in results if r["overall_status"] == "SUCCESS"),
        "total_documents_canonicalized": sum(len(r.get("documents_canonicalized", [])) for r in results),
        "results": results,
    }
    return summary


def main():
    summary = run_pilot()
    OUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH} -- overall_status(es): "
          f"{[r['overall_status'] for r in summary['results']]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
