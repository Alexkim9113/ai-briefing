# PHASE 5E — 공통 유틸. CODE ONLY, LLM 미사용.
# 이 Layer도 5D와 동일하게 "이미 구조화된 Evidence/Claim Record"를 검증·분류해 타입 객체로
# 만든다 — 원문 텍스트에서 Contradiction/Assumption 등을 추론하지 않는다(운영자 지시 48번).
import hashlib

VALID_TARGET_TYPES = ("STRUCTURAL_CHANGE", "DRIVER", "DEPENDENCY", "CONTROL", "POWER_SHIFT",
                       "VALUE_SHIFT", "SCARCITY_SHIFT", "BOTTLENECK", "STRUCTURAL_ANALYSIS")


def hash_id(prefix, key):
    return f"{prefix}_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def valid_target(target_object_type, target_object_id, target_index):
    """target_index: {target_object_type: set(existing_ids)}. 5D 대상 객체가 실제 존재할 때만
    5E 객체를 만든다(Acceptance: 5D 대상 없이 5E 객체 없음)."""
    if target_object_type not in VALID_TARGET_TYPES:
        return False
    ids = target_index.get(target_object_type)
    if ids is None:
        return False
    return target_object_id in ids


def confidence_label(evidence_strength, has_counter_evidence):
    """가짜 확률 금지. LOW/MEDIUM/HIGH만."""
    s = evidence_strength - (2 if has_counter_evidence else 0)
    if s >= 5:
        return "HIGH"
    if s >= 2:
        return "MEDIUM"
    return "LOW"


def cap_confidence(confidence, ceiling):
    """운영자 지시 32번 EPISTEMIC CEILING — effective_confidence는 ceiling을 넘을 수 없다.
    ceiling이 UNKNOWN이면 하향 보수적으로 LOW까지만 허용(원인 불명은 확신 근거가 아니다)."""
    order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    if ceiling not in order:
        return "LOW" if order.get(confidence, 0) > 0 else confidence
    return confidence if order.get(confidence, 0) <= order[ceiling] else ceiling


def fill_common_evidence(shell, rec):
    """rec(Evidence/Claim Record)의 공통 필드를 shell에 채운다. Counter Evidence가 있어도
    대상 자체를 삭제하지 않고 confidence만 낮춘다(운영자 지시 6번)."""
    shell["evidence_ids"] = list(rec.get("evidence_ids", []))
    shell["first_seen"] = rec.get("first_seen")
    shell["last_seen"] = rec.get("last_seen")
    strength = len(shell["evidence_ids"])
    shell["evidence_strength"] = strength
    if "confidence" in shell:
        shell["confidence"] = confidence_label(strength, False)
    return shell
