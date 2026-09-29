# PHASE 5E — Assumption(운영자 지시 18번). 명시적 Evidence Record에서만 생성 — LLM 추측 금지.
from common import hash_id, valid_target
from schema import new_assumption_shell


def generate_assumption_candidates(evidence_records, target_index):
    out = {}
    for rec in evidence_records or []:
        if rec.get("type") != "ASSUMPTION":
            continue
        target_type, target_id = rec.get("target_object_type"), rec.get("target_object_id")
        if not valid_target(target_type, target_id, target_index):
            continue
        statement = rec.get("assumption_statement")
        assumption_type = rec.get("assumption_type")
        if not statement or not assumption_type:
            continue
        aid = hash_id("asm", f"{target_type}|{target_id}|{assumption_type}|{statement}")
        shell = new_assumption_shell(aid, target_type, target_id, assumption_type, statement,
                                      bool(rec.get("required_for_interpretation", False)))
        shell["supporting_evidence_ids"] = list(rec.get("supporting_evidence_ids", []))
        shell["challenging_evidence_ids"] = list(rec.get("challenging_evidence_ids", []))
        if shell["challenging_evidence_ids"]:
            shell["evidence_status"] = "CHALLENGED"
        elif shell["supporting_evidence_ids"]:
            shell["evidence_status"] = "SUPPORTED"
        shell["evidence_ids"] = sorted(set(shell["supporting_evidence_ids"]) | set(shell["challenging_evidence_ids"]))
        shell["first_seen"] = rec.get("first_seen")
        shell["last_seen"] = rec.get("last_seen")
        out[aid] = shell
    return out
