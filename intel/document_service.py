# DOCUMENT: 기존 기사 하나 = DOCUMENT 하나. document_id는 새로 만들지 않고 기존 article id를
# 그대로 쓴다(이미 sha1(정규화된 링크)라서 안정적). 기존 JSON은 전혀 바꾸지 않는다.
#
# rights_mode / source_kind는 이번 Phase에서 "적용"하지 않는다(운영자 지시 12~23: Publication Gate는
# 아직 안 만듦). Public Site·Renderer는 이 필드를 전혀 안 읽는다 — 나중에 Rights Firewall을 만들 때
# DOCUMENT 스키마를 다시 바꾸지 않아도 되게, 자리만 미리 마련해 두는 것(Schema Compatibility).
import hashlib
import re

RIGHTS_MODES = ("LINK_ONLY", "FACT_ONLY", "FACT_ANALYSIS", "OPEN_LICENSE", "LICENSED",
                "PUBLIC_DOMAIN", "GOV_OFFICIAL", "METAXIS_ORIGINAL", "MANUAL_REVIEW")

# 운영자 지시(2026-09-29): category(어디서 수집했는가)와 document_type(이 글이 실제로 무엇인가)을
# 분리한다. 기존 category/field는 절대 안 바꾸고, 이 모듈에서만 계산해 intel/documents.json에 별도로 얹는다.
DOCUMENT_TYPES = ("NEWS", "RESEARCH", "POLICY", "LAW", "COURT", "REPORT", "PRESS_RELEASE",
                  "EVENT_PROMO", "RECRUITMENT", "COMPANY_ANNOUNCEMENT", "VIDEO", "OTHER")
SOURCE_TYPES = ("NEWS_MEDIA", "GOVERNMENT", "ACADEMIC_INSTITUTION", "JOURNAL", "RESEARCH_REPOSITORY",
                "COMPANY", "NGO", "INTERNATIONAL_ORG", "VIDEO_PLATFORM", "CREATOR_PLATFORM", "OTHER")

# arXiv/Nature 같은 "진짜 논문 저장소" 도메인 — 이 도메인 글은 RESEARCH일 확률이 매우 높다(11번 예시).
_RESEARCH_REPO_DOMAINS = ("rss.arxiv.org", "arxiv.org")
_GOV_DOMAIN_HINTS = (".go.kr", "korea.kr", "whitehouse.gov", ".gov", "europa.eu")
# "대학 공식 발표·게시판" vs "대학을 취재한 언론기사"를 구분하기 위한 실마리: 제목에 대학 이름이 있어도
# 언론사 이름으로 수집됐으면(예: 조선일보) NEWS, 대학 자체 뉴스룸 피드면(예: MIT News, Stanford) 더 애매해서
# 이번 단계는 억지로 RESEARCH라 부르지 않고 category=papers인데도 기사체(따옴표·감탄·의견 동사)면 NEWS로 내린다.
_NEWSY_VERBS = re.compile(r"admits?|worries?|urges?|fears?|says?|말했|밝혔|우려|경고", re.I)


def _guess_document_type(item, domain):
    cat, title = item.get("category"), item.get("title", "")
    if cat == "talks":
        return "VIDEO"
    if cat == "papers":
        if domain in _RESEARCH_REPO_DOMAINS:
            return "RESEARCH"          # 13번: 실제 논문 저장소 도메인만 RESEARCH로 확정
        if _NEWSY_VERBS.search(title):  # "Stanford admits...", "~우려" 같은 기사체 문장은 논문이 아니라 뉴스
            return "NEWS"
        return "OTHER"                  # 확실치 않으면 억지로 RESEARCH라 부르지 않는다(12번)
    if cat == "policy":
        if domain and any(h in domain for h in _GOV_DOMAIN_HINTS):
            return "POLICY"            # 정부 도메인 원문만 POLICY로 확정
        if "보도자료" in item.get("source", ""):
            return "PRESS_RELEASE"
        return "NEWS"                   # 정책을 다룬 일반 언론 기사는 NEWS(14번: article about policy != policy)
    return "NEWS" if cat in ("news_ko", "news_global") else "OTHER"


def _guess_source_type(source_id, domain):
    if domain in _RESEARCH_REPO_DOMAINS or (domain and "nature.com" in domain):
        return "RESEARCH_REPOSITORY" if domain in _RESEARCH_REPO_DOMAINS else "JOURNAL"
    if domain and any(h in domain for h in _GOV_DOMAIN_HINTS):
        return "GOVERNMENT"
    if domain == "youtube.com":
        return "VIDEO_PLATFORM"
    if domain and (".edu" in domain or "news.mit.edu" in domain or "stanford" in domain):
        return "ACADEMIC_INSTITUTION"
    return "NEWS_MEDIA" if domain else "OTHER"


def content_hash(item):
    """제목+요약으로 만든 해시. 같은 기사라도 편집되면 바뀌므로, 나중에 '내용이 바뀐 문서' 감지에 쓴다."""
    blob = (item.get("title", "") + "\n" + (item.get("summary") or "")).encode("utf-8", "ignore")
    return hashlib.sha1(blob).hexdigest()[:16]


def to_document(item, source_id, now_iso, domain=None):
    return {
        "document_id": item["id"],           # 기존 article id 그대로(3번: Stable ID 재사용)
        "source_id": source_id,
        "canonical_url": item.get("link"),
        "title": item.get("title"),
        "category": item.get("category"),    # Legacy Compatibility로 그대로 유지(9번: 삭제·변경 안 함)
        "document_type": _guess_document_type(item, domain),  # 신규: "이 글이 실제로 무엇인가"
        "field": item.get("field") or None,
        "published": item.get("published"),
        "content_hash": content_hash(item),
        # 14~15번: 권리 상태를 모르면 항상 LINK_ONLY로 안전하게 시작(Fail-safe). 이번 Phase는 이 값을
        # 아무 데서도 읽거나 적용하지 않고, 필드가 존재한다는 것만 확인한다.
        "rights_mode": "LINK_ONLY",
        "created_at": now_iso,
        "updated_at": now_iso,
    }
