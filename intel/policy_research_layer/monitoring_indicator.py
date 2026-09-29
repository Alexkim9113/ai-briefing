# PHASE 5G — Monitoring Indicator(운영자 지시 36~39번). Indicator != Forecast — 관찰 대상일
# 뿐 그 변화에 대한 조건부 판단이 아니다. 데이터가 없어도 measurement_definition이 명확하면
# MONITORING_CANDIDATE로 생성하되 baseline/latest는 null로 두고 0으로 만들지 않는다.
from common import hash_id


def generate_monitoring_indicator_candidates(evidence_records):
    out = {}
    for rec in evidence_records or []:
        if rec.get("type") != "MONITORING_INDICATOR":
            continue
        name = rec.get("indicator_name")
        measurement_definition = rec.get("measurement_definition")
        if not name or not measurement_definition:
            continue
        mid = hash_id("mon", f"{name}|{measurement_definition}")
        from schema import new_monitoring_indicator_shell
        shell = new_monitoring_indicator_shell(
            mid, name, rec.get("indicator_type"), rec.get("target_object_type"), rec.get("target_object_id"),
            measurement_definition, rec.get("unit"), rec.get("direction_of_interest"),
            rec.get("data_source_type"), rec.get("collection_frequency"), rec.get("geography"),
            rec.get("population"))
        # 실제 데이터가 없으면 null 유지(0으로 만들지 않음) — 값이 명시적으로 제공될 때만 채운다.
        shell["baseline_value"] = rec.get("baseline_value")
        shell["latest_value"] = rec.get("latest_value")
        shell["baseline_date"] = rec.get("baseline_date")
        shell["latest_date"] = rec.get("latest_date")
        shell["thresholds"] = list(rec.get("thresholds", []))
        shell["uncertainty_ids"] = list(rec.get("uncertainty_ids", []))
        out[mid] = shell
    return out
