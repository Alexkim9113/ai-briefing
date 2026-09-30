#!/usr/bin/env python3
# PHASE M.5D — real acquisition connector: Crossref REST API (api.crossref.org).
#
# Free, no-key, well-documented JSON API for scholarly metadata. This is a NEW connector but
# copies the EXACT hardened-fetch/validation/canonicalization/status-vocabulary pattern from
# intel/historical_acquisition/fetch_federal_register.py: same STATUS_VALUES vocabulary, same
# scheme/private-IP/redirect/size/timeout security contract, same LINK_ONLY discipline (title +
# authors + DOI + short abstract excerpt if present + link -- never full text).
#
# Targets the MISSING_ACADEMIC_EVIDENCE gap (intel/historical_acquisition/gap_source_map.py),
# narrowed to a pilot topic's real query terms -- not a bulk crawl (works.select fields +
# rows=5).
#
# NETWORK REALITY (honest, not assumed): this script was NOT run against a live network from the
# authoring sandbox (api.crossref.org was not reachable; see gap_source_map.py's
# SANDBOX_BLOCKED_CONFIRMED_403 pattern for other hosts in this repo). Its real reachability from
# GitHub Actions is unknown until actually run there -- this file does not fabricate that result.
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
from urllib.parse import urlparse, quote

HERE = Path(__file__).resolve().parent
OUT_PATH = HERE / "crossref_pilot_result.json"

USER_AGENT = "Mozilla/5.0 (compatible; METAXIS-HistoricalAcquisitionPilot/1.0; mailto:metaxis-pilot@example.org)"
MAX_BYTES = 2_000_000
PER_URL_TIMEOUT_SECONDS = 20
MAX_REDIRECTS = 5

# Exact same granular vocabulary as fetch_federal_register.py -- never a collapsed boolean.
STATUS_VALUES = (
    "FETCH_OK", "FETCH_FAILED", "PARSE_OK", "PARSE_FAILED", "VALIDATION_OK",
    "VALIDATION_FAILED", "SCHEMA_CHANGED", "SECURITY_BLOCKED", "RATE_LIMITED",
    "NOT_FOUND", "UNSUPPORTED", "CANONICALIZED", "SUCCESS",
)

GAP_TYPE = "MISSING_ACADEMIC_EVIDENCE"
SOURCE_NAME = "Crossref REST API"
SOURCE_TIER = "TIER_1"
SOURCE_TYPE = "RESEARCH_REPOSITORY"
SOURCE_ID = "src_crossref"

