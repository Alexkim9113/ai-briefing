# STAGE 7 — 공용 헬퍼. Stage 6 common.py의 stable-id 패턴을 재사용한다(새 방식을 발명하지 않음).
import hashlib
import re


def normalize_query(text):
    """대소문자/중복 공백만 정규화 - 의미를 바꾸는 어떤 처리도 하지 않는다(추측 금지)."""
    return re.sub(r"\s+", " ", (text or "").strip()).lower()


def stable_query_id(question_text, mode, now_iso):
    norm = normalize_query(question_text)
    h = hashlib.sha1(f"{mode}|{norm}|{now_iso}".encode("utf-8")).hexdigest()
    return f"query_{h[:16]}"


def stable_response_id(query_id, context_hash):
    h = hashlib.sha1(f"{query_id}|{context_hash}".encode("utf-8")).hexdigest()
    return f"resp_{h[:16]}"


def context_hash(context_pack):
    """섹션 9/51: 동일 query+scope+evidence+prompt_version+model이면 cache 재사용 판단에 쓸
    deterministic hash. dict 순서에 의존하지 않도록 sort_keys."""
    import json
    blob = json.dumps(context_pack, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]
