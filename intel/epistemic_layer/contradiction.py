# PHASE 5E — Contradiction(운영자 지시 8~11번). Scope Guard를 통과해야만
# DIRECT_CONTRADICTION이 된다. Temporal/Geographic/Population Guard가 막으면
# TEMPORAL_REVERSAL_CANDIDATE/NO_DIRECT_CONTRADICTION/CONTEXT_DEPENDENT로만 남는다 —
# 절대로 방향이 반대라는 이유만으로 Contradiction을 만들지 않는다.
from itertools import combinations

from common import hash_id, valid_target, fill_common_evidence
from schema import new_contradiction_shell
from scope import classify_pair

SEVERITY_BY_CONFLICT = {"DIRECT_CONTRADICTION": "HIGH", "CONTEXT_DEPENDENT": "MEDIUM"}


def _claims(evidence_records, target_index):
    claims = []
    for rec in evidence_records or []:
        if rec.get("type") != "CLAIM":
            continue
        if not valid_target(rec.get("target_object_type"), rec.get("target_object_id"), target_index):
            continue
        claims.append(rec)
    return claims


def generate_contradiction_candidates(evidence_records, target_index):
    out = {}
    claims = _claims(evidence_records, target_index)
    for claim_a, claim_b in combinations(claims, 2):
        category, dimension, flags = classify_pair(claim_a, claim_b)
        if category not in ("DIRECT_CONTRADICTION", "TEMPORAL_REVERSAL_CANDIDATE",
                             "NO_DIRECT_CONTRADICTION", "CONTEXT_DEPENDENT"):
            continue
        a_type, a_id = claim_a["target_object_type"], claim_a["target_object_id"]
        b_type, b_id = claim_b["target_object_type"], claim_b["target_object_id"]
        cid = hash_id("ctd", "|".join(sorted([f"{a_type}:{a_id}", f"{b_type}:{b_id}", str(dimension)])))
        severity = SEVERITY_BY_CONFLICT.get(category, "LOW")
        shell = new_contradiction_shell(cid, a_type, a_id, b_type, b_id, dimension, flags, category, severity)
        shell["evidence_ids"] = sorted(set(claim_a.get("evidence_ids", [])) | set(claim_b.get("evidence_ids", [])))
        shell["confidence"] = "HIGH" if category == "DIRECT_CONTRADICTION" else "LOW"
        out[cid] = shell
    return out
