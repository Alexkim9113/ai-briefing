# 공통 유틸. hash_id는 기존 Layer들과 동일한 멱등성 패턴(재실행해도 같은 id).
import hashlib


def hash_id(prefix, key):
    return f"{prefix}_" + hashlib.sha1(key.encode("utf-8", "ignore")).hexdigest()[:16]


def text_hash(text):
    return hashlib.sha1((text or "").encode("utf-8", "ignore")).hexdigest()[:16]


def content_hash_for_cache(text, version):
    """Gemini 캐시 키(섹션 23): content_hash + evidence_processing_version."""
    return hashlib.sha1(f"{text or ''}|{version}".encode("utf-8", "ignore")).hexdigest()[:16]


def confidence_from_strength(strength, has_counter):
    """가짜 확률 금지 — LOW/MEDIUM/HIGH만. Counter Evidence가 있으면 한 단계 낮춘다(삭제는 안 함)."""
    s = strength - (1 if has_counter else 0)
    if s >= 3:
        return "HIGH"
    if s >= 1:
        return "MEDIUM"
    return "LOW"
