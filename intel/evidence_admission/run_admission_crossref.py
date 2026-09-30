#!/usr/bin/env python3
# PHASE M.5D -- CLI entry point for the Crossref admission-gate shadow job. Mirrors
# run_admission.py exactly, pointed at the Crossref connector's shadow result instead of
# Federal Register's. Reads the shadow result file (never the raw fetcher output directly)
# and runs it through the same, unforked admission_gate.admit_shadow_result(). Zero LLM.
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import admission_gate  # noqa: E402

SHADOW_RESULT_PATH = HERE.parent / "historical_acquisition" / "crossref_pilot_result.json"


def main():
    if not SHADOW_RESULT_PATH.exists():
        print(f"[admission] no shadow result at {SHADOW_RESULT_PATH} -- nothing to admit "
              f"(this is a valid, honest outcome, not an error)")
        return 0
    shadow_result = json.loads(SHADOW_RESULT_PATH.read_text(encoding="utf-8"))
    summary = admission_gate.admit_shadow_result(shadow_result)
    print(f"[admission] candidates_seen={summary['candidates_seen']} "
          f"admitted={summary['admitted']} duplicate_existing={summary['duplicate_existing']} "
          f"rejected={summary['rejected']} review_required={summary['review_required']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
