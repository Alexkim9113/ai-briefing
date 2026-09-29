# PHASE 5D — Scarcity Shift(운영자 지시 16, 17, 19번). SCARCITY != PRICE, SCARCITY != VALUE,
# SCARCITY != BOTTLENECK — Scarcity 자체는 시스템 제한 여부와 무관하게 독립적으로 판단한다.
from common import hash_id, active_structural_changes, fill_common_evidence
from schema import new_scarcity_shift_shell


def generate_scarcity_shift_candidates(evidence_records, structural_changes):
    active = active_structural_changes(structural_changes)
    out = {}
    for rec in evidence_records or []:
        if rec.get("type") != "SCARCITY_SHIFT":
            continue
        scid = rec.get("structural_change_id")
        if scid not in active:
            continue
        from_scarcity, to_scarcity = rec.get("from_scarcity"), rec.get("to_scarcity")
        mechanism = rec.get("mechanism")
        if not mechanism or (not from_scarcity and not to_scarcity):
            continue
        ssid = hash_id("scr", f"{scid}|{from_scarcity}|{to_scarcity}|{mechanism}")
        shell = new_scarcity_shift_shell(ssid, from_scarcity, to_scarcity, mechanism, [scid])
        shell["emerging_scarcity"] = list(rec.get("emerging_scarcity", []))
        shell["declining_scarcity"] = list(rec.get("declining_scarcity", []))
        shell = fill_common_evidence(shell, rec)
        out[ssid] = shell
    return out
