# SOURCE INTELLIGENCE CORRECTION v1.0 — Phase D(spec 섹션 17/59). 문서마다 실제로
# 확보한 원문 정도를 정직하게 판정한다. 추측 금지 - 실제로 어떤 필드가 있는지만 본다.
from schema import CONTENT_STATUS_VALUES


def assign_content_status(raw_item, acquired=None):
    """raw_item: briefing.py가 만드는 원본 item(title/summary/mx 등).
    acquired: content_acquisition.acquire_content()의 결과(dict) 또는 None(시도 안 함).
    현재 production 기본 경로는 acquired=None(본문 수집 자체가 없음) - 이 경우 SNIPPET_ONLY/
    TITLE_ONLY만 정직하게 반환한다. FULL_TEXT는 실제로 acquired["status"]=="FULL_TEXT"일
    때만 나온다 - 위시풀 싱킹으로 승격시키지 않는다(섹션 17 마지막)."""
    if acquired is not None:
        status = acquired.get("status")
        if status in CONTENT_STATUS_VALUES:
            return status
        return "UNKNOWN"

    summary = (raw_item or {}).get("summary") or ""
    title = (raw_item or {}).get("title") or ""
    if summary.strip():
        return "SNIPPET_ONLY"
    if title.strip():
        return "TITLE_ONLY"
    return "UNKNOWN"


def is_strong_enough_for(content_status, required_statuses):
    """content_status가 required_statuses(예: {"FULL_TEXT","STRUCTURED_PRIMARY_DATA"})
    중 하나에 해당하는지만 검사 - 서열을 추측해서 비교하지 않는다(섹션 18: PRIMARY도
    TRUE를 의미하지 않으므로 임의 서열화가 위험할 수 있음 - 화이트리스트 방식이 더 안전)."""
    return content_status in required_statuses
