# N-6 PRIORITY 4 -- Policy Research Live Acquisition attempt log. NOT a new Intelligence/Claim
# engine: this reuses source_health_model.check_one_source() (itself reusing
# acquisition_queue.queue_model's CircuitBreaker/retry_with_backoff) against the SAME already-
# registered source URLs in source_health_model.TIER1_CANDIDATES -- never a guessed/new URL -- and
# records the attempt honestly. If blocked (expected, given this sandbox's confirmed egress
# policy), this module records SEARCH_NOT_RUN/ACCESS_BLOCKED with the real proxy error captured and
# fabricates NO policy research evidence item. The two topics in scope (AI_ENERGY_INFRA,
# AI_LABOR) are reflected only in which already-registered sources are attempted, never in any
# synthesized result content.
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "intel" / "source_health"))
import source_health_model as shm  # noqa: E402
import live_result_guard as lrg  # noqa: E402

RESULT_PATH = HERE / "policy_research_acquisition_result.json"

# Institutions named in the spec (OECD, World Bank, IEA, EIA, KDI, ILO) mapped to sources that are
# ALREADY registered in source_health_model.TIER1_CANDIDATES (never a newly-guessed URL). Named
# institutions this corpus has no already-registered URL for (OECD, IEA, KDI) are recorded as
# NO_REGISTERED_SOURCE rather than inventing a URL for them.
POLICY_RESEARCH_TARGETS = (
    {"topic": "AI_ENERGY_INFRA", "institution": "World Bank", "candidate_id": "src_worldbank_api"},
    {"topic": "AI_ENERGY_INFRA", "institution": "EIA", "candidate_id": "src_eia_api"},
    {"topic": "AI_LABOR", "institution": "World Bank", "candidate_id": "src_worldbank_api"},
    {"topic": "AI_LABOR", "institution": "ILO", "candidate_id": "src_ilo"},
    {"topic": "AI_ENERGY_INFRA", "institution": "OECD", "candidate_id": None},
    {"topic": "AI_ENERGY_INFRA", "institution": "IEA", "candidate_id": None},
    {"topic": "AI_LABOR", "institution": "KDI", "candidate_id": None},
)

_CANDIDATES_BY_ID = {c["source_id"]: c for c in shm.TIER1_CANDIDATES}


def attempt_policy_research_acquisition(targets=POLICY_RESEARCH_TARGETS):
    """Attempts a real HTTP request (via check_one_source, 8s timeout, existing circuit-breaker
    pattern) for each target that has an already-registered source. Returns one record per target
    -- never raises, never fabricates an evidence item. A target naming an institution this corpus
    has no registered URL for is recorded NO_REGISTERED_SOURCE, not a guessed URL."""
    results = []
    for target in targets:
        cand = _CANDIDATES_BY_ID.get(target["candidate_id"]) if target["candidate_id"] else None
        if cand is None:
            results.append({
                "topic": target["topic"], "institution": target["institution"],
                "acquisition_outcome": "NO_REGISTERED_SOURCE",
                "detail": "no already-registered source URL exists in this corpus for this "
                          "institution -- Section 4's no-guessed-URL rule means no request was "
                          "attempted rather than inventing one",
            })
            continue
        check = shm.check_one_source(cand)
        outcome = "ACCESS_BLOCKED" if check["status"] in ("BLOCKED", "AUTH_REQUIRED") else (
            "SEARCH_RUN_NO_EVIDENCE" if check["status"] == "HEALTHY" else "SEARCH_NOT_RUN")
        results.append({
            "topic": target["topic"], "institution": target["institution"],
            "source_id": cand["source_id"], "source_url": cand["url"],
            "acquisition_outcome": outcome,
            "http_status": check["status"], "proxy_error": check.get("known_limitation"),
            "checked_at": check["last_checked"],
        })
    return results


def save_result(results, environment=None):
    """N-9 Section 9-11: tags the result with its real execution environment and routes
    GITHUB_ACTIONS results to their own canonical path so a sandbox/test run of this same
    function can never again silently clobber a real live result (the exact N-8 incident)."""
    env = lrg.detect_environment(environment)
    payload = {
        "run_at": shm._now(),
        "environment": env,
        "note": ("N-6 Priority 4 -- live policy research acquisition attempt. No evidence item is "
                 "admitted into any Intelligence Object/Claim from this run unless "
                 "acquisition_outcome == SEARCH_RUN_NO_EVIDENCE or better; ACCESS_BLOCKED/"
                 "SEARCH_NOT_RUN/NO_REGISTERED_SOURCE rows contribute nothing to the evidence "
                 "graph."),
        "results": results,
    }
    target = lrg.select_output_path(RESULT_PATH, env)
    return lrg.guarded_write(target, payload, env)


if __name__ == "__main__":
    results = attempt_policy_research_acquisition()
    path = save_result(results)
    print(json.dumps({"saved_to": str(path), "results": results}, ensure_ascii=False, indent=1))
