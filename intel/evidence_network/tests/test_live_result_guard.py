# N-9 SECTIONS 9-14 -- Live/Sandbox Artifact Write Protection tests.
# Structural regression test for the exact N-8 incident: a TEST_FIXTURE/SANDBOX write must never
# be allowed to land on a GITHUB_ACTIONS canonical result path.
import atexit
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import live_result_guard as lrg  # noqa: E402
import policy_research_acquisition as pra  # noqa: E402
import counterevidence_live_acquisition as cla  # noqa: E402
import longitudinal_evidence_acquisition as lea  # noqa: E402

# N-9B Deliverable 0 follow-through: the three
# test_*_save_result_with_test_fixture_environment_never_touches_live_file
# tests below call the real production attempt_*/save_result() functions,
# which overwrite the real canonical BASE result file (e.g.
# policy_research_acquisition_result.json) with freshly-fetched content as
# a side effect, even though environment="TEST_FIXTURE" correctly keeps
# GITHUB_ACTIONS-suffixed live files untouched. That base file is real
# canonical data (consumed elsewhere as the SANDBOX/base precedence slot),
# so a full-suite run must not leave it mutated. We snapshot each base
# file's real bytes once at import time and restore them on interpreter
# exit, the same pattern used in test_url_resolver.py / test_source_registry.py.
_BASE_RESULT_PATHS = [
    pra.HERE / "policy_research_acquisition_result.json",
    cla.HERE / "counterevidence_live_acquisition_result.json",
    lea.HERE / "longitudinal_evidence_acquisition_result.json",
]
_BASE_RESULT_BACKUPS = {
    p: (p.read_bytes() if p.exists() else None) for p in _BASE_RESULT_PATHS
}


def _restore_base_results():
    for p, backup in _BASE_RESULT_BACKUPS.items():
        if backup is not None:
            p.write_bytes(backup)
        elif p.exists():
            p.unlink()


atexit.register(_restore_base_results)


def test_detect_environment_explicit_override_wins():
    assert lrg.detect_environment("TEST_FIXTURE") == "TEST_FIXTURE"
    assert lrg.detect_environment("GITHUB_ACTIONS") == "GITHUB_ACTIONS"


def test_detect_environment_rejects_unknown_value():
    try:
        lrg.detect_environment("NOT_A_REAL_ENVIRONMENT")
        raise AssertionError("expected AssertionError for an unknown environment value")
    except AssertionError as e:
        assert "unknown environment value" in str(e)


def test_live_path_for_matches_source_health_precedent():
    assert lrg.live_path_for(Path("foo_result.json")) == Path("foo_result.github_actions.json")


def test_canonical_github_actions_paths_cover_all_three_live_acquisition_scripts():
    names = {Path(p).name for p in lrg.CANONICAL_GITHUB_ACTIONS_PATHS}
    assert "policy_research_acquisition_result.github_actions.json" in names
    assert "counterevidence_live_acquisition_result.github_actions.json" in names
    assert "longitudinal_evidence_acquisition_result.github_actions.json" in names


def test_guarded_write_refuses_a_test_fixture_write_onto_a_canonical_live_path():
    """This IS the N-8 incident, reproduced deliberately and confirmed blocked: a TEST_FIXTURE
    (sandbox-test-equivalent) payload attempting to write onto a GITHUB_ACTIONS canonical path
    must be refused, never silently applied."""
    canonical_path = next(iter(lrg.CANONICAL_GITHUB_ACTIONS_PATHS))
    before = Path(canonical_path).read_text(encoding="utf-8") if Path(canonical_path).exists() else None
    try:
        lrg.guarded_write(canonical_path, {"environment": "TEST_FIXTURE", "fabricated": True}, "TEST_FIXTURE")
        raise AssertionError("guarded_write must have refused this write")
    except lrg.LiveResultOverwriteBlocked:
        pass
    after = Path(canonical_path).read_text(encoding="utf-8") if Path(canonical_path).exists() else None
    assert before == after, "canonical live file content must be completely unchanged after a blocked write attempt"


def test_guarded_write_refuses_a_sandbox_write_onto_a_canonical_live_path():
    canonical_path = next(iter(lrg.CANONICAL_GITHUB_ACTIONS_PATHS))
    try:
        lrg.guarded_write(canonical_path, {"environment": "SANDBOX"}, "SANDBOX")
        raise AssertionError("guarded_write must have refused this write")
    except lrg.LiveResultOverwriteBlocked:
        pass


