# PHASE 5E — Paradox Candidate(운영자 지시 13번). 표면적으로는 반대지만 서로 다른 구조적
# 차원에서 동시에 참일 수 있는 경우. PARADOX_RULE_MATRIX는 candidate 생성용 규칙일 뿐,
# 최종 의미 판단이 아니다 — 절대 자동으로 철학적 해설/내러티브를 만들지 않는다.
from itertools import combinations

from common import hash_id, valid_target
from schema import new_paradox_candidate_shell, PARADOX_RULE_MATRIX
from scope import classify_pair


def generate_paradox_candidates(evidence_records, target_index):
    out = {}
    claims = [rec for rec in (evidence_records or []) if rec.get("type") == "CLAIM"
              and valid_target(rec.get("target_object_type"), rec.get("target_object_id"), target_index)]
    for claim_a, claim_b in combinations(claims, 2):
        category, pair_key, flags = classify_pair(claim_a, claim_b)
        if category != "PARADOX_CANDIDATE":
            continue
        paradox_type = PARADOX_RULE_MATRIX.get(pair_key, "OTHER")
        a_type, a_id = claim_a["target_object_type"], claim_a["target_object_id"]
        b_type, b_id = claim_b["target_object_type"], claim_b["target_object_id"]
        dims = sorted(pair_key) if pair_key else []
        pid = hash_id("pdx", "|".join(sorted([f"{a_type}:{a_id}", f"{b_type}:{b_id}"]) + dims))
        shell = new_paradox_candidate_shell(pid, a_type, a_id, b_type, b_id, paradox_type, dims,
                                             flags.get("scope_match"))
        shell["supporting_evidence_ids"] = sorted(
            set(claim_a.get("evidence_ids", [])) | set(claim_b.get("evidence_ids", [])))
        shell["confidence"] = "LOW"
        out[pid] = shell
    return out
