# PHASE 5F — Futures Assessment(운영자 지시 40번). Structural Change 단위 통합 평가.
from common import hash_id, cap_confidence
from schema import new_futures_assessment_shell


def build_futures_assessments(structural_change_ids, collections_by_name, ceiling_map):
    out = {}
    for scid in structural_change_ids:
        def _refs_sc(obj, id_field_candidates):
            for f in id_field_candidates:
                if scid in obj.get(f, []):
                    return True
            return (obj.get("target_object_type") == "STRUCTURAL_CHANGE" and
                    obj.get("target_object_id") == scid) or \
                   (obj.get("source_object_type") == "STRUCTURAL_CHANGE" and
                    obj.get("source_object_id") == scid)

        trajectories = {tid: t for tid, t in collections_by_name.get("trajectories", {}).items()
                        if _refs_sc(t, ["supporting_structural_change_ids"])}
        outlooks = {oid: o for oid, o in collections_by_name.get("outlooks", {}).items()
                   if scid in o.get("structural_change_ids", []) or
                   any(tid in trajectories for tid in o.get("trajectory_ids", []))}
        paths = {pid: p for pid, p in collections_by_name.get("alternative_paths", {}).items()
                if any(tid in trajectories for tid in p.get("trajectory_ids", []))}
        scenarios = {sid: s for sid, s in collections_by_name.get("scenarios", {}).items()
                    if scid in s.get("structural_change_ids", []) or
                    any(pid in paths for pid in s.get("alternative_path_ids", []))}
        eff2 = {eid: e for eid, e in collections_by_name.get("second_order_effects", {}).items()
               if _refs_sc(e, [])}
        eff3 = {eid: e for eid, e in collections_by_name.get("third_order_effects", {}).items()
               if e.get("source_second_order_effect_id") in eff2}
        forecasts = {fid: f for fid, f in collections_by_name.get("forecasts", {}).items()
                    if (f.get("target") or {}).get("type") == "STRUCTURAL_CHANGE" and
                    (f.get("target") or {}).get("id") == scid}

        if not any([trajectories, outlooks, paths, scenarios, eff2, eff3, forecasts]):
            continue

        faid = hash_id("fas", scid)
        shell = new_futures_assessment_shell(faid, [scid])
        shell["trajectory_ids"] = sorted(trajectories.keys())
        shell["outlook_ids"] = sorted(outlooks.keys())
        shell["alternative_path_ids"] = sorted(paths.keys())
        shell["scenario_ids"] = sorted(scenarios.keys())
        shell["second_order_effect_ids"] = sorted(eff2.keys())
        shell["third_order_effect_ids"] = sorted(eff3.keys())
        shell["forecast_ids"] = sorted(forecasts.keys())

        counter, uncertainty, assumption, falsifier = set(), set(), set(), set()
        for coll in (trajectories, outlooks, paths, scenarios, eff2, eff3, forecasts):
            for obj in coll.values():
                counter.update(obj.get("counter_evidence_ids", []))
                uncertainty.update(obj.get("uncertainty_ids", []))
                assumption.update(obj.get("assumption_ids", []))
                falsifier.update(obj.get("falsifier_ids", []))
        shell["counter_evidence_ids"] = sorted(counter)
        shell["uncertainty_ids"] = sorted(uncertainty)
        shell["assumption_ids"] = sorted(assumption)
        shell["falsifier_ids"] = sorted(falsifier)
        shell["epistemic_ceiling"] = ceiling_map.get(("STRUCTURAL_CHANGE", scid), "UNKNOWN")
        out[faid] = shell
    return out
