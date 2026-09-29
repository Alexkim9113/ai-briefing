# PHASE 5E — Epistemic Assessment(운영자 지시 27~34번). 대상 객체별 통합 평가.
# Epistemic Ceiling: 하위 Evidence 품질이 허용하는 수준을 넘어 상위 확신이 자동으로
# 올라가지 않게 한다("certainty laundering" 방지, 운영자 지시 32~33번).
from common import hash_id, cap_confidence
from schema import new_epistemic_assessment_shell

_CEILING_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "UNKNOWN": -1}


def compute_epistemic_ceiling(ceiling_records, target_type, target_id):
    """명시적으로 제공된 EPISTEMIC_CEILING 레코드에서만 계산한다 — 추정/기본 HIGH 금지.
    레코드가 없거나 source_independence_known이 False면 UNKNOWN(운영자 지시 34번:
    Source Independence 미확인 -> 확신 상한을 임의로 올리지 않는다)."""
    for rec in ceiling_records or []:
        if rec.get("target_object_type") == target_type and rec.get("target_object_id") == target_id:
            upstream_confidence = rec.get("upstream_confidence")
            source_independence_known = rec.get("source_independence_known")
            if not source_independence_known or upstream_confidence not in ("LOW", "MEDIUM", "HIGH"):
                return "UNKNOWN"
            return upstream_confidence
    return "UNKNOWN"


def build_epistemic_assessments(target_objects, collections_by_name, ceiling_records):
    """target_objects: {(target_type, target_id): declared_confidence_before or None}.
    collections_by_name: {"counter_evidence": {...}, "contradictions": {...}, ...} — 각
    객체는 target_object_type/target_object_id 또는 object_a_*/object_b_* 필드를 갖는다."""
    out = {}
    for (target_type, target_id), confidence_before in target_objects.items():
        eaid = hash_id("eas", f"{target_type}|{target_id}")
        shell = new_epistemic_assessment_shell(eaid, target_type, target_id)

        def _belongs(obj):
            if obj.get("target_object_type") == target_type and obj.get("target_object_id") == target_id:
                return True
            pair_match = ((obj.get("object_a_type") == target_type and obj.get("object_a_id") == target_id) or
                          (obj.get("object_b_type") == target_type and obj.get("object_b_id") == target_id))
            return pair_match

        ce = [o for o in collections_by_name.get("counter_evidence", {}).values() if _belongs(o)]
        ctd = [o for o in collections_by_name.get("contradictions", {}).values() if _belongs(o)]
        tns = [o for o in collections_by_name.get("tensions", {}).values() if _belongs(o)]
        pdx = [o for o in collections_by_name.get("paradox_candidates", {}).values() if _belongs(o)]
        unc = [o for o in collections_by_name.get("uncertainties", {}).values() if _belongs(o)]
        asm = [o for o in collections_by_name.get("assumptions", {}).values() if _belongs(o)]
        fls = [o for o in collections_by_name.get("falsifiers", {}).values() if _belongs(o)]
        gap = [o for o in collections_by_name.get("evidence_gaps", {}).values() if _belongs(o)]
        alt = [o for o in collections_by_name.get("alternative_explanations", {}).values() if _belongs(o)]

        shell["counter_evidence_count"] = len(ce)
        shell["supporting_evidence_count"] = sum(len(o.get("evidence_ids", [])) for o in
                                                  collections_by_name.get("_supporting", {}).get(
                                                      (target_type, target_id), []))
        shell["contradiction_ids"] = sorted(o["contradiction_id"] for o in ctd)
        shell["tension_ids"] = sorted(o["tension_id"] for o in tns)
        shell["paradox_candidate_ids"] = sorted(o["paradox_candidate_id"] for o in pdx)
        shell["uncertainty_ids"] = sorted(o["uncertainty_id"] for o in unc)
        shell["assumption_ids"] = sorted(o["assumption_id"] for o in asm)
        shell["falsifier_ids"] = sorted(o["falsifier_id"] for o in fls)
        shell["evidence_gap_ids"] = sorted(o["evidence_gap_id"] for o in gap)
        shell["alternative_explanation_ids"] = sorted(o["alternative_explanation_id"] for o in alt)

        confidence_before = confidence_before or "LOW"
        shell["confidence_before"] = confidence_before
        ceiling = compute_epistemic_ceiling(ceiling_records, target_type, target_id)
        shell["epistemic_ceiling"] = ceiling

        # 미해결 Contradiction/HIGH Uncertainty가 있으면 확신을 낮춘다; Ceiling을 넘지 않는다.
        confidence_after = confidence_before
        if any(c.get("status") == "AUTO_CANDIDATE" and c.get("conflict_type") == "DIRECT_CONTRADICTION"
               for c in ctd):
            confidence_after = "LOW"
        confidence_after = cap_confidence(confidence_after, ceiling)
        shell["confidence_after"] = confidence_after
        out[eaid] = shell
    return out
