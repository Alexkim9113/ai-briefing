# PHASE 5G — Policy Constraint(운영자 지시 22~25번). Feasibility != Desirability —
# Constraint는 실행 가능성만 기록하며 바람직함을 판단하지 않는다.
from common import hash_id
from schema import new_policy_constraint_shell, CONSTRAINT_TYPES, SEVERITY_LEVELS


def generate_constraint_candidates(evidence_records, policy_options):
    out = {}
    for rec in evidence_records or []:
        if rec.get("type") != "POLICY_CONSTRAINT":
            continue
        oid = rec.get("policy_option_id")
        if oid not in policy_options:
            continue
        constraint_type = rec.get("constraint_type")
        constraint = rec.get("constraint")
        if constraint_type not in CONSTRAINT_TYPES or not constraint:
            continue
        severity = rec.get("severity")
        if severity not in SEVERITY_LEVELS:
            severity = "UNKNOWN"
        cid = hash_id("con", f"{oid}|{constraint_type}|{constraint}")
        shell = new_policy_constraint_shell(cid, oid, constraint_type, constraint, severity)
        shell["supporting_evidence_ids"] = list(rec.get("evidence_ids", []))
        shell["uncertainty_ids"] = list(rec.get("uncertainty_ids", []))
        out[cid] = shell
    return out
