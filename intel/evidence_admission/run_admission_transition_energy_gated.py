#!/usr/bin/env python3
# PHASE M.5E-4 -- item 2: gated CLI entry point for the TRANSITION-gap (AI_ENERGY_INFRA)
# admission-gate shadow job.
#
# Chosen as a NEW file (run_admission_transition_energy_gated.py) rather than modifying
# run_admission_transition_energy.py in place, for two reasons: (1) run_admission_transition_
# energy.py already has its own committed test file
# (intel/evidence_admission/tests/test_run_admission_transition_energy.py, from M.5E-3) that
# exercises its current "call admission_gate directly" behavior end-to-end; keeping that file
# unmodified means that existing test suite keeps proving what it always proved, with zero risk
# of a regression from this slice. (2) the supervising session's instructions explicitly permit
# either approach ("your call, document which") and ungated-vs-gated are now two clearly
# different real operations (skip the pre-filter vs enforce it) -- naming them as two files
# is more honest than silently changing run_admission_transition_energy.py's meaning under the
# same name. run_admission_transition_energy.py itself is NOT modified by this slice.
#
# This is now the RECOMMENDED entry point for the TRANSITION_GAP/AI_ENERGY_INFRA shadow job
# going forward (a supervising session should point .github/workflows/daily.yml at THIS file,
# not the ungated one, if/when it wires this job up) -- but that wiring decision itself is left
# to the supervising session per the standing constraints.
#
# Reads the shadow result file (never the raw fetcher output directly), runs every canonicalized
# candidate through transition_admission_gate.classify_batch() FIRST, and passes only
# TRANSITION_ADMITTED_CANDIDATE-classified documents through to the real, unforked
# admission_gate.admit_shadow_result(). TRANSITION_REJECTED and INSUFFICIENT_TRANSITION_EVIDENCE
# candidates never reach admission_gate -- they are logged to
# transition_admission_gate_log.json (append-only across runs) with their reason, never silently
# dropped. Zero LLM.
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
GAP_CLOSURE_DIR = HERE.parent / "gap_closure"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(GAP_CLOSURE_DIR))
import admission_gate  # noqa: E402
import transition_admission_gate as tag  # noqa: E402

SHADOW_RESULT_PATH = GAP_CLOSURE_DIR / "transition_evidence_energy_result.json"
GATE_LOG_PATH = GAP_CLOSURE_DIR / "transition_admission_gate_log.json"


def _load_json(path, default):
    if not Path(path).exists():
        return default
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _append_gate_log(entries, log_path=GATE_LOG_PATH):
    existing = _load_json(log_path, [])
    if not isinstance(existing, list):
        existing = []
    existing.extend(entries)
    log_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_gated_admission(shadow_result, documents=None, admit_fn=admission_gate.admit_shadow_result,
                         documents_path=None):
    """Core, testable logic: takes an already-parsed shadow result (same shape
    fetch_transition_evidence_energy.py's run_pilot() produces), runs the pre-filter, and calls
    admit_fn (admission_gate.admit_shadow_result by default; a test stub in tests) only with a
    reconstructed shadow_result containing exclusively TRANSITION_ADMITTED_CANDIDATE documents.
    Returns (admission_summary_or_none, gate_log_entries, filtered_shadow_result).

    documents is the real corpus dict (for computing existing_source_families); when None it is
    loaded from admission_gate.DOCUMENTS_PATH (or documents_path override) -- read-only, never
    written here."""
    if documents is None:
        docs_path = documents_path or admission_gate.DOCUMENTS_PATH
        documents = _load_json(docs_path, {})
    existing_families = tag.existing_source_families_from_documents(documents)

    now_iso = datetime.now(timezone.utc).isoformat()
    gate_log_entries = []
    admitted_by_entry = []

    for entry in shadow_result.get("results", []):
        candidates = entry.get("documents_canonicalized") or []
        verdicts = tag.classify_batch(candidates, existing_source_families=existing_families)
        admitted_candidates = []
        for cand, verdict in zip(candidates, verdicts):
            log_row = dict(verdict)
            log_row["gate_run_at"] = now_iso
            log_row["gap_type"] = entry.get("gap_type") or cand.get("gap_type_addressed")
            gate_log_entries.append(log_row)
            if verdict["verdict"] == "TRANSITION_ADMITTED_CANDIDATE":
                admitted_candidates.append(cand)
        new_entry = dict(entry)
        new_entry["documents_canonicalized"] = admitted_candidates
        admitted_by_entry.append(new_entry)

    filtered_shadow_result = dict(shadow_result)
    filtered_shadow_result["results"] = admitted_by_entry

    total_admitted_candidates = sum(len(e["documents_canonicalized"]) for e in admitted_by_entry)
    if total_admitted_candidates == 0:
        admission_summary = None
    else:
        admission_summary = admit_fn(filtered_shadow_result)

    return admission_summary, gate_log_entries, filtered_shadow_result


def main():
    if not SHADOW_RESULT_PATH.exists():
        print(f"[gated-admission] no shadow result at {SHADOW_RESULT_PATH} -- nothing to gate "
              f"or admit (this is a valid, honest outcome, not an error)")
        return 0
    shadow_result = json.loads(SHADOW_RESULT_PATH.read_text(encoding="utf-8"))
    admission_summary, gate_log_entries, _ = run_gated_admission(shadow_result)
    _append_gate_log(gate_log_entries)

    verdict_counts = {}
    for row in gate_log_entries:
        verdict_counts[row["verdict"]] = verdict_counts.get(row["verdict"], 0) + 1
    print(f"[gated-admission] candidates_seen={len(gate_log_entries)} verdict_counts={verdict_counts} "
          f"log_written_to={GATE_LOG_PATH}")
    if admission_summary is None:
        print("[gated-admission] 0 candidates cleared the transition gate -- admission_gate was "
              "NOT called (this is a valid, honest outcome, not an error)")
    else:
        print(f"[admission] candidates_seen={admission_summary['candidates_seen']} "
              f"admitted={admission_summary['admitted']} "
              f"duplicate_existing={admission_summary['duplicate_existing']} "
              f"rejected={admission_summary['rejected']} "
              f"review_required={admission_summary['review_required']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
