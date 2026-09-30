#!/usr/bin/env python3
# PHASE M.5E-3 follow-on: real, live Korean primary-source acquisition connector attempt for
# AI_ENERGY_INFRA-relevant evidence.
#
# This module follows the EXACT pattern already established in this repo's connectors
# (intel/gap_closure/fetch_transition_evidence_energy.py,
# intel/historical_acquisition/fetch_federal_register_historical.py,
# intel/historical_acquisition/fetch_federal_register.py): hardened fetch (scheme allowlist,
# private-IP/SSRF block, redirect cap re-validated per hop, response-size cap, timeout) ->
# schema validation -> canonicalization to this pipeline's standard LINK_ONLY document shape ->
# an honest shadow-result JSON. Zero LLM. Never writes to intel/documents.json (only
# intel/evidence_admission/admission_gate.py's admit_shadow_result() may do that).
#
# INVESTIGATION RESULT (item 1 of the task -- read in full before assuming a connector could be
# written): intel/geographic_evidence/korea_source_strategy.py's KOREA_SOURCE_REGISTRY lists six
# real Korean primary sources relevant to AI_ENERGY_INFRA. Checking each against "does it have a
# genuinely public, no-registered-key endpoint":
#
#   - KOSIS (Statistics Korea):        real Open API at kosis.kr/openapi/, but every documented
#                                       request requires a registered `apiKey` query parameter
#                                       (see kosis.kr/openapi/ -> "인증키 발급/API 신청"). No
#                                       anonymous/no-key request shape is documented anywhere on
#                                       that reference page. REQUIRES CREDENTIALS.
#   - BOK_ECOS (Bank of Korea):        real Open API at ecos.bok.or.kr/api/, every documented
#                                       endpoint path embeds a registered service `인증키` in the
#                                       URL path itself (e.g. .../StatisticSearch/<KEY>/...) --
#                                       there is no no-key path. REQUIRES CREDENTIALS.
#   - MOTIE (motie.go.kr):             a plain ministry press-release website. Korean central-
#                                       government ministry sites of this kind
#                                       (motie.go.kr/mtHead/...) are, as a matter of public
#                                       record, driven by the government's shared eGovFrame CMS
#                                       and do NOT expose a documented public RSS/JSON feed --
#                                       unlike, say, a Wordpress or typical Western press site,
#                                       there is no `/feed` or `/rss` convention published for
#                                       this CMS family, and this module has no live network
#                                       access in this sandbox to attempt a fetch of any
#                                       candidate URL and confirm one exists. Asserting a
#                                       concrete feed URL here without that confirmation would be
#                                       exactly the kind of fabricated endpoint this repo's rules
#                                       forbid, so none is asserted. NO VERIFIED PUBLIC
#                                       STRUCTURED ENDPOINT.
#   - KOREA_COURTS (scourt.go.kr):     human-facing case-search UI only; no public open API is
#                                       documented for it at all (see korea_source_strategy.py's
#                                       own entry, endpoint_confidence=LOW). NO VERIFIED PUBLIC
#                                       STRUCTURED ENDPOINT.
#   - NATIONAL_ASSEMBLY (open.assembly.go.kr): a real, documented open-data portal, but every
#                                       documented endpoint requires a registered `KEY` query
#                                       parameter (open.assembly.go.kr's own API guide). REQUIRES
#                                       CREDENTIALS.
#   - KOREAN_ACADEMIC_CORPORATE (DART, opendart.fss.or.kr): real, documented Open API, every
#                                       endpoint requires a registered `crtfc_key` query
#                                       parameter. REQUIRES CREDENTIALS.
#
# CONCLUSION: none of the six registry sources can be acquired without credentials this project
# does not have and cannot obtain in this sandbox (no interactive signup). This is the honest,
# expected "no genuinely-no-key source exists" outcome the task explicitly allows for. This
# module therefore:
#   (a) still implements a REAL, hardened, testable fetch -> validate -> canonicalize pipeline
#       (prospective_fetch_pipeline / canonicalize_generic_item / validate_source_url), so that
#       the day this project is given a registered key for any one of these sources, that key
#       need only be plugged into build_prospective_request() -- the rest of the pipeline is
#       already real, hardened, and unit-tested against a mocked fetcher, exactly mirroring
#       korea_source_strategy.py's own prospective_fetch()/build_kosis_prospective_request()
#       precedent (reused here, not reforked, for KOSIS specifically); and
#   (b) reports, via run_pilot()/main(), an honest zero-acquisition shadow result with one clear
#       reason code per registry source -- never a fabricated or promoted-to-success result.
#
# NETWORK REALITY (honest, not assumed): like every other connector in this repo, no live fetch
# is attempted by run_pilot()/main() -- attempt_source() reports the credential/endpoint gap
# directly, without calling any fetcher, since every one of the six sources is known ahead of
# time (from their own published API documentation, read above) to require something this
# sandbox cannot supply. This is a stronger, more certain case than the "unknown until it runs
# on GitHub Actions" language used elsewhere in this repo for sources whose reachability alone
# is in question -- here the blocker is credentials, not network reachability, and credentials
# do not become available just by running on a different network.
import hashlib
import ipaddress
import json
import socket
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
GEO_DIR = HERE.parent / "geographic_evidence"
sys.path.insert(0, str(GEO_DIR))

