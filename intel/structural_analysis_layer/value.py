# PHASE 5D — Value Shift(운영자 지시 14, 15, 19번). VALUE != REVENUE, VALUE != SCARCITY —
# 사전 지식으로 자동 생성하지 않고 명시적 VALUE Evidence Record만 후보로 만든다.
from common import hash_id, active_structural_changes, fill_common_evidence
from schema import new_value_shift_shell, VALUE_DIRECTIONS, VALUE_TYPES


def generate_value_shift_candidates(evidence_records, structural_changes):
    active = active_structural_changes(structural_changes)
    out = {}
    for rec in evidence_records or []:
        if rec.get("type") != "VALUE_SHIFT":
            continue
        scid = rec.get("structural_change_id")
        if scid not in active:
            continue
        value_object, mechanism = rec.get("value_object"), rec.get("mechanism")
        if not value_object or not mechanism:
            continue
        direction = rec.get("direction", "UNKNOWN")
        if direction not in VALUE_DIRECTIONS:
            direction = "UNKNOWN"
        value_type = rec.get("value_type", "OTHER")
        if value_type not in VALUE_TYPES:
            value_type = "OTHER"
        vid = hash_id("val", f"{scid}|{value_object}|{mechanism}")
        shell = new_value_shift_shell(vid, value_object, direction, value_type, mechanism, [scid])
        shell = fill_common_evidence(shell, rec)
        out[vid] = shell
    return out
