# PHASE 5D — 공통 유틸(운영자 지시 25, 27번). CODE ONLY.
# 이 Layer의 "Candidate Generation"은 텍스트/키워드에서 관계를 추론하는 것이 아니라, 이미
# 구조화된 Evidence Record(상위 Layer 또는 사람이 명시적으로 제공한 구조적 사실)를 검증·정리해
# 타입 객체로 만드는 것이다 — 아직 Dependency/Control/Power 등을 자동 추출하는 NLP/LLM
# 파이프라인이 없으므로, Evidence 없이 자동 생성하지 않는다는 원칙(운영자 지시 4번)을 이렇게
# 충족한다. 실제 Production은 Structural Change=0이므로 Evidence Record도 없고, 따라서
# 이 Layer의 모든 산출물은 0이다.
import hashlib


def hash_id(prefix, key):
    return f"{prefix}_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def active_structural_changes(structural_changes):
    return {scid: sc for scid, sc in (structural_changes or {}).items()
            if sc.get("status") != "REJECTED" and sc.get("override_status") != "HUMAN_REJECTED"}


def confidence_label(evidence_strength, has_counter_evidence):
    """가짜 확률 금지(운영자 지시 25번). LOW/MEDIUM/HIGH만."""
    s = evidence_strength - (2 if has_counter_evidence else 0)
    if s >= 5:
        return "HIGH"
    if s >= 2:
        return "MEDIUM"
    return "LOW"


def fill_common_evidence(shell, rec):
    """rec(Evidence Record)의 공통 필드를 shell에 채운다. counter_evidence_ids가 있어도
    객체 자체는 삭제하지 않고 confidence만 낮춘다(운영자 지시 27번)."""
    shell["supporting_pattern_ids"] = list(rec.get("supporting_pattern_ids", []))
    shell["supporting_change_ids"] = list(rec.get("supporting_change_ids", []))
    shell["supporting_event_ids"] = list(rec.get("supporting_event_ids", []))
    shell["counter_evidence_ids"] = list(rec.get("counter_evidence_ids", []))
    shell["domains"] = list(rec.get("domains", []))
    shell["entities"] = list(rec.get("entities", []))
    shell["institutions"] = list(rec.get("institutions", []))
    shell["resources"] = list(rec.get("resources", []))
    shell["first_seen"] = rec.get("first_seen")
    shell["last_seen"] = rec.get("last_seen")
    strength = (len(shell["supporting_pattern_ids"]) + len(shell["supporting_change_ids"])
                + len(shell["supporting_event_ids"]))
    shell["evidence_strength"] = strength
    shell["confidence"] = confidence_label(strength, bool(shell["counter_evidence_ids"]))
    return shell