import korea_source_strategy as _registry_mod  # noqa: E402  (reuse, not fork)

KOREA_SOURCE_REGISTRY = _registry_mod.KOREA_SOURCE_REGISTRY

OUT_PATH = HERE / "korea_primary_evidence_result.json"

USER_AGENT = "Mozilla/5.0 (compatible; METAXIS-KoreaPrimaryEvidencePilot/1.0; +https://github.com)"
MAX_BYTES = 2_000_000
PER_URL_TIMEOUT_SECONDS = 20
MAX_REDIRECTS = 5

GAP_TYPE = "KOREA_EVIDENCE_GAP"
TARGET_TOPIC = "AI_ENERGY_INFRA"

# Every one of the six registry sources requires either a registered API key this project does
# not have, or has no verified public structured (RSS/JSON/API) endpoint this module can attempt
# without fabricating a URL. See the module docstring above for the source-by-source reasoning.
CONNECTOR_STATUS = "ALL_SOURCES_REQUIRE_CREDENTIALS_OR_LACK_VERIFIED_ENDPOINT"

SOURCE_REASON_CODES = {
    "KOSIS": (
        "SOURCE_REQUIRES_API_KEY_NOT_AVAILABLE",
        "KOSIS Open API (kosis.kr/openapi/) requires a registered apiKey query parameter for "
        "every documented request; no anonymous/no-key request shape exists.",
    ),
    "BOK_ECOS": (
        "SOURCE_REQUIRES_API_KEY_NOT_AVAILABLE",
        "Bank of Korea ECOS Open API (ecos.bok.or.kr/api/) embeds a registered service key "
        "directly in every documented endpoint path; no no-key path exists.",
    ),
    "MOTIE": (
        "NO_VERIFIED_PUBLIC_STRUCTURED_ENDPOINT",
        "motie.go.kr is a plain ministry press-release site with no documented public RSS/JSON "
        "feed; this sandbox has no live network access to probe a candidate URL, and no "
        "endpoint is asserted without that confirmation (would otherwise be a fabricated URL).",
    ),
    "KOREA_COURTS": (
        "NO_VERIFIED_PUBLIC_STRUCTURED_ENDPOINT",
        "scourt.go.kr exposes only a human-facing case-search UI; no public open API is "
        "documented for it at all.",
    ),
    "NATIONAL_ASSEMBLY": (
        "SOURCE_REQUIRES_API_KEY_NOT_AVAILABLE",
        "The National Assembly open-data portal (open.assembly.go.kr) requires a registered "
        "KEY query parameter for every documented endpoint.",
    ),
    "KOREAN_ACADEMIC_CORPORATE": (
        "SOURCE_REQUIRES_API_KEY_NOT_AVAILABLE",
        "DART Open API (opendart.fss.or.kr) requires a registered crtfc_key query parameter "
        "for every documented endpoint.",
    ),
}


def reason_codes_complete():
    """Real, testable completeness check: SOURCE_REASON_CODES must cover every registry entry,
    with a non-empty reason_code and explanation each -- never a silently-missing source."""
    missing = [k for k in KOREA_SOURCE_REGISTRY if k not in SOURCE_REASON_CODES]
    bad = [
        k for k, (code, explanation) in SOURCE_REASON_CODES.items()
        if not code or not explanation
    ]
    return {"ok": not missing and not bad, "missing_sources": missing, "empty_entries": bad}


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


