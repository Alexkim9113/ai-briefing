# N-6 PRIORITY 5 -- Counterevidence Live Acquisition attempt log. Same pattern as
# policy_research_acquisition.py (N-6 Priority 4): reuses source_health_model.check_one_source()
# against already-registered source URLs, never a new engine and never a guessed URL. Scope: the
# two counterevidence angles this corpus already recognizes (non-AI drivers of power demand for
# AI_ENERGY_INFRA, non-AI drivers of labor-market change for AI_LABOR -- see
# intel/counterevidence/energy_infra_counterevidence.py and report_engine's
# build_counterevidence_section()). A blocked attempt is recorded as ACCESS_BLOCKED/
# SEARCH_NOT_RUN; no counterevidence item is fabricated or admitted.
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "intel" / "source_health"))
import source_health_model as shm  # noqa: E402

RESULT_PATH = HERE / "counterevidence_live_acquisition_result.json"

_CANDIDATES_BY_ID = {c["source_id"]: c for c in shm.TIER1_CANDIDATES}

# Each row: the counterevidence ANGLE already named in this corpus's existing counterevidence
# records (intel/counterevidence/energy_infra_counterevidence.py / build_counterevidence_section())
# paired with the already-registered source that could, if reachable, speak to it.
COUNTEREVIDENCE_TARGETS = (
    {"topic": "AI_ENERGY_INFRA", "angle": "manufacturing_reshoring_power_demand",
     "candidate_id": "src_eia_api"},
    {"topic": "AI_ENERGY_INFRA", "angle": "ev_adoption_power_demand", "candidate_id": "src_eia_api"},
    {"topic": "AI_ENERGY_INFRA", "angle": "weather_driven_power_demand",
     "candidate_id": "src_worldbank_api"},
    {"topic": "AI_LABOR", "angle": "post_pandemic_labor_participation_recovery",
     "candidate_id": "src_worldbank_api"},
    {"topic": "AI_LABOR", "angle": "demographic_aging_labor_participation", "candidate_id": "src_ilo"},
)


def attempt_counterevidence_acquisition(targets=COUNTEREVIDENCE_TARGETS):
    results = []
    for target in targets:
        cand = _CANDIDATES_BY_ID.get(target["candidate_id"])
        if cand is None:
            results.append({**target, "acquisition_outcome": "NO_REGISTERED_SOURCE"})
            continue
        check = shm.check_one_source(cand)
        outcome = "ACCESS_BLOCKED" if check["status"] in ("BLOCKED", "AUTH_REQUIRED") else (
            "SEARCH_RUN_NO_EVIDENCE" if check["status"] == "HEALTHY" else "SEARCH_NOT_RUN")
        results.append({
            "topic": target["topic"], "angle": target["angle"],
            "source_id": cand["source_id"], "source_url": cand["url"],
            "acquisition_outcome": outcome,
            "http_status": check["status"], "proxy_error": check.get("known_limitation"),
            "checked_at": check["last_checked"],
        })
    return results


def save_result(results):
    payload = {
        "run_at": shm._now(),
        "note": ("N-6 Priority 5 -- live counterevidence acquisition attempt. No counterevidence "
                 "item is admitted into any Intelligence Object/Claim from this run unless "
                 "acquisition_outcome == SEARCH_RUN_NO_EVIDENCE or better; ACCESS_BLOCKED/"
                 "SEARCH_NOT_RUN/NO_REGISTERED_SOURCE rows contribute nothing to the evidence "
                 "graph (and never render as 'no counterevidence exists')."),
        "results": results,
    }
    RESULT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return RESULT_PATH


if __name__ == "__main__":
    results = attempt_counterevidence_acquisition()
    path = save_result(results)
    print(json.dumps({"saved_to": str(path), "results": results}, ensure_ascii=False, indent=1))