# Narrow, targeted query matching this corpus's real pilot topic ("AI agents" -- see
# intel/temporal_depth field distribution, "에이전트" = "agents", 12 real docs) -- not a bulk crawl.
DEFAULT_QUERY_TERM = "AI agents autonomous systems"
FETCH_URL = (
    "https://api.crossref.org/works"
    f"?query={quote(DEFAULT_QUERY_TERM)}"
    "&rows=5&sort=published&order=desc"
    "&select=title,author,DOI,abstract,published,container-title,URL,type"
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
    """Same security contract as fetch_federal_register.py's real_json_fetcher()."""
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


# Crossref's real, documented envelope: {"status": "ok", "message": {"items": [...]}}.
REQUIRED_ITEM_FIELDS = ("title", "DOI")


def validate_schema(payload):
    """VALIDATION_OK / VALIDATION_FAILED / SCHEMA_CHANGED -- mirrors
    fetch_federal_register.py's validate_schema() exactly in shape and intent, adapted to
    Crossref's real documented top-level envelope (status/message/message.items)."""
    if not isinstance(payload, dict) or "message" not in payload:
        return "SCHEMA_CHANGED", "missing top-level 'message' key"
    message = payload["message"]
    if not isinstance(message, dict) or "items" not in message:
        return "SCHEMA_CHANGED", "'message' missing 'items' key"
    items = message["items"]
    if not isinstance(items, list):
        return "SCHEMA_CHANGED", "'message.items' is not a list"
    if len(items) == 0:
        return "NOT_FOUND", "'message.items' is empty -- no matching works"
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            return "VALIDATION_FAILED", f"item[{i}] is not an object"
        missing = [f for f in REQUIRED_ITEM_FIELDS if f not in item]
        if missing:
            return "VALIDATION_FAILED", f"item[{i}] missing fields: {missing}"
    return "VALIDATION_OK", None


def _extract_title(item):
    t = item.get("title")
    if isinstance(t, list):
        return t[0] if t else None
    return t


def _extract_authors(item):
    authors = item.get("author") or []
    names = []
    for a in authors:
        if not isinstance(a, dict):
            continue
        given = a.get("given", "")
        family = a.get("family", "")
        full = (given + " " + family).strip()
        if full:
            names.append(full)
    return names


def _extract_published_date(item):
    """Crossref gives 'published' as {"date-parts": [[year, month, day]]} -- may be partial
    (year-only). Returns an ISO date string using the parts actually present, zero-padded, or
    None if genuinely absent -- never fabricates a day/month the source did not provide."""
    published = item.get("published") or {}
    parts_list = published.get("date-parts") if isinstance(published, dict) else None
    if not parts_list or not isinstance(parts_list, list) or not parts_list[0]:
        return None
    parts = parts_list[0]
    year = parts[0] if len(parts) > 0 else None
    month = parts[1] if len(parts) > 1 else 1
    day = parts[2] if len(parts) > 2 else 1
    if not year:
        return None
    try:
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    except (ValueError, TypeError):
        return None


def canonicalize_document(item, retrieved_at):
    """Builds a canonical, LINK_ONLY-compliant record from one Crossref work: title + authors +
    DOI + abstract excerpt (if present, truncated) + link -- never full text. Deterministic
    document_id from the work's own stable DOI, not a random UUID (idempotent re-runs)."""
    doi = item.get("DOI")
    title = _extract_title(item)
    if not doi or not title:
        return None, "PARSE_FAILED"
    content_basis = f"crossref:{doi}:{title}"
    content_hash = hashlib.sha256(content_basis.encode("utf-8")).hexdigest()[:16]
    abstract_raw = item.get("abstract") or ""
    # Crossref abstracts are sometimes JATS-XML-tagged; strip tags crudely (no external parser,
    # zero LLM) rather than storing the raw markup or the full text.
    abstract_text = abstract_raw
    for tag in ("<jats:p>", "</jats:p>", "<jats:title>", "</jats:title>"):
        abstract_text = abstract_text.replace(tag, "")
    container = item.get("container-title")
    if isinstance(container, list):
        container = container[0] if container else None
    doc = {
        "document_id": f"crossref_{doi.replace('/', '_')}",
        "content_hash": content_hash,
        "document_type": "RESEARCH",
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "source_tier": SOURCE_TIER,
        "source_type": SOURCE_TYPE,
        "title": title,
        "authors": _extract_authors(item),
        "doi": doi,
        "abstract_excerpt": (abstract_text.strip()[:500] or None) if abstract_text.strip() else None,
        "journal_or_venue": container,
        "work_type": item.get("type"),
        "published": _extract_published_date(item),
        "canonical_url": item.get("URL") or f"https://doi.org/{doi}",
        "rights_mode": "LINK_ONLY",
        "gap_type_addressed": GAP_TYPE,
        "retrieved_at": retrieved_at,
        "provenance_id": f"prov_crossref_{doi.replace('/', '_')}_{retrieved_at}",
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
        return _finish([entry], retrieved_at)

    schema_status, schema_reason = validate_schema(fetch_result["data"])
    entry["schema_status"] = schema_status
    entry["schema_reason"] = schema_reason
    entry["overall_status"] = schema_status

    if schema_status != "VALIDATION_OK":
        return _finish([entry], retrieved_at)

    docs = []
    parse_failures = 0
    for item in fetch_result["data"]["message"]["items"]:
        doc, parse_status = canonicalize_document(item, retrieved_at)
        if doc is None:
            parse_failures += 1
            continue
        docs.append(doc)
    entry["documents_canonicalized"] = docs
    entry["documents_attempted"] = len(fetch_result["data"]["message"]["items"])
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
