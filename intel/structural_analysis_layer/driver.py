# PHASE 5D — Driver(운영자 지시 4, 5, 6번). Driver != Cause — driver_relation은
# ASSOCIATED_WITH/ENABLES/... 중 하나이며 CAUSAL_CONFIRMED 같은 상태는 쓰지 않는다.
from common import hash_id, active_structural_changes, fill_common_evidence
from schema import new_driver_shell, DRIVER_RELATIONS


def generate_driver_candidates(evidence_records, structural_changes):
    active = active_structural_changes(structural_changes)
    out = {}
    for rec in evidence_records or []:
        if rec.get("type") != "DRIVER":
            continue
        scid = rec.get("structural_change_id")
        if scid not in active:
            continue  # Acceptance 1번: Structural Change 없이 생성 없음
        name, driver_type = rec.get("name"), rec.get("driver_type")
        if not name or not driver_type:
            continue
        relation = rec.get("relation_type", "UNKNOWN")
        if relation not in DRIVER_RELATIONS:
            relation = "UNKNOWN"  # 매핑 불가 시 억지 분류 금지
        did = hash_id("drv", f"{scid}|{name}|{driver_type}")
        shell = new_driver_shell(did, name, driver_type, [scid], relation)
        shell = fill_common_evidence(shell, rec)
        out[did] = shell
    return out