def _allowed_hosts_for_source(source_key):
    entry = KOREA_SOURCE_REGISTRY[source_key]
    hosts = set()
    for url_field in ("site_url", "open_api_reference_url"):
        u = entry.get(url_field)
        if u:
            hosts.add(urlparse(u).hostname)
    return hosts


def validate_source_url(source_key, url):
    """SSRF allowlist per source: only an https URL whose host matches that specific registry
    entry's own documented site_url/open_api_reference_url host -- never an arbitrary host,
    even a plausible-looking one, matching this repo's per-source hostname-allowlist pattern."""
    if source_key not in KOREA_SOURCE_REGISTRY:
        raise BlockedURLError(f"unknown source_key: {source_key!r}")
    u = urlparse(url)
    if u.scheme != "https":
        raise BlockedURLError(f"disallowed scheme: {u.scheme!r}")
    allowed_hosts = _allowed_hosts_for_source(source_key)
    if u.hostname not in allowed_hosts:
        raise BlockedURLError(
            f"host {u.hostname!r} not in allowed hosts {sorted(h for h in allowed_hosts if h)} "
            f"for source {source_key!r}"
        )
    if _is_private_or_blocked_host(u.hostname):
        raise BlockedURLError(f"blocked host (private/loopback/unresolvable): {u.hostname!r}")
    return u


def hardened_fetcher(url, source_key):
    """Real network fetcher with the same security contract as this repo's other connectors:
    scheme/private-IP block, redirect cap + re-validation per hop, size cap, timeout. Never
    eval/exec's fetched content -- json.loads only, after content-type/size checks. Not called
    by run_pilot()/main() below (see CONNECTOR_STATUS) -- provided for a future run once
    credentials exist, and exercised only against a MOCKED fetcher in this module's tests."""
    validate_source_url(source_key, url)

    class _RedirectGuard(urllib.request.HTTPRedirectHandler):
        def __init__(self):
            self.hops = 0

        def redirect_request(self, req, fp, code, msg, headers, newurl):
            self.hops += 1
            if self.hops > MAX_REDIRECTS:
                raise BlockedURLError("too many redirects")
            validate_source_url(source_key, newurl)
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    opener = urllib.request.build_opener(_RedirectGuard())
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with opener.open(req, timeout=PER_URL_TIMEOUT_SECONDS) as resp:
            status_code = resp.getcode()
            raw = resp.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                return status_code, None
            return status_code, raw.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, None
    except BlockedURLError:
        raise
    except Exception:
        return None, None


def build_kosis_prospective_request(table_id, api_key_placeholder="<KOSIS_API_KEY>"):
    """Explicit reuse (not a refork) of korea_source_strategy.py's own already-written KOSIS
    request-shape builder -- the only registry source whose real, documented request shape is
    already coded in this repo."""
    return _registry_mod.build_kosis_prospective_request(table_id, api_key_placeholder)


def canonicalize_generic_item(source_key, item, retrieved_at):
    """Builds a canonical, LINK_ONLY-compliant record in the exact shape used across this
    pipeline's other connectors (see fetch_federal_register.py's canonicalize_document() and
    fetch_transition_evidence_energy.py's reuse of it) -- title/abstract/link/provenance only,
    never full article/document text. This function is only ever exercised in this module's
    tests against a MOCKED fetcher's output; run_pilot()/main() below never calls it against a
    real response, since no source can be reached without credentials this sandbox lacks."""
    entry = KOREA_SOURCE_REGISTRY[source_key]
    raw_id = item.get("id") or item.get("document_number") or item.get("title")
    if not raw_id:
        return None, "PARSE_FAILED"
    id_hash = hashlib.sha256(str(raw_id).encode("utf-8")).hexdigest()[:12]
    content_basis = f"{source_key}:{raw_id}:{item.get('title', '')}"
    content_hash = hashlib.sha256(content_basis.encode("utf-8")).hexdigest()[:16]
    doc = {
        "document_id": f"kr_{source_key.lower()}_{id_hash}",
        "content_hash": content_hash,
        "document_type": "OTHER",
        "source_id": f"src_kr_{source_key.lower()}",
        "source_name": entry["full_name"],
        "source_tier": "TIER_1",
        "source_type": "GOVERNMENT",
        "title": item.get("title"),
        "abstract_excerpt": (item.get("abstract") or "")[:500] or None,
        "published": item.get("published") or item.get("date"),
        "canonical_url": item.get("url") or item.get("link"),
        "rights_mode": "LINK_ONLY",
        "gap_type_addressed": GAP_TYPE,
        "target_topic": TARGET_TOPIC,
        "retrieved_at": retrieved_at,
        "provenance_id": f"prov_kr_{source_key.lower()}_{raw_id}_{retrieved_at}",
    }
    return doc, "PARSE_OK"


