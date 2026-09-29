# PHASE 5D — Bottleneck(운영자 지시 18, 19번). SCARCITY != BOTTLENECK — Scarcity Evidence
# 만으로는 Bottleneck을 생성하지 않는다. 시스템 확장/행동을 실제로 제한한다는 별도
# BOTTLENECK Evidence(affected_system)가 있어야 한다.
from common import hash_id, active_structural_changes, fill_common_evidence
from schema import new_bottleneck_shell


def generate_bottleneck_candidates(evidence_records, structural_changes):
    active = active_structural_changes(structural_changes)
    out = {}
    for rec in evidence_records or []:
        if rec.get("type") != "BOTTLENECK":
            continue
        scid = rec.get("structural_change_id")
        if scid not in active:
            continue
        resource_or_gate, affected_system = rec.get("resource_or_gate"), rec.get("affected_system")
        if not resource_or_gate or not affected_system:
            continue
        bid = hash_id("btl", f"{scid}|{resource_or_gate}|{affected_system}")
        shell = new_bottleneck_shell(bid, resource_or_gate, affected_system, [scid])
        shell["controller_if_known"] = rec.get("controller_if_known")
        shell["dependency_ids"] = list(rec.get("dependency_ids", []))
        shell = fill_common_evidence(shell, rec)
        out[bid] = shell
    return out
