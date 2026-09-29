# PHASE 4B — Primary Document Selection(운영자 지시 7번). CONFIRMED Event에만 적용.
# 결정적(deterministic) 규칙 — 재실행해도 항상 같은 결과. Primary != True document, 대표 근거일 뿐.
_WIRE_SOURCES = {"연합뉴스", "뉴시스", "Reuters", "AP", "AFP", "로이터"}
_GOV_HINTS = ("행안부", "과기정통부", "정부", "국회", "백악관", "white house", "ministry", "행정안전부")
_COURT_LAW_HINTS = ("법원", "판결", "court", "ruling", "재판부")
_COMPANY_OFFICIAL_HINTS = ("official", "블로그", "press release", "보도자료")
_SPECIALIST_SOURCES = {"AI타임스", "인공지능신문", "TechCrunch AI", "The Decoder", "SiliconANGLE AI"}
_REPROCESSOR_HINTS = ("구글뉴스", "google news", "news.google")


def _priority(item, raw_source_str):
    s = (raw_source_str or "").lower()
    title = item.get("title", "").lower()
    if any(h in s or h in title for h in _GOV_HINTS):
        return 3
    if item.get("document_type") == "RESEARCH":
        return 2
    if any(h in s or h in title for h in _COURT_LAW_HINTS):
        return 3
    if any(h in s for h in _COMPANY_OFFICIAL_HINTS):
        return 4
    if raw_source_str in _WIRE_SOURCES:
        return 5
    if any(h in s for h in _REPROCESSOR_HINTS):
        return 8
    if raw_source_str in _SPECIALIST_SOURCES:
        return 7
    return 6  # Major Media 기본값


def select_primary(document_ids, raw_items_by_id, documents_by_id):
    """우선순위 낮은 숫자가 더 대표성 있음(1=Original Official ... 8=Reprocessor).
    동률이면 발행시각이 이른 쪽, 그다음 document_id 사전순 — 재실행해도 안 바뀜."""
    def key(did):
        raw = raw_items_by_id.get(did, {})
        doc = documents_by_id.get(did, {})
        merged = {**raw, "document_type": doc.get("document_type")}
        pr = _priority(merged, raw.get("source"))
        return (pr, raw.get("published") or "9999", did)
    return sorted(document_ids, key=key)[0]
