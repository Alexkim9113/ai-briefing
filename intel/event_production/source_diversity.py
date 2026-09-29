# PHASE 4B — Source Diversity(운영자 지시 8번). Event가 CONFIRMED된 "이후"에만 계산 —
# Same Event 판정에는 절대 쓰지 않는다(핵심 지시, score.py/signals.py에서도 의도적으로 제외).
import re

# 구글뉴스 재배포처럼 같은 원문을 여러 이름으로 재수집하는 경우를 하나의 canonical source로
# 묶는다 — intel/source_service.py의 MULTI_TENANT/도메인 정규화 취지를 가볍게 재사용.
_REPROCESSOR_RX = re.compile(r"구글뉴스|google news", re.I)


def canonical_source(raw_source):
    if _REPROCESSOR_RX.search(raw_source or ""):
        return "GOOGLE_NEWS_SYNDICATION"  # 재배포 소스는 서로 다른 outlet이어도 syndication 경로로 뭉뚱그림
    return (raw_source or "").strip().lower()


def compute(document_ids, raw_items_by_id):
    sources = {canonical_source(raw_items_by_id.get(d, {}).get("source", "")) for d in document_ids}
    sources.discard("")
    return {"source_count": len(document_ids), "source_diversity": len(sources)}
