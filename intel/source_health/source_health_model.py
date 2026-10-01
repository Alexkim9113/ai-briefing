# N-5 Section 20-29 -- Source Health minimal contract. No new monitoring platform: a small,
# honest, stdlib-only check against a Tier-1 subset of real registered sources (the ones this
# corpus's actual Intelligence Objects depend on, plus the historically-attempted candidates
# already named in intel/statistical_context/, intel/historical_acquisition/ and
# intel/historical_evidence/). Reuses the existing CircuitBreaker/retry_with_backoff from
# acquisition_queue/queue_model.py rather than building a new retry framework.
import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RESULT_PATH = HERE / "source_health_result.json"

sys.path.insert(0, str(ROOT / "intel" / "acquisition_queue"))
import queue_model as qm  # noqa: E402

SOURCE_HEALTH_STATES = ("HEALTHY", "DEGRADED", "BLOCKED", "AUTH_REQUIRED", "NOT_FOUND", "UNKNOWN",
                        "NOT_INSTRUMENTED")

STALE_AFTER_SECONDS = 24 * 3600  # Section 23 -- a success older than this is no longer "current"

# Section 25 -- Tier 1 only: the sources the two real Intelligence Objects actually depend on,
# plus the already-registered historical-acquisition candidates this corpus has previously named
# (never a guessed URL -- each of these appears verbatim in an existing module, cited in `origin`).
TIER1_CANDIDATES = (
    {"source_id": "src_worldbank_api", "name": "World Bank Indicators API",
     "url": "https://api.worldbank.org/v2/country/USA/indicator/EG.USE.ELEC.KH.PC?date=2020:2022&format=json&per_page=5",
     "origin": "intel/statistical_evidence/scripts/world_bank_fetch.py"},
    {"source_id": "src_eia_api", "name": "EIA Electricity Retail Sales API",
     "url": "https://api.eia.gov/v2/electricity/retail-sales/data/?frequency=monthly&api_key=",
     "origin": "intel/statistical_context/energy_indicators.py"},
    {"source_id": "src_crossref_api", "name": "CrossRef Works API",
     "url": "https://api.crossref.org/works?rows=1",
     "origin": "intel/historical_evidence/fetch_real_historical_analogy_evidence.py"},
    {"source_id": "src_federal_register_api", "name": "Federal Register API",
     "url": "https://www.federalregister.gov/api/v1/documents.json?per_page=1",
     "origin": "intel/historical_acquisition/fetch_federal_register.py"},
    {"source_id": "src_ilo", "name": "ILO (International Labour Organization)",
     "url": "https://www.ilo.org", "origin": "N-5 spec Section 58 candidate list"},
    {"source_id": "src_riss", "name": "RISS (한국교육학술정보원)",
     "url": "https://www.riss.kr", "origin": "N-5 spec Section 58 candidate list"},
)


def _classify_error(exc):
    msg = str(exc)
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code in (401, 403):
            return "AUTH_REQUIRED", exc.code
        if exc.code == 404:
            return "NOT_FOUND", exc.code
        return "DEGRADED", exc.code
    if "CONNECT" in msg or "proxy" in msg.lower() or "connect_rejected" in msg.lower():
        return "BLOCKED", "UNKNOWN"
    return "BLOCKED", "UNKNOWN"


def _is_egress_proxy_block(exc):
    """N-7 Section 12 -- detect the sandbox's own network-egress proxy rejection (e.g. 'Tunnel
    connection failed: 403 Forbidden') so it is never confused with the *source* itself being
    blocked. This is an environment fact, not a source fact."""
    msg = str(exc).lower()
    return ("tunnel connection failed" in msg) or ("proxy" in msg and "403" in msg)


def current_environment():
    """N-7 Section 11 -- which execution environment this check is running in. GitHub Actions sets
    GITHUB_ACTIONS=true; absent that, this is the sandbox (egress-restricted by org policy)."""
    import os
    return "GITHUB_ACTIONS" if os.environ.get("GITHUB_ACTIONS") == "true" else "SANDBOX"


