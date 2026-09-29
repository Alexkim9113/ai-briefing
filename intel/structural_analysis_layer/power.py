# PHASE 5D — Power(운영자 지시 11, 12, 13, 21번). Power는 독립 점수가 아니라 관계 구조
# (Dependency + Control이 같은 Structural Change에서 같은 대상을 가리킬 때)에서 후보로
# 나타난다. 자동 확정은 하지 않는다(status는 그대로 RULE_CANDIDATE).
from common import hash_id, active_structural_changes
from schema import new_power_shift_shell, POWER_RESOURCES

_DEPENDENCY_TO_POWER_RESOURCE = {
    "COMPUTE": "COMPUTE", "DATA": "DATA", "ENERGY": "ENERGY", "CAPITAL": "CAPITAL",
    "PLATFORM": "PLATFORM", "DISTRIBUTION": "DISTRIBUTION", "LEGAL_PERMISSION": "PERMISSION",
    "AUTHENTICATION": "AUTHENTICATION", "STANDARD": "STANDARD_SETTING", "KNOWLEDGE": "INFORMATION",
    "INFRASTRUCTURE": "INFRASTRUCTURE", "TRUST": "TRUST",
}


def _power_resource_for(dependency_type):
    r = _DEPENDENCY_TO_POWER_RESOURCE.get(dependency_type, "OTHER")
    return r if r in POWER_RESOURCES else "OTHER"


def generate_power_shift_candidates(dependencies, controls, structural_changes, evidence_records=None):
    """Dependency.dependency_target == Control.controller 이고 같은 Structural Change를
    공유할 때만 Power Shift 후보 생성(운영자 지시 21번: 자동 확정 아니라 candidate만).
    gainers/losers는 별도 POWER_SHIFT_EVIDENCE 레코드가 명시한 경우에만 채운다(운영자
    지시 12번: Evidence 없으면 [])."""
    active = active_structural_changes(structural_changes)
    gainer_loser = {}
    for rec in evidence_records or []:
        if rec.get("type") == "POWER_SHIFT_EVIDENCE":
            gainer_loser[rec["structural_change_id"]] = {
                "gainers": list(rec.get("gainers", [])), "losers": list(rec.get("losers", []))}

    out = {}
    for did, dep in (dependencies or {}).items():
        if dep.get("status") == "HUMAN_REJECTED" or dep.get("override_status") == "HUMAN_REJECTED":
            continue
        for scid in dep.get("supporting_structural_change_ids", []):
            if scid not in active:
                continue
            for cid, ctrl in (controls or {}).items():
                if ctrl.get("status") == "HUMAN_REJECTED" or ctrl.get("override_status") == "HUMAN_REJECTED":
                    continue
                if scid not in ctrl.get("supporting_structural_change_ids", []):
                    continue
                if ctrl.get("controller") != dep.get("dependency_target"):
                    continue  # Dependency 대상과 Control 주체가 일치해야 관계 구조 성립

                psid = hash_id("pow", f"{scid}|{did}|{cid}")
                shell = new_power_shift_shell(
                    psid, dep.get("dependent_actor"), ctrl.get("controller"),
                    _power_resource_for(dep.get("dependency_type")), ctrl.get("control_mechanism"), [scid])
                gl = gainer_loser.get(scid, {"gainers": [], "losers": []})
                shell["gainers"], shell["losers"] = gl["gainers"], gl["losers"]
                shell["supporting_dependency_ids"] = [did]
                shell["supporting_control_ids"] = [cid]
                shell["supporting_pattern_ids"] = sorted(set(dep.get("supporting_pattern_ids", [])
                                                              + ctrl.get("supporting_pattern_ids", [])))
                shell["supporting_change_ids"] = sorted(set(dep.get("supporting_change_ids", [])
                                                             + ctrl.get("supporting_change_ids", [])))
                shell["supporting_event_ids"] = sorted(set(dep.get("supporting_event_ids", [])
                                                            + ctrl.get("supporting_event_ids", [])))
                strength = len(shell["supporting_pattern_ids"]) + len(shell["supporting_change_ids"]) + 1
                shell["evidence_strength"] = strength
                shell["confidence"] = "MEDIUM" if strength >= 3 else "LOW"
                out[psid] = shell
    return out
