# N-9 SECTIONS 9-14 -- Live/Sandbox Artifact Write Protection.
#
# Root incident this module closes (documented in N-8's final report): running
# intel/evidence_network/tests/test_live_acquisition_attempts.py re-executes the real
# acquisition scripts against whatever network the test runner has. In the sandbox that network
# is egress-blocked, so a routine test run silently overwrote the real GITHUB_ACTIONS result
# files (policy_research_acquisition_result.json / longitudinal_evidence_acquisition_result.json)
# with fresh SANDBOX_BLOCKED data. N-8 caught this manually via `git status` and `git checkout --`.
# This module makes that structurally impossible instead of relying on vigilance:
#
#   1. every acquisition result file carries an explicit "environment" field
#      (GITHUB_ACTIONS / SANDBOX / LOCAL / TEST_FIXTURE -- never guessed).
#   2. a GITHUB_ACTIONS result is written ONLY to its own environment-suffixed canonical path
#      (the same ".github_actions.json" pattern intel/source_health/source_health_model.py
#      already uses), never to the shared/base path a sandbox or test run also writes to.
#   3. guarded_write() refuses (raises LiveResultOverwriteBlocked) any attempt to write a
#      non-GITHUB_ACTIONS payload onto a path this module designates as a GITHUB_ACTIONS
#      canonical path -- a second, explicit line of defense even if a caller's routing logic
#      has a bug.
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent

ENVIRONMENT_VALUES = ("GITHUB_ACTIONS", "SANDBOX", "LOCAL", "TEST_FIXTURE")

# Canonical paths that must contain ONLY a GITHUB_ACTIONS-produced result. Any attempt to write
# a non-GITHUB_ACTIONS payload to one of these is refused by guarded_write(). Paths are absolute,
# resolved at import time, so comparison is robust to relative-vs-absolute path spelling.
CANONICAL_GITHUB_ACTIONS_PATHS = frozenset(
    str(p.resolve()) for p in (
        HERE / "policy_research_acquisition_result.github_actions.json",
        HERE / "counterevidence_live_acquisition_result.github_actions.json",
        HERE / "longitudinal_evidence_acquisition_result.github_actions.json",
        HERE.parent / "source_health" / "source_health_result.github_actions.json",
    )
)


class LiveResultOverwriteBlocked(RuntimeError):
    """Raised when something attempted to overwrite a GITHUB_ACTIONS canonical result file with
    a non-GITHUB_ACTIONS (sandbox/test/local) payload. This is a structural refusal, not a
    warning -- the caller must route to the non-canonical path instead."""


def detect_environment(explicit=None):
    """Three real sources of truth, in order -- never a guess:
      1. an explicit override the caller passed (e.g. a test deliberately simulating a
         TEST_FIXTURE write to exercise guarded_write()'s refusal path).
      2. the GITHUB_ACTIONS=true env var GitHub Actions itself sets (same fact
         source_health_model.current_environment() already uses -- kept consistent).
      3. absent both, this is some other execution context. N9_LIVE_RESULT_ENVIRONMENT lets a
         test harness declare TEST_FIXTURE honestly instead of this module guessing SANDBOX for
         a context that is not actually the egress-restricted sandbox either; with neither signal
         present, SANDBOX is the correct default because that has been this repo's only
         non-GitHub-Actions execution environment to date (never silently relabeled LOCAL)."""
    if explicit is not None:
        assert explicit in ENVIRONMENT_VALUES, f"unknown environment value: {explicit}"
        return explicit
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return "GITHUB_ACTIONS"
    forced = os.environ.get("N9_LIVE_RESULT_ENVIRONMENT")
    if forced in ENVIRONMENT_VALUES:
        return forced
    return "SANDBOX"


def live_path_for(base_path):
    """The environment-suffixed canonical path a GITHUB_ACTIONS result for this base_path must be
    written to -- e.g. foo_result.json -> foo_result.github_actions.json. Mirrors the existing
    source_health_result.json / source_health_result.github_actions.json pattern exactly, so this
    is a minimal, already-precedented convention rather than a new taxonomy."""
    base_path = Path(base_path)
    return base_path.with_suffix(".github_actions.json")


def guarded_write(path, payload, environment):
    """Writes payload (a dict already carrying "environment") to path, UNLESS path is a
    designated GITHUB_ACTIONS canonical path and environment is not GITHUB_ACTIONS -- in which
    case it refuses and raises LiveResultOverwriteBlocked instead of silently overwriting real
    live data with sandbox/test/local data."""
    path = Path(path)
    resolved = str(path.resolve()) if path.exists() or path.parent.exists() else str(path)
    is_canonical_live_path = resolved in CANONICAL_GITHUB_ACTIONS_PATHS
    if is_canonical_live_path and environment != "GITHUB_ACTIONS":
        raise LiveResultOverwriteBlocked(
            f"refused to write a {environment} result onto the GITHUB_ACTIONS canonical path "
            f"{path} -- route {environment} writes to the non-canonical base path instead "
            f"(see live_result_guard.live_path_for / select_output_path)"
        )
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path


def select_output_path(base_path, environment):
    """Section 11's minimal environment-isolation rule: a GITHUB_ACTIONS result goes to its own
    environment-suffixed path; every other environment goes to the shared base path. This is
    exactly the rule source_health_model.save_environment_result() already implements for source
    health -- this function generalizes it for the other three live-acquisition scripts so they
    can no longer collide with a real live result on the same canonical path."""
    if environment == "GITHUB_ACTIONS":
        return live_path_for(base_path)
    return Path(base_path)


def load_with_precedence(base_path):
    """Section 14 -- deterministic result selection, never 'whichever file has the latest mtime'.
    Rule (documented here, applied by every reader): when a GITHUB_ACTIONS live result exists for
    this base_path, it is the PRIMARY result shown for display/operator purposes, even if the
    sandbox/base file has a more recent mtime (e.g. from a local test run) -- a live, real-network
    GitHub Actions observation always outranks a sandbox run that is known in advance to be
    egress-blocked. The sandbox/base result is never discarded: it is always also returned as
    SECONDARY, since "SANDBOX=BLOCKED, GITHUB_ACTIONS=HEALTHY for the same source" is a correct,
    expected, environment-specific pair of observations -- not a contradiction to reconcile into
    one fake unified status (N-9 Section 16)."""
    base_path = Path(base_path)
    live_path = live_path_for(base_path)
    live = json.loads(live_path.read_text(encoding="utf-8")) if live_path.exists() else None
    base = json.loads(base_path.read_text(encoding="utf-8")) if base_path.exists() else None
    primary = live if live is not None else base
    primary_source = "GITHUB_ACTIONS_FILE" if live is not None else ("BASE_FILE" if base is not None else "NONE")
    secondary = base if live is not None else None
    return {
        "primary": primary,
        "primary_source": primary_source,
        "secondary_sandbox_or_base": secondary,
    }
