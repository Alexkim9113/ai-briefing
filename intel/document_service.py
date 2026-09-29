# DOCUMENT: 기존 기사 하나 = DOCUMENT 하나. document_id는 새로 만들지 않고 기존 article id를
# 그대로 쓴다(이미 sha1(정규화된 링크)라서 안정적). 기존 JSON은 전혀 바꾸지 않는다.
#
# rights_mode / source_kind는 이번 Phase에서 "적용"하지 않는다(운영자 지시 12~23: Publication Gate는
# 아직 안 만듦). Public Site·Renderer는 이 필드를 전혀 안 읽는다 — 나중에 Rights Firewall을 만들 때
# DOCUMENT 스키마를 다시 바꾸지 않아도 되게, 자리만 미리 마련해 두는 것(Schema Compatibility).
import hashlib

RIGHTS_MODES = ("LINK_ONLY", "FACT_ONLY", "FACT_ANALYSIS", "OPEN_LICENSE", "LICENSED",
                "PUBLIC_DOMAIN", "GOV_OFFICIAL", "METAXIS_ORIGINAL", "MANUAL_REVIEW")
SOURCE_KINDS = ("NEWS", "RESEARCH", "POLICY", "LAW", "COURT", "GOVERNMENT", "COMPANY", "VIDEO")
_KIND_BY_CATEGORY = {"news_ko": "NEWS", "news_global": "NEWS", "papers": "RESEARCH", "policy": "POLICY", "talks": "VIDEO"}


def content_hash(item):
    """제목+요약으로 만든 해시. 같은 기사라도 편집되면 바뀌므로, 나중에 '내용이 바뀐 문서' 감지에 쓴다."""
    blob = (item.get("title", "") + "\n" + (item.get("summary") or "")).encode("utf-8", "ignore")
    return hashlib.sha1(blob).hexdigest()[:16]


def to_document(item, source_id, now_iso):
    return {
        "document_id": item["id"],           # 기존 article id 그대로(3번: Stable ID 재사용)
        "source_id": source_id,
        "canonical_url": item.get("link"),
        "title": item.get("title"),
        "category": item.get("category"),
        "source_kind": _KIND_BY_CATEGORY.get(item.get("category"), "NEWS"),  # 22번: DOCUMENT != RESEARCH/POLICY/LAW 구분용
        "field": item.get("field") or None,
        "published": item.get("published"),
        "content_hash": content_hash(item),
        # 14~15번: 권리 상태를 모르면 항상 LINK_ONLY로 안전하게 시작(Fail-safe). 이번 Phase는 이 값을
        # 아무 데서도 읽거나 적용하지 않고, 필드가 존재한다는 것만 확인한다.
        "rights_mode": "LINK_ONLY",
        "created_at": now_iso,
        "updated_at": now_iso,
    }
