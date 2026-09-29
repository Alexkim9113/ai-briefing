# PHASE 5F — Forecast Revision(운영자 지시 36~37번). 기존 Forecast를 절대 삭제하지 않고
# Revision 기록만 누적한다 — Forecast Memory의 핵심.
from common import hash_id


def generate_forecast_revisions(evidence_records, forecasts):
    out = {}
    for rec in evidence_records or []:
        if rec.get("type") != "FORECAST_REVISION":
            continue
        forecast_id = rec.get("forecast_id")
        if forecast_id not in forecasts:
            continue
        new_statement = rec.get("new_statement")
        if not new_statement:
            continue
        frid = hash_id("frev", f"{forecast_id}|{rec.get('previous_statement')}|{new_statement}|"
                               f"{rec.get('timestamp')}")
        shell = {
            "forecast_revision_id": frid, "forecast_id": forecast_id,
            "previous_statement": rec.get("previous_statement"), "new_statement": new_statement,
            "previous_confidence": rec.get("previous_confidence"), "new_confidence": rec.get("new_confidence"),
            "revision_reason": rec.get("revision_reason"),
            "trigger_evidence_ids": list(rec.get("trigger_evidence_ids", [])),
            "counter_evidence_ids": list(rec.get("counter_evidence_ids", [])),
            "timestamp": rec.get("timestamp"), "human_validated": bool(rec.get("human_validated", False)),
        }
        out[frid] = shell
        # Forecast 본문은 삭제하지 않고 최신 statement/confidence만 갱신 — 이전 기록은 Revision에 보존.
        forecasts[forecast_id]["forecast_statement"] = new_statement
        if rec.get("new_confidence") in ("LOW", "MEDIUM", "HIGH"):
            forecasts[forecast_id]["confidence"] = rec["new_confidence"]
        forecasts[forecast_id]["status"] = "REVISED"
    return out, forecasts
