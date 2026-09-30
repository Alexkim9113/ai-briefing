# PHASE M.2 — historical evidence source independence adapter. Same exact reasoning and
# pattern as intel/pattern_layer/source_independence_gate.py: does NOT build a new
# independence system, adapts intel/operator_brain/source_independence.py's existing
# INDEPENDENT/LIKELY_INDEPENDENT/SHARED_ORIGIN/DERIVED_FROM_SAME_SOURCE/UNKNOWN vocabulary and
# assess_independence() union-find, loaded via the same importlib isolation
# private_api/loader.py uses for cross-package imports that would otherwise collide.
#
# Purpose: N HistoricalEvidence records that all cite the same underlying book/paper/
# press-release must not count as N independent confirmations for analogy evidence
# sufficiency. UNKNOWN provenance must never be silently treated as independent - this falls
# straight out of assess_independence()'s own pairwise_status() logic (a trail entry with
# found=False, or no canonical_url/source_id, can only ever produce UNKNOWN, never
# INDEPENDENT), which this adapter does not alter.
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
OPERATOR_BRAIN_DIR = INTEL_DIR / "operator_brain"


def _load_isolated(path, unique_name):
    key = f"_foresight_engine_isolated__{unique_name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_source_independence():
    return _load_isolated(OPERATOR_BRAIN_DIR / "source_independence.py", "source_independence")


def _trail_entry(evidence):
    """A HistoricalEvidence record -> one provenance trail entry. `found` is True only when the
    record actually carries a real source identifier (source_id or canonical_url) - a record
    with neither (evidence_status == REJECTED_NO_SOURCE, or UNKNOWN provenance fields left
    unset) is `found: False`, which assess_independence()'s pairwise_status() can only ever
    resolve to UNKNOWN - never INDEPENDENT. This is the mechanism that keeps UNKNOWN
    provenance from silently inflating independence."""
    source_id = evidence.get("source_id")
    canonical_url = evidence.get("canonical_url")
    found = bool(source_id) or bool(canonical_url)
    return {
        "document_id": source_id,
        "canonical_url": canonical_url,
        "found": found,
    }


def independence_families(evidence_ids, evidence_by_id, reports_on_pairs=None):
    """Groups the given evidence_ids into independent-source families. Two evidence records
    that cite the exact same source_id, or the exact same canonical_url, or the same domain,
    collapse into one family - mirroring pattern_layer's change-level adapter exactly, applied
    to historical evidence instead of pattern-layer changes."""
    si = _load_source_independence()
    trails = [(eid, [_trail_entry(evidence_by_id[eid])]) for eid in evidence_ids if eid in evidence_by_id]
    if not trails:
        return {"overall_status": "UNKNOWN", "pair_statuses": {}, "evidence_family_count": 0, "families": []}
    return si.assess_independence(trails, reports_on_pairs=reports_on_pairs or set())


def independent_evidence_count(evidence_ids, evidence_by_id, reports_on_pairs=None):
    """<= len(evidence_ids) always - additive-only, never inflates the raw count. UNKNOWN
    provenance (found=False) is its own singleton family per record (assess_independence never
    unions on UNKNOWN), so it is counted at face value, not silently trusted as independently
    verified - callers must separately check evidence_status/confidence before treating an
    UNKNOWN-provenance record as strong support."""
    valid_ids = [eid for eid in evidence_ids if eid in evidence_by_id]
    if len(valid_ids) <= 1:
        return len(valid_ids)
    result = independence_families(valid_ids, evidence_by_id, reports_on_pairs)
    return result["evidence_family_count"]
