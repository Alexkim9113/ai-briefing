#!/usr/bin/env python3
# PHASE M.5C -- CLI entry point for the admission-gate shadow job. Reads the Federal Register
# connector's shadow result file (never the raw fetcher output directly -- only through the
# committed JSON file, so calling the connector alone can never itself touch documents.json)
# and runs it through admission_gate.admit_shadow_result(), the ONLY function allowed to write
# intel/documents.json. Zero LLM.
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import admission_gate  # noqa: E402

SHADOW_RESULT_PATH = HERE.parent / "historical_acquisition" / "federal_register_pilot_result.json"


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
