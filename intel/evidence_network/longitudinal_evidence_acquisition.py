# N-6 PRIORITY 6 -- Longitudinal Evidence Acquisition attempt log. Attempts real live fetches for
# BASELINE / TRANSITION / CURRENT data points (same already-registered World Bank/EIA source URLs,
# only the date-range query parameter changes -- never a new or guessed source). CRITICAL: on
# ACCESS_BLOCKED this module must NOT construct a BASELINE->TRANSITION->CURRENT structure from
# fabricated data, and must NOT promote the single existing statistic already in this corpus
# (series_af37f1207e7ff042 / the AI_LABOR equivalent) into a "transition" claim just because no new
# data came in. If every period is blocked, the honest output is simply "no longitudinal evidence
# acquired this run" -- nothing more.
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "intel" / "source_health"))
import source_health_model as shm  # noqa: E402

import live_result_guard as lrg  # noqa: E402

RESULT_PATH = HERE / "longitudinal_evidence_acquisition_result.json"

# BASELINE/TRANSITION/CURRENT windows for the same already-registered World Bank indicator this
# corpus's real AI_ENERGY_INFRA Intelligence Object already cites (EG.USE.ELEC.KH.PC, USA) -- only
# the date range differs per period, never a new indicator or country.
LONGITUDINAL_TARGETS = (
    {"topic": "AI_ENERGY_INFRA", "period": "BASELINE", "date_range": "2010:2013",
     "indicator": "EG.USE.ELEC.KH.PC"},
    {"topic": "AI_ENERGY_INFRA", "period": "TRANSITION", "date_range": "2018:2021",
     "indicator": "EG.USE.ELEC.KH.PC"},
    {"topic": "AI_ENERGY_INFRA", "period": "CURRENT", "date_range": "2023:2024",
     "indicator": "EG.USE.ELEC.KH.PC"},
)

_WB_BASE = "https://api.worldbank.org/v2/country/USA/indicator/{indicator}?date={date_range}&format=json&per_page=5"


def _attempt_fetch(url, timeout_seconds=8):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "METAXIS-longitudinal/1.0"})
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            body = resp.read()
            return {"ok": True, "http_status": resp.status, "bytes": len(body)}
    except Exception as e:  # noqa: BLE001 -- never raise past an acquisition attempt
        status, http_status = shm._classify_error(e)
        return {"ok": False, "status": status, "http_status": http_status, "error": str(e)}


def attempt_longitudinal_acquisition(targets=LONGITUDINAL_TARGETS):
    results = []
    for target in targets:
        url = _WB_BASE.format(indicator=target["indicator"], date_range=target["date_range"])
        attempt = _attempt_fetch(url)
        if attempt["ok"]:
            outcome = "SEARCH_RUN_NO_EVIDENCE"  # fetched but not yet parsed into an admitted claim
        else:
            outcome = "ACCESS_BLOCKED" if attempt["status"] in ("BLOCKED", "AUTH_REQUIRED") else "SEARCH_NOT_RUN"
        results.append({
            "topic": target["topic"], "period": target["period"],
            "indicator": target["indicator"], "date_range": target["date_range"], "url": url,
            "acquisition_outcome": outcome,
            "proxy_error": attempt.get("error") if not attempt["ok"] else None,
        })
    return results


def save_result(results, environment=None):
    """N-9 Section 9-11: see policy_research_acquisition.save_result for the rationale -- same
    environment-tagging + canonical-path routing so a sandbox/test run can never clobber the real
    GITHUB_ACTIONS result."""
    env = lrg.detect_environment(environment)
    all_blocked = all(r["acquisition_outcome"] != "SEARCH_RUN_NO_EVIDENCE" for r in results)
    payload = {
        "run_at": shm._now(),
        "environment": env,
        "note": ("N-6 Priority 6 -- live longitudinal (BASELINE/TRANSITION/CURRENT) acquisition "
                 "attempt. No BASELINE->TRANSITION->CURRENT structure is constructed from this "
                 "run's results, and no existing single statistic is promoted into a 'transition' "
                 "claim, unless at least one period actually returned real data "
                 "(acquisition_outcome == SEARCH_RUN_NO_EVIDENCE or better) for a Priority 7-9 "
                 "follow-up to parse."),
        "all_periods_blocked": all_blocked,
        "longitudinal_structure_constructed": False,  # never flipped true by this run alone
        "results": results,
    }
    target = lrg.select_output_path(RESULT_PATH, env)
    return lrg.guarded_write(target, payload, env)


if __name__ == "__main__":
    results = attempt_longitudinal_acquisition()
    path = save_result(results)
    print(json.dumps({"saved_to": str(path), "results": results}, ensure_ascii=False, indent=1))
