#!/usr/bin/env python3
# PHASE M.3 — real Korea + international official-source indicator fetch pilot.
#
# This script was NOT successfully run against a live network in the authoring sandbox: real
# HTTPS requests to World Bank, KOSIS, ECOS and OECD SDMX were attempted directly (urllib, no
# wrapper) from that sandbox and all four failed identically at the outbound proxy with
# "Tunnel connection failed: 403 Forbidden" - confirmed independently in this session, not
# assumed from a prior session's report. This matches intel/source_intelligence/scripts/
# fetch_pilot.py's own documented finding (pypi.org reachable, other external hosts blocked).
#
# This module reuses that pilot's hardened fetcher CONTRACT (scheme/private-IP/redirect/size/
# timeout protections) rather than building a second, unprotected one - see _validate_url()/
# real_json_fetcher() below, a JSON-response adaptation of fetch_pilot.py's real_fetcher()
# (same security checks, different Content-Type acceptance since these are JSON APIs, not
# HTML pages).
#
# It is wired into .github/workflows/daily.yml as an isolated, non-blocking shadow job
# (reality_shadow) that will actually run against GitHub Actions' real network on the next
# cron tick. Its result there is the first REAL confirmation of whether these no-key public
# endpoints are reachable from this project's automation - this script does not fabricate
# that result here.
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
FORESIGHT_DIR = HERE.parent
sys.path.insert(0, str(FORESIGHT_DIR))

from reality_indicator import new_indicator, new_observation, ObservationRejected  # noqa: E402

USER_AGENT = "Mozilla/5.0 (compatible; METAXIS-RealityIndicatorPilot/1.0; +https://github.com)"
MAX_BYTES = 2_000_000
PER_URL_TIMEOUT_SECONDS = 20
MAX_REDIRECTS = 5

OUT_PATH = FORESIGHT_DIR / "reality_pilot_result.json"


class _BlockedURLError(Exception):
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


def _validate_url(url):
    u = urlparse(url)
    if u.scheme not in ("http", "https"):
        raise _BlockedURLError(f"disallowed scheme: {u.scheme!r}")
    if _is_private_or_blocked_host(u.hostname):
        raise _BlockedURLError(f"blocked host (private/loopback/unresolvable): {u.hostname!r}")
    return u


def real_json_fetcher(url):
    """Same security contract as fetch_pilot.py's real_fetcher(), adapted for JSON APIs:
    scheme/private-IP block, redirect cap + re-validation per hop, size cap, timeout. Never
    eval/exec's fetched content - json.loads only, and only after content-type/size checks."""
    _validate_url(url)

    class _RedirectGuard(urllib.request.HTTPRedirectHandler):
        def __init__(self):
            self.hops = 0

        def redirect_request(self, req, fp, code, msg, headers, newurl):
            self.hops += 1
            if self.hops > MAX_REDIRECTS:
                raise _BlockedURLError("too many redirects")
            _validate_url(newurl)
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    opener = urllib.request.build_opener(_RedirectGuard())
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with opener.open(req, timeout=PER_URL_TIMEOUT_SECONDS) as resp:
            status_code = resp.getcode()
            resolved_url = resp.geturl()
            raw = resp.read(MAX_BYTES + 1)
            byte_size = len(raw)
            if byte_size > MAX_BYTES:
                return {"ok": False, "status_code": status_code, "resolved_url": resolved_url,
                        "error": "response exceeded MAX_BYTES cap, discarded"}
            text = raw.decode("utf-8", errors="replace")
            try:
                data = json.loads(text)
            except json.JSONDecodeError as e:
                return {"ok": False, "status_code": status_code, "resolved_url": resolved_url,
                        "error": f"non-JSON response: {e}"}
            return {"ok": True, "status_code": status_code, "resolved_url": resolved_url, "data": data}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status_code": e.code, "error": repr(e)}
    except _BlockedURLError:
        raise
    except Exception as e:
        return {"ok": False, "status_code": None, "error": repr(e)}