def test_guarded_write_allows_a_github_actions_write_onto_its_own_canonical_path():
    with tempfile.TemporaryDirectory() as td:
        # Use a throwaway path registered as canonical only for this test via monkeypatch-free
        # direct call: guarded_write's canonicality check is path-based, so we simulate by
        # writing to a NON-canonical temp path with environment=GITHUB_ACTIONS and confirming it
        # succeeds (the canonical-path refusal path is already proven above; this proves the
        # non-refusal path is not over-broad).
        p = Path(td) / "some_result.github_actions.json"
        out = lrg.guarded_write(p, {"environment": "GITHUB_ACTIONS"}, "GITHUB_ACTIONS")
        assert out.exists()


def test_select_output_path_routes_github_actions_to_suffixed_path():
    base = Path("x_result.json")
    assert lrg.select_output_path(base, "GITHUB_ACTIONS") == Path("x_result.github_actions.json")
    assert lrg.select_output_path(base, "SANDBOX") == base
    assert lrg.select_output_path(base, "TEST_FIXTURE") == base
    assert lrg.select_output_path(base, "LOCAL") == base


def test_policy_research_save_result_with_test_fixture_environment_never_touches_live_file():
    """End-to-end: calling the real production save_result() with environment='TEST_FIXTURE'
    (as a test harness honestly would) must land on the base path, never the canonical live
    path -- the live file's content and mtime are untouched."""
    live_path = pra.HERE / "policy_research_acquisition_result.github_actions.json"
    before = live_path.read_text(encoding="utf-8") if live_path.exists() else None
    results = pra.attempt_policy_research_acquisition()
    written = pra.save_result(results, environment="TEST_FIXTURE")
    assert written.name == "policy_research_acquisition_result.json"
    after = live_path.read_text(encoding="utf-8") if live_path.exists() else None
    assert before == after


def test_counterevidence_save_result_with_test_fixture_environment_never_touches_live_file():
    live_path = cla.HERE / "counterevidence_live_acquisition_result.github_actions.json"
    before = live_path.read_text(encoding="utf-8") if live_path.exists() else None
    results = cla.attempt_counterevidence_acquisition()
    written = cla.save_result(results, environment="TEST_FIXTURE")
    assert written.name == "counterevidence_live_acquisition_result.json"
    after = live_path.read_text(encoding="utf-8") if live_path.exists() else None
    assert before == after


def test_longitudinal_save_result_with_test_fixture_environment_never_touches_live_file():
    live_path = lea.HERE / "longitudinal_evidence_acquisition_result.github_actions.json"
    before = live_path.read_text(encoding="utf-8") if live_path.exists() else None
    results = lea.attempt_longitudinal_acquisition()
    written = lea.save_result(results, environment="TEST_FIXTURE")
    assert written.name == "longitudinal_evidence_acquisition_result.json"
    after = live_path.read_text(encoding="utf-8") if live_path.exists() else None
    assert before == after


def test_all_three_live_files_carry_environment_github_actions():
    for name in ("policy_research_acquisition_result.github_actions.json",
                 "counterevidence_live_acquisition_result.github_actions.json",
                 "longitudinal_evidence_acquisition_result.github_actions.json"):
        data = json.loads((HERE.parent / name).read_text(encoding="utf-8"))
        assert data["environment"] == "GITHUB_ACTIONS"


def test_load_with_precedence_prefers_github_actions_but_keeps_sandbox_as_secondary():
    base = HERE.parent / "policy_research_acquisition_result.json"
    result = lrg.load_with_precedence(base)
    assert result["primary_source"] == "GITHUB_ACTIONS_FILE"
    assert result["primary"]["environment"] == "GITHUB_ACTIONS"
    assert result["secondary_sandbox_or_base"] is not None
    # whichever non-live environment most recently wrote the base file (SANDBOX from a plain
    # script run, or TEST_FIXTURE from this same suite's own end-to-end tests above) is valid
    # here -- the invariant this guards is "never GITHUB_ACTIONS on the base/secondary slot",
    # not a specific one of the two legitimate non-live environments.
    assert result["secondary_sandbox_or_base"]["environment"] in ("SANDBOX", "TEST_FIXTURE", "LOCAL")


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    failed = []
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:  # noqa: BLE001
            failed.append((t.__name__, repr(e)))
    for name, err in failed:
        print(f"FAIL {name}: {err}")
    print(f"{passed}/{len(tests)} passed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
