# DOCUMENT: 기존 기사 하나 = DOCUMENT 하나. document_id는 새로 만들지 않고 기존 article id를
# 그대로 쓴다(이미 sha1(정규화된 링크)라서 안정적). 기존 JSON은 전혀 바꾸지 않는다.
import hashlib


def content_hash(item):
    """제목+요약으로 만든 해시. 같은 기사라도 편집되면 바뀌므로, 나중에 '내용이 바뀐 문서' 감지에 쓴다."""
    blob = (item.get("title", "") + "\n" + (item.get("summary") or "")).encode("utf-8", "ignore")
    return hashlib.sha1(blob).hexdigest()[:16]


def to_document(item, source_id, now_iso):
    return {
        "document_id": item["id"],           # 기존 article id 그대로(G번: Stable ID 재사용)
        "source_id": source_id,
        "canonical_url": item.get("link"),
        "title": item.get("title"),
        "category": item.get("category"),
        "field": item.get("field") or None,
        "published": item.get("published"),
        "content_hash": content_hash(item),
        "created_at": now_iso,
        "updated_at": now_iso,
    }