# ---------------------------------------------------------------------------
# Source matrix: at least one Korean official source (KOSIS/ECOS, no-key sample endpoint) and
# one international official source (World Bank - historically the most open, no-auth API).
# ---------------------------------------------------------------------------
SOURCES = [
    {
        "source_id": "worldbank_gdp_kr",
        "organization": "World Bank",
        "country": "KOR",
        # World Bank's own documented no-auth sample endpoint for GDP current US$.
        "url": "https://api.worldbank.org/v2/country/kr/indicator/NY.GDP.MKTP.CD?format=json&per_page=5",
        "indicator_id": "ind_worldbank_kr_gdp_current_usd",
        "canonical_name": "KR_GDP_CURRENT_USD",
        "display_name": "Korea GDP (current US$)",
        "domain": "ECONOMY",
        "unit": "USD",
        "frequency": "ANNUAL",
        "geography": "COUNTRY",
        "source_tier": "TIER_1",
        "dataset_name": "World Development Indicators: NY.GDP.MKTP.CD",
        "canonical_url": "https://data.worldbank.org/indicator/NY.GDP.MKTP.CD?locations=KR",
        "license": "CC-BY-4.0",
    },
    {
        "source_id": "ecos_bok_sample",
        "organization": "Bank of Korea (ECOS)",
        "country": "KOR",
        # ECOS's own documented public sample endpoint (no key required for the /sample/ path).
        "url": "https://ecos.bok.or.kr/api/StatisticSearch/sample/json/kr/1/5/722Y001",
        "indicator_id": "ind_ecos_kr_base_rate",
        "canonical_name": "KR_BOK_BASE_RATE",
        "display_name": "Korea BOK Base Rate",
        "domain": "ECONOMY",
        "unit": "PERCENT",
        "frequency": "IRREGULAR",
        "geography": "COUNTRY",
        "source_tier": "TIER_1",
        "dataset_name": "ECOS 722Y001 (Bank of Korea Base Rate)",
        "canonical_url": "https://ecos.bok.or.kr/",
        "license": "KOGL-1",
    },
]


def run_pilot():
    retrieved_at = datetime.now(timezone.utc).isoformat()
    results = []
    for src in SOURCES:
        entry = {"source_id": src["source_id"], "organization": src["organization"],
                  "url": src["url"], "attempted_at": retrieved_at}
        indicator = new_indicator(
            src["indicator_id"], src["canonical_name"], src["display_name"], src["domain"],
            src["source_id"], src["source_tier"], src["organization"], src["unit"],
            src["frequency"], src["geography"], dataset_name=src["dataset_name"],
            canonical_url=src["canonical_url"], license=src["license"],
            retrieved_at=retrieved_at, verification_status="UNKNOWN",
        )
        entry["indicator"] = indicator
        try:
            fetch_result = real_json_fetcher(src["url"])
        except _BlockedURLError as e:
            fetch_result = {"ok": False, "error": f"BLOCKED_BY_SECURITY_POLICY: {e}"}
        entry["fetch_result"] = {k: v for k, v in fetch_result.items() if k != "data"}
        entry["fetch_succeeded"] = bool(fetch_result.get("ok"))

        if fetch_result.get("ok"):
            # Real parsing would go here (deterministic, source-specific schema mapping) - not
            # fabricated in this report since the sandbox never actually reached this branch.
            entry["observation_created"] = "PARSING_NOT_YET_EXERCISED_LIVE"
        else:
            entry["observation_created"] = None
            try:
                new_observation("obs_never_created", src["indicator_id"], "N/A", None,
                                 src["unit"], "OFFICIAL_REPORTED", retrieved_at)
            except ObservationRejected as e:
                entry["observation_rejection_demo"] = str(e)  # proves the reject path works
        results.append(entry)

    summary = {
        "attempted_at": retrieved_at,
        "sandbox_network_status": "BLOCKED - confirmed by direct HTTPS attempt in this session "
                                   "(all sources returned proxy tunnel 403 before reaching host)",
        "sources_attempted": len(results),
        "sources_succeeded": sum(1 for r in results if r["fetch_succeeded"]),
        "results": results,
        "next_real_verification": "GitHub Actions cron run of reality_shadow job in "
                                   ".github/workflows/daily.yml (real network, no sandbox proxy)",
    }
    return summary


if __name__ == "__main__":
    summary = run_pilot()
    OUT_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str),
                         encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, indent=2))