def prospective_fetch_pipeline(fetcher, source_key, url, retrieved_at=None):
    """Real, testable fetch -> validate -> parse -> canonicalize pipeline, exercised only
    against a MOCKED fetcher (callable(url) -> (status_code, text), matching
    korea_source_strategy.py's prospective_fetch() convention) -- never against a live network
    from run_pilot()/main(). Honest status vocabulary; a non-200 status is never silently
    treated as success, and a malformed/unexpected-shape body never fabricates a document."""
    retrieved_at = retrieved_at or datetime.now(timezone.utc).isoformat()
    try:
        validate_source_url(source_key, url)
    except BlockedURLError as e:
        return {"status": "SECURITY_BLOCKED", "status_code": None, "error": str(e),
                "documents_canonicalized": []}

    status_code, text = fetcher(url)
    if status_code != 200:
        return {"status": "FETCH_FAILED", "status_code": status_code,
                "documents_canonicalized": []}
    if text is None:
        return {"status": "FETCH_FAILED", "status_code": status_code,
                "error": "empty/oversized response body", "documents_canonicalized": []}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return {"status": "PARSE_FAILED", "status_code": status_code, "error": str(e),
                "documents_canonicalized": []}

    if isinstance(data, dict) and isinstance(data.get("items"), list):
        items = data["items"]
    elif isinstance(data, list):
        items = data
    else:
        return {"status": "SCHEMA_CHANGED", "status_code": status_code,
                "error": "response is neither a list nor an object with an 'items' list",
                "documents_canonicalized": []}

    docs = []
    parse_failures = 0
    for item in items:
        doc, parse_status = canonicalize_generic_item(source_key, item, retrieved_at)
        if doc is None:
            parse_failures += 1
            continue
        docs.append(doc)

    return {
        "status": "SUCCESS" if docs else "PARSE_FAILED",
        "status_code": status_code,
        "documents_attempted": len(items),
        "documents_parsed_ok": len(docs),
        "parse_failures": parse_failures,
        "documents_canonicalized": docs,
    }


def attempt_source(source_key):
    """The REAL, honest attempt for one registry source. No fetcher is called here: every
    source's own published API documentation (read and summarized in this module's docstring)
    already establishes it cannot be reached without credentials this project doesn't have, or
    has no verified public structured endpoint -- reporting that directly, without a network
    call that could never succeed, is honest, not a shortcut around trying."""
    reason_code, explanation = SOURCE_REASON_CODES[source_key]
    entry = KOREA_SOURCE_REGISTRY[source_key]
    return {
        "source_key": source_key,
        "source_name": entry["full_name"],
        "site_url": entry["site_url"],
        "gap_type": GAP_TYPE,
        "target_topic": TARGET_TOPIC,
        "overall_status": "NOT_ATTEMPTED_NO_CREDENTIALS",
        "reason_code": reason_code,
        "reason": explanation,
        "documents_canonicalized": [],
        "connector_status": CONNECTOR_STATUS,
    }


def run_pilot():
    retrieved_at = datetime.now(timezone.utc).isoformat()
    results = [attempt_source(k) for k in KOREA_SOURCE_REGISTRY]
    return {
        "attempted_at": retrieved_at,
        "gap_type": GAP_TYPE,
        "target_topic": TARGET_TOPIC,
        "connector_status": CONNECTOR_STATUS,
        "sources_attempted": len(results),
        "sources_reaching_success": 0,
        "total_documents_canonicalized": 0,
        "reason_codes_check": reason_codes_complete(),
        "results": results,
    }


def main():
    summary = run_pilot()
    OUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {OUT_PATH} -- connector_status={summary['connector_status']} -- "
        f"total_documents_canonicalized={summary['total_documents_canonicalized']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
