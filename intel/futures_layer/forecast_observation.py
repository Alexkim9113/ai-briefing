# PHASE 5F — Forecast Observation(운영자 지시 35번). 시간이 지나 Forecast를 Evidence와
# 비교한 기록 — 이벤트 로그이므로 누적만 하고 덮어쓰지 않는다.
from common import hash_id


def generate_forecast_observations(evidence_records, forecasts):
    out = {}
    for rec in evidence_records or []:
        if rec.get("type") != "FORECAST_OBSERVATION":
            continue
        forecast_id = rec.get("forecast_id")
        if forecast_id not in forecasts:
            continue
        observation_date = rec.get("observation_date")
        if not observation_date:
            continue
        foid = hash_id("fobs", f"{forecast_id}|{observation_date}|{rec.get('assessment')}")
        shell = {
            "forecast_observation_id": foid, "forecast_id": forecast_id,
            "observation_date": observation_date,
            "observed_indicators": list(rec.get("observed_indicators", [])),
            "supporting_evidence_ids": list(rec.get("supporting_evidence_ids", [])),
            "contradicting_evidence_ids": list(rec.get("contradicting_evidence_ids", [])),
            "assessment": rec.get("assessment"), "confidence_change": rec.get("confidence_change"),
            "notes_code": rec.get("notes_code"), "created_at": None,
        }
        out[foid] = shell
    return out


# Forecast의 status는 관측 결과에 따라 규칙 기반으로만 전이한다(자동 서사 생성 없음).
_ASSESSMENT_TO_STATUS = {
    "SUPPORTS": "SUPPORTED", "PARTIALLY_SUPPORTS": "PARTIALLY_SUPPORTED",
    "WEAKENS": "WEAKENED", "CONTRADICTS": "CONTRADICTED",
}


def apply_observations_to_forecast_status(forecasts, observations):
    for obs in observations.values():
        fid = obs["forecast_id"]
        new_status = _ASSESSMENT_TO_STATUS.get(obs.get("assessment"))
        if fid in forecasts and new_status:
            forecasts[fid]["status"] = new_status
    return forecasts