def check_one_source(candidate, timeout_seconds=8, max_retries=2, clock=time.time):
    """A single source check with retry/backoff (reusing queue_model.retry_with_backoff) and a
    per-call circuit breaker so one bad source can never hang the whole pilot. Returns a
    SOURCE_HEALTH_STATES-shaped record -- never a guessed HEALTHY."""
    breaker = qm.CircuitBreaker(failure_threshold=max_retries, cooldown_seconds=0, clock=clock)
    last_error = None
    attempt = 0
    env = current_environment()
    while breaker.allow_request():
        try:
            req = urllib.request.Request(candidate["url"], headers={"User-Agent": "METAXIS-source-health/1.0"})
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                status_code = resp.status
            breaker.record_success()
            return {
                "source_id": candidate["source_id"], "status": "HEALTHY",
                "last_checked": _now(), "last_http_status": status_code, "last_success": True,
                "failure_count": attempt, "is_stale": False,
                "known_limitation": "single live check, not continuous monitoring",
                "provenance_of_check": candidate["origin"],
                "environment": env, "environment_status": "OK", "source_status": "HEALTHY",
            }
        except Exception as e:  # noqa: BLE001 -- a failed health check must never raise
            last_error = e
            breaker.record_failure()
            delay = qm.retry_with_backoff(attempt, base_seconds=1, max_retries=max_retries)
            attempt += 1
            if delay is None:
                break

    status, http_status = _classify_error(last_error) if last_error else ("UNKNOWN", "UNKNOWN")
    egress_blocked = last_error is not None and _is_egress_proxy_block(last_error)
    # Section 12: a sandbox egress-proxy rejection is an ENVIRONMENT fact, never a SOURCE fact.
    # The legacy `status` field is kept for existing consumers, but source_status/environment_status
    # now say explicitly which layer actually failed.
    if egress_blocked and env == "SANDBOX":
        source_status = "UNKNOWN"
        environment_status = "EGRESS_BLOCKED"
    else:
        source_status = status
        environment_status = "OK"
    return {
        "source_id": candidate["source_id"], "status": status,
        "last_checked": _now(), "last_http_status": http_status, "last_success": False,
        "failure_count": attempt, "is_stale": False,
        "known_limitation": f"{attempt} attempt(s) failed: {str(last_error)[:200]}" if last_error else "no attempts made",
        "provenance_of_check": candidate["origin"],
        "environment": env, "environment_status": environment_status, "source_status": source_status,
    }


def _now():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def run_tier1_pilot(candidates=TIER1_CANDIDATES):
    """Section 58-59 -- a small, real, honest pilot against Tier-1 sources only. Every candidate
    gets CHECKED, never silently skipped; a 0-HEALTHY result is reported as-is, never reinterpreted
    as a TRUE_NULL data finding (that vocabulary belongs to evidence gaps, not source health).
    N-7: also tags the run with its execution environment (Section 11)."""
    results = [check_one_source(c) for c in candidates]
    return {"checked_at": _now(), "environment": current_environment(), "results": results}


def mark_stale(records, now=None, stale_after_seconds=STALE_AFTER_SECONDS):
    """Section 23 -- age-based staleness, independent of status. An old HEALTHY stays HEALTHY in
    its `status` field but gets is_stale=True so a reader never mistakes a past success for a
    current one."""
    import datetime
    now = now or datetime.datetime.now(datetime.timezone.utc)
    out = []
    for r in records:
        r = dict(r)
        try:
            checked = datetime.datetime.fromisoformat(r["last_checked"])
        except (KeyError, ValueError, TypeError):
            r["is_stale"] = True
            out.append(r)
            continue
        age = (now - checked).total_seconds()
        r["is_stale"] = age > stale_after_seconds
        out.append(r)
    return out


LIVE_RESULT_PATH = HERE / "source_health_result.github_actions.json"


def save_result(result, path=None):
    target = path or RESULT_PATH
    target.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return target


def save_environment_result(result):
    """N-7 Section 11 -- route a run's result to an environment-specific artifact, so a sandbox
    EGRESS_BLOCKED run is never overwritten onto, or confused with, a real GitHub Actions live
    result. Returns the path actually written."""
    if result.get("environment") == "GITHUB_ACTIONS":
        return save_result(result, LIVE_RESULT_PATH)
    return save_result(result, RESULT_PATH)


def load_result():
    if not RESULT_PATH.exists():
        return None
    return json.loads(RESULT_PATH.read_text(encoding="utf-8"))


def load_live_result():
    """The most recent GitHub Actions live source-health result, or None if the workflow has not
    produced one yet (honest absence, never fabricated)."""
    if not LIVE_RESULT_PATH.exists():
        return None
    return json.loads(LIVE_RESULT_PATH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    result = run_tier1_pilot()
    save_environment_result(result)
    print(json.dumps(result, ensure_ascii=False, indent=1))
