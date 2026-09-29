# PHASE 5D — Control(운영자 지시 9, 10번). Control은 Dependency와 별도의 Evidence(실제
# 통제 메커니즘 근거)가 있어야만 생성된다 — Dependency 하나만으로 Control을 추정하지 않는다.
from common import hash_id, active_structural_changes, fill_common_evidence
from schema import new_control_shell


def generate_control_candidates(evidence_records, structural_changes):
    active = active_structural_changes(structural_changes)
    out = {}
    for rec in evidence_records or []:
        if rec.get("type") != "CONTROL":
            continue
        scid = rec.get("structural_change_id")
        if scid not in active:
            continue
        controller, resource, mechanism = (rec.get("controller"), rec.get("controlled_resource_or_access"),
                                            rec.get("control_mechanism"))
        if not controller or not resource or not mechanism:
            continue
        cid = hash_id("ctl", f"{scid}|{controller}|{resource}|{mechanism}")
        shell = new_control_shell(cid, controller, resource, mechanism, [scid])
        shell["affected_actors"] = list(rec.get("affected_actors", []))
        shell = fill_common_evidence(shell, rec)
        out[cid] = shell
    return out
