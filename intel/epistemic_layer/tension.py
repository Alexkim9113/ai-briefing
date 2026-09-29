# PHASE 5E — Tension(운영자 지시 12번). 두 변화가 동시에 참일 수 있지만 구조적으로
# 서로 반대 압력을 만드는 경우. Contradiction과 반드시 분리한다(scope.classify_pair가
# TENSION을 반환한 경우만 사용).
from itertools import combinations

from common import hash_id, valid_target
from schema import new_tension_shell
from scope import classify_pair


def generate_tension_candidates(evidence_records, target_index):
    out = {}
    claims = [rec for rec in (evidence_records or []) if rec.get("type") == "CLAIM"
              and valid_target(rec.get("target_object_type"), rec.get("target_object_id"), target_index)]
    for claim_a, claim_b in combinations(claims, 2):
        category, pair_key, flags = classify_pair(claim_a, claim_b)
        if category != "TENSION":
            continue
        a_type, a_id = claim_a["target_object_type"], claim_a["target_object_id"]
        b_type, b_id = claim_b["target_object_type"], claim_b["target_object_id"]
        dims = sorted(pair_key) if pair_key else []
        tid = hash_id("tns", "|".join(sorted([f"{a_type}:{a_id}", f"{b_type}:{b_id}"]) + dims))
        shell = new_tension_shell(tid, a_type, a_id, b_type, b_id, "STRUCTURAL_TENSION", dims,
                                   "OPPOSING_PRESSURE", flags.get("scope_match"))
        shell["supporting_evidence_ids"] = sorted(
            set(claim_a.get("evidence_ids", [])) | set(claim_b.get("evidence_ids", [])))
        shell["confidence"] = "LOW"
        out[tid] = shell
    return out
