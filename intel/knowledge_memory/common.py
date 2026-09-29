# STAGE 6 — 공용 유틸. 새 알고리즘 없음 — 다른 layer들의 text_hash/stable-id 패턴 재사용.
import hashlib
import re

_WS_RE = re.compile(r"\s+")


def normalize_statement(text):
    """dedup/stable-id 계산용 정규화 — 공백/대소문자만 통일한다(의미 변경 없음)."""
    return _WS_RE.sub(" ", (text or "").strip()).lower()


def stable_note_id(note_type, normalized_statement, canonical_subject_id):
    """섹션 36: rerun마다 바뀌지 않는 deterministic ID."""
    key = f"{note_type}|{normalized_statement}|{canonical_subject_id or ''}"
    return "note_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def stable_relation_id(subject_id, relation_type, object_id):
    key = f"{subject_id}|{relation_type}|{object_id}"
    return "rel_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def dedup_fingerprint(note_type, normalized_statement, concept_ids, source_object_ids):
    """섹션 35: exact/deterministic dedup 키. concept_ids/source_object_ids는 정렬해서
    순서 차이로 인한 허위 불일치를 막는다."""
    key = "|".join([
        note_type,
        normalized_statement,
        ",".join(sorted(concept_ids or [])),
        ",".join(sorted(source_object_ids or [])),
    ])
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
