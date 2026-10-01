# M.6 -- minimal Statistical Evidence object + admission. Separate sidecar
# (statistical_evidence.json), never writes documents.json. Reuses the existing admission
# discipline (ADMIT ≠ BELIEVE): admit_statistical_series() is the only function that writes the
# sidecar, and it is idempotent -- re-admitting the same series_id updates in place, never
# duplicates.
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SIDECAR_PATH = HERE / "statistical_evidence.json"

STATISTICAL_RECORD_FIELDS = (
    "indicator_id", "source_id", "indicator_name", "definition", "unit", "geography", "period",
    "value", "revision_status", "retrieved_at", "source_url", "provenance", "validation_status",
)

SERIES_TREND_STATUSES = (
    "INCREASING", "DECREASING", "STABLE", "VOLATILE", "STRUCTURAL_BREAK_POSSIBLE",
    "INSUFFICIENT_SERIES", "NO_CLEAR_SIGNAL",
)

VALIDATION_STATUSES = ("VALIDATED", "REJECTED_NO_VALUE", "REJECTED_NO_PROVENANCE")


def _series_id(indicator_id, geography):
    return f"series_{hashlib.sha256(f'{indicator_id}|{geography}'.encode()).hexdigest()[:16]}"


def new_observation(indicator_id, source_id, indicator_name, unit, geography, period, value,
                     source_url, retrieved_at=None):
    return {
        "indicator_id": indicator_id, "source_id": source_id, "indicator_name": indicator_name,
        "definition": None, "unit": unit, "geography": geography, "period": period,
        "value": value, "revision_status": "UNKNOWN", "retrieved_at": retrieved_at or
        datetime.now(timezone.utc).isoformat(), "source_url": source_url,
        "provenance": source_id, "validation_status": "UNKNOWN",
    }


def validate_observation(obs):
    """Deterministic validation -- never an LLM judgment call. A real value and a real
    source_url/provenance are required; everything else may be UNKNOWN."""
    if obs.get("value") is None:
        return "REJECTED_NO_VALUE"
    if not obs.get("source_url") or not obs.get("provenance"):
        return "REJECTED_NO_PROVENANCE"
    return "VALIDATED"


def classify_series_trend(observations):
    """A deterministic trend classification -- 2-3 points is explicitly NOT enough to declare a
    directional trend (Section's own caution). Only a monotonic run of >=4 validated points in
    one direction is called INCREASING/DECREASING; anything else is reported honestly."""
    validated = sorted(
        (o for o in observations if o.get("validation_status") == "VALIDATED"),
        key=lambda o: o["period"],
    )
    if len(validated) < 4:
        return "INSUFFICIENT_SERIES"
    values = [o["value"] for o in validated]
    diffs = [values[i + 1] - values[i] for i in range(len(values) - 1)]
    if all(d > 0 for d in diffs):
        return "INCREASING"
    if all(d < 0 for d in diffs):
        return "DECREASING"
    spread = max(values) - min(values)
    mean = sum(values) / len(values)
    if mean and spread / mean > 0.3:
        return "VOLATILE"
    if mean and spread / mean < 0.05:
        return "STABLE"
    return "NO_CLEAR_SIGNAL"


def load_sidecar():
    if not SIDECAR_PATH.exists():
        return {}
    return json.loads(SIDECAR_PATH.read_text(encoding="utf-8"))


def save_sidecar(data):
    SIDECAR_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def admit_statistical_series(indicator_id, geography, raw_observations, source_url, source_id):
    """The ONLY function permitted to write statistical_evidence.json. Idempotent: re-admitting
    the same (indicator_id, geography) series_id updates in place -- it never creates a second
    series object for the same real series. Returns (series_record, was_new)."""
    series_id = _series_id(indicator_id, geography)
    sidecar = load_sidecar()
    was_new = series_id not in sidecar

    observations = []
    for raw in raw_observations:
        obs = new_observation(
            indicator_id=indicator_id, source_id=source_id,
            indicator_name=raw.get("indicator_name"), unit=raw.get("unit"), geography=geography,
            period=raw["period"], value=raw["value"], source_url=source_url,
        )
        obs["validation_status"] = validate_observation(obs)
        observations.append(obs)

    trend = classify_series_trend(observations)
    series_record = {
        "series_id": series_id, "indicator_id": indicator_id, "geography": geography,
        "source_id": source_id, "source_url": source_url, "observations": observations,
        "trend_status": trend,
        "admitted_at": sidecar.get(series_id, {}).get("admitted_at") or datetime.now(timezone.utc).isoformat(),
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
    sidecar[series_id] = series_record
    save_sidecar(sidecar)
    return series_record, was_new


def main():
    sidecar = load_sidecar()
    print(f"statistical_evidence.json has {len(sidecar)} series")


if __name__ == "__main__":
    main()
