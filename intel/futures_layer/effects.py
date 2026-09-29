# PHASE 5F — Second/Third-order Effect(운영자 지시 23~31, 46번). 2차/3차 효과는 Observed
# Fact가 아니라 HYPOTHESIS_CANDIDATE다. 명시적 mechanism chain(SOURCE→MECHANISM→EFFECT)이
# 없으면 생성하지 않는다("A happened therefore Z" leap 금지). Depth Limit: 3차까지만
# (4차 이상을 만드는 함수 자체를 이 모듈에 두지 않는다).
from common import hash_id, cap_confidence
from schema import new_second_order_effect_shell, new_third_order_effect_shell, REAL_DOMAINS
from speculation import compute_speculation_level, apply_speculation_ceiling


def generate_second_order_effects(evidence_records, target_index, ceiling_map):
    out = {}
    for rec in evidence_records or []:
        if rec.get("type") != "SECOND_ORDER_EFFECT":
            continue
        source_type, source_id = rec.get("source_object_type"), rec.get("source_object_id")
        from common import valid_target
        if not valid_target(source_type, source_id, target_index):
            continue  # 5E 우회 금지 — source도 Epistemic Assessment가 있는 대상이어야 함
        mechanism = rec.get("mechanism")
        effect_type = rec.get("effect_type")
        if not mechanism or not effect_type:
            continue  # 명시적 mechanism 없는 leap 금지
        affected_domain = rec.get("affected_domain")
        if affected_domain not in REAL_DOMAINS:
            continue  # Domain != Event Type — 실제 Domain 기준만 허용
        eid = hash_id("eff2", f"{source_type}|{source_id}|{effect_type}|{mechanism}")
        shell = new_second_order_effect_shell(eid, source_type, source_id, effect_type,
                                               affected_domain, mechanism, list(rec.get("required_conditions", [])))
        shell["supporting_evidence_ids"] = list(rec.get("evidence_ids", []))
        shell["counter_evidence_ids"] = list(rec.get("counter_evidence_ids", []))
        shell["uncertainty_ids"] = list(rec.get("uncertainty_ids", []))
        shell["analogy_ids"] = list(rec.get("analogy_ids", []))

        ceiling = ceiling_map.get((source_type, source_id), "UNKNOWN")
        shell["epistemic_ceiling"] = ceiling
        speculation = compute_speculation_level(lineage_distance=3, assumption_count=0, unsupported_transitions=0)
        shell["speculation_level"] = speculation
        confidence = cap_confidence("LOW", ceiling)
        shell["confidence"] = apply_speculation_ceiling(confidence, speculation, ceiling)
        out[eid] = shell
    return out


def generate_third_order_effects(evidence_records, second_order_effects, ceiling_map):
    out = {}
    for rec in evidence_records or []:
        if rec.get("type") != "THIRD_ORDER_EFFECT":
            continue
        source_2nd_id = rec.get("source_second_order_effect_id")
        if source_2nd_id not in second_order_effects:
            continue  # Depth Limit — 존재하는 2차 효과 위에서만 3차 효과 생성(4차 이상 없음)
        mechanism = rec.get("mechanism")
        effect_type = rec.get("effect_type")
        if not mechanism or not effect_type:
            continue
        affected_domains = list(rec.get("affected_domains", []))
        if not affected_domains or any(d not in REAL_DOMAINS for d in affected_domains):
            continue
        eid = hash_id("eff3", f"{source_2nd_id}|{effect_type}|{mechanism}")
        shell = new_third_order_effect_shell(eid, source_2nd_id, effect_type, affected_domains,
                                              mechanism, list(rec.get("required_conditions", [])))
        shell["supporting_evidence_ids"] = list(rec.get("evidence_ids", []))
        shell["counter_evidence_ids"] = list(rec.get("counter_evidence_ids", []))
        shell["uncertainty_ids"] = list(rec.get("uncertainty_ids", []))
        shell["analogy_ids"] = list(rec.get("analogy_ids", []))

        ceiling = second_order_effects[source_2nd_id].get("epistemic_ceiling", "UNKNOWN")
        shell["epistemic_ceiling"] = ceiling
        speculation = "HIGH"  # 3차 효과는 lineage distance가 가장 길다(운영자 지시 47번)
        shell["speculation_level"] = speculation
        confidence = cap_confidence("LOW", ceiling)
        shell["confidence"] = apply_speculation_ceiling(confidence, speculation, ceiling)
        out[eid] = shell
    return out
