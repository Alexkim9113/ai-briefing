# PHASE 5G — 공통 유틸. CODE ONLY, LLM 미사용.
import hashlib


def hash_id(prefix, key):
    return f"{prefix}_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def valid_structural_change(scid, target_index):
    """target_index는 '5F Futures Assessment가 실제로 존재하는' Structural Change만 담는다 —
    5F를 우회한 Policy/Research 객체 생성을 막는다(운영자 지시 2번: 5G는 반드시 5F를 통과)."""
    return scid in (target_index or {}).get("STRUCTURAL_CHANGE", set())


def valid_target(target_object_type, target_object_id, target_index):
    ids = (target_index or {}).get(target_object_type)
    if not ids:
        return False
    return target_object_id in ids


def cap_confidence(confidence, ceiling):
    order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    if ceiling not in order:
        return "LOW" if order.get(confidence, 0) > 0 else confidence
    return confidence if order.get(confidence, 0) <= order[ceiling] else ceiling
