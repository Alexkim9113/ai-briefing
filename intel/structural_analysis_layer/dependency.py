# PHASE 5D — Dependency(운영자 지시 7, 9번). Dependency != Control — Dependency Evidence
# 만으로는 Control을 생성하지 않는다(control.py는 별도 CONTROL Evidence를 요구).
from common import hash_id, active_structural_changes, fill_common_evidence
from schema import new_dependency_shell, DEPENDENCY_TYPES, DEPENDENCY_DIRECTIONS


def generate_dependency_candidates(evidence_records, structural_changes):
    active = active_structural_changes(structural_changes)
    out = {}
    for rec in evidence_records or []:
        if rec.get("type") != "DEPENDENCY":
            continue
        scid = rec.get("structural_change_id")
        if scid not in active:
            continue
        actor, target, function = rec.get("dependent_actor"), rec.get("dependency_target"), rec.get("dependency_function")
        if not actor or not target or not function:
            continue
        dep_type = rec.get("dependency_type", "OTHER")
        if dep_type not in DEPENDENCY_TYPES:
            dep_type = "OTHER"
        did = hash_id("dep", f"{scid}|{actor}|{target}|{function}")
        shell = new_dependency_shell(did, actor, target, function, dep_type, [scid])
        shell["strength"] = rec.get("strength", "LOW")
        direction = rec.get("direction", "UNKNOWN")
        shell["direction"] = direction if direction in DEPENDENCY_DIRECTIONS else "UNKNOWN"
        shell = fill_common_evidence(shell, rec)
        out[did] = shell
    return out
