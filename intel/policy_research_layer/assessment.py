# PHASE 5G — Policy Research Assessment(운영자 지시 62번). Structural Change 단위 통합 평가.
from common import hash_id
from schema import new_policy_research_assessment_shell


def build_policy_research_assessments(structural_change_ids, futures_assessment_map, collections, ceiling_map):
    out = {}
    for scid in structural_change_ids:
        pqs = {pid: pq for pid, pq in collections.get("policy_questions", {}).items()
              if scid in pq.get("target_structural_change_ids", [])}
        opts = {oid: o for oid, o in collections.get("policy_options", {}).items()
               if o.get("policy_question_id") in pqs}
        tradeoffs = {tid: t for tid, t in collections.get("policy_tradeoffs", {}).items()
                    if t.get("policy_option_id") in opts}
        stakeholders = {sid: s for sid, s in collections.get("stakeholder_impacts", {}).items()
                       if s.get("policy_option_id") in opts}
        constraints = {cid: c for cid, c in collections.get("policy_constraints", {}).items()
                      if c.get("policy_option_id") in opts}
        policy_unc = {uid: u for uid, u in collections.get("policy_uncertainties", {}).items()
                     if u.get("policy_question_id") in pqs or u.get("policy_option_id") in opts}
        rqs = {rid: r for rid, r in collections.get("research_questions", {}).items()
              if any(pqid in pqs for pqid in r.get("related_policy_question_ids", []))}
        rgaps = {gid: g for gid, g in collections.get("research_gaps", {}).items()
                if g.get("target_object_type") == "STRUCTURAL_CHANGE" and g.get("target_object_id") == scid}
        eneeds = {eid: e for eid, e in collections.get("evidence_needs", {}).items()
                 if any(rid in rqs for rid in e.get("related_research_question_ids", [])) or
                 any(pqid in pqs for pqid in e.get("related_policy_question_ids", []))}
        mons = {mid: m for mid, m in collections.get("monitoring_indicators", {}).items()
               if m.get("target_object_type") == "STRUCTURAL_CHANGE" and m.get("target_object_id") == scid}

        if not any([pqs, opts, tradeoffs, stakeholders, constraints, policy_unc, rqs, rgaps, eneeds, mons]):
            continue

        faids = futures_assessment_map.get(scid, [])
        paid = hash_id("pra", scid)
        shell = new_policy_research_assessment_shell(paid, faids, [scid])
        shell["policy_question_ids"] = sorted(pqs.keys())
        shell["policy_option_ids"] = sorted(opts.keys())
        shell["tradeoff_ids"] = sorted(tradeoffs.keys())
        shell["stakeholder_impact_ids"] = sorted(stakeholders.keys())
        shell["constraint_ids"] = sorted(constraints.keys())
        shell["policy_uncertainty_ids"] = sorted(policy_unc.keys())
        shell["research_question_ids"] = sorted(rqs.keys())
        shell["research_gap_ids"] = sorted(rgaps.keys())
        shell["evidence_need_ids"] = sorted(eneeds.keys())
        shell["monitoring_indicator_ids"] = sorted(mons.keys())

        counter, uncertainty, assumption, falsifier, domains, jurisdictions = set(), set(), set(), set(), set(), set()
        for coll in (pqs, opts, tradeoffs, stakeholders, policy_unc):
            for obj in coll.values():
                counter.update(obj.get("counter_evidence_ids", []))
                uncertainty.update(obj.get("uncertainty_ids", []))
                assumption.update(obj.get("assumption_ids", []))
                falsifier.update(obj.get("falsifier_ids", []))
                if "affected_domains" in obj:
                    domains.update(obj.get("affected_domains", []))
                if "jurisdiction" in obj:
                    jurisdictions.add(obj["jurisdiction"])
        shell["counter_evidence_ids"] = sorted(counter)
        shell["uncertainty_ids"] = sorted(uncertainty)
        shell["assumption_ids"] = sorted(assumption)
        shell["falsifier_ids"] = sorted(falsifier)
        shell["domains"] = sorted(domains)
        shell["jurisdictions"] = sorted(jurisdictions)
        shell["epistemic_ceiling"] = ceiling_map.get(("STRUCTURAL_CHANGE", scid), "UNKNOWN")
        out[paid] = shell
    return out
