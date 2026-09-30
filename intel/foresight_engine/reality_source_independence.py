# PHASE M.3 — indicator source independence adapter. Fourth copy of the same exact pattern as
# operator_brain/source_independence.py's original, pattern_layer/source_independence_gate.py,
# and foresight_engine/historical_source_independence.py. Does NOT alter the original.
#
# Lighter-weight application than the other three by design decision: at pilot scale (a
# handful of indicators, 0 live-fetched observations due to the sandbox network block - see
# run_reality_pilot.py), there is no real multi-source data-conflict case yet to collapse
# families over. This module is still provided as a real, callable function (not just a
# comment) so that when two indicators reporting the same concept from different-looking
# source_ids turn out to share an underlying release/organization, N of them are not counted
# as N independent confirmations.
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


def _trail_entry(indicator):
    """An Indicator record -> one provenance trail entry. found=True only with a real
    source_id/canonical_url - matches the exact reasoning in historical_source_independence.py:
    UNKNOWN provenance can never resolve to INDEPENDENT via assess_independence()."""
    source_id = indicator.get("source_id")
    canonical_url = indicator.get("canonical_url")
    found = bool(source_id) or bool(canonical_url)
    return {"document_id": source_id, "canonical_url": canonical_url, "found": found}


def indicator_independence_families(indicator_ids, indicators_by_id, reports_on_pairs=None):
    si = _load_source_independence()
    trails = [(iid, [_trail_entry(indicators_by_id[iid])])
              for iid in indicator_ids if iid in indicators_by_id]
    if not trails:
        return {"overall_status": "UNKNOWN", "pair_statuses": {}, "evidence_family_count": 0, "families": []}
    return si.assess_independence(trails, reports_on_pairs=reports_on_pairs or set())


def independent_indicator_count(indicator_ids, indicators_by_id, reports_on_pairs=None):
    valid_ids = [iid for iid in indicator_ids if iid in indicators_by_id]
    if len(valid_ids) <= 1:
        return len(valid_ids)
    result = indicator_independence_families(valid_ids, indicators_by_id, reports_on_pairs)
    return result["evidence_family_count"]
