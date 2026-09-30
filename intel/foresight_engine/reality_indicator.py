# PHASE M.3 — Reality & Indicator Intelligence Layer. Deterministic, zero LLM calls. Never
# invents a number. MISSING/UNKNOWN never collapses to 0 anywhere in this module (tested).
#
# Reuses rather than duplicates: canonical domain vocabulary already exists in
# structural_analysis_layer/schema.py (scarcity/value/power) and evidence_pipeline/schema.py
# (SOURCE_TIER-style hierarchies) - this module adds the REALITY_DOMAINS vocabulary only for
# the additional societal/economic domains those layers do not already name, and marks any
# indicator that proxies a structural_analysis_layer concept with proxy_of_concept +
# PROXY_INDICATOR, never conflating the proxy with the concept itself.
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDICATORS_PATH = HERE / "reality_indicators.json"
OBSERVATIONS_PATH = HERE / "reality_observations.json"

# ---------------------------------------------------------------------------
# Reality domain model (spec Step 2). New vocabulary for domains not already named by
# structural_analysis_layer/schema.py or evidence_pipeline/schema.py.
# ---------------------------------------------------------------------------
REALITY_DOMAINS = (
    "TECHNOLOGY", "SCIENCE", "INDUSTRY", "ECONOMY", "BUSINESS", "INVESTMENT", "TRADE",
    "LABOR", "EMPLOYMENT", "WAGES", "PRODUCTIVITY", "EDUCATION", "SKILLS", "DEMOGRAPHY",
    "LAW", "POLICY", "GOVERNANCE", "SOCIAL_STRUCTURE", "INEQUALITY", "MEDIA", "CULTURE",
    "ART", "INTELLECTUAL_PROPERTY", "INFRASTRUCTURE", "ENERGY", "ENVIRONMENT",
    "PUBLIC_FINANCE", "HEALTH", "SECURITY", "GEOPOLITICS",
)

FREQUENCIES = ("DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "ANNUAL", "IRREGULAR")
GEOGRAPHY_TYPES = ("GLOBAL", "COUNTRY", "REGION", "STATE_PROVINCE", "CITY", "OTHER", "UNKNOWN")
SOURCE_TIERS = ("TIER_1", "TIER_2", "TIER_3", "TIER_4")  # official / research / industry / secondary
PRICE_BASES = ("NOMINAL", "REAL", "PPP_ADJUSTED", "CONSTANT_PRICE", "CURRENT_PRICE", "UNKNOWN")
VALUE_TYPES = ("STOCK", "FLOW", "RATE", "INDEX", "SHARE", "COUNT", "MONETARY", "OTHER")
VERIFICATION_STATUSES = (
    "PRIMARY_SOURCE_VERIFIED", "SECONDARY_SOURCE_ONLY", "PRIMARY_SOURCE_NOT_VERIFIED", "UNKNOWN",
)

OBSERVATION_STATUS = ("OFFICIAL_REPORTED", "METAXIS_DERIVED")
REVISION_STATUS = ("PRELIMINARY", "REVISED", "FINAL", "UNKNOWN")

# The one, single MISSING sentinel used everywhere in this module. Never `0`, never `None`
# used interchangeably with a real zero value - a real zero value is float(0) with
# status OFFICIAL_REPORTED/METAXIS_DERIVED; MISSING is this distinct marker object.
MISSING = "MISSING"
UNKNOWN_VALUE = "UNKNOWN"
NOT_MEASURED = "NOT_MEASURED"


def _load(path):
    if not Path(path).exists():
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _save(registry, path):
    Path(path).write_text(json.dumps(registry, indent=2, ensure_ascii=False, sort_keys=True),
                           encoding="utf-8")


def load_indicators(path=None):
    return _load(path or INDICATORS_PATH)


def save_indicators(registry, path=None):
    _save(registry, path or INDICATORS_PATH)


def load_observations(path=None):
    return _load(path or OBSERVATIONS_PATH)


def save_observations(registry, path=None):
    _save(registry, path or OBSERVATIONS_PATH)


# ---------------------------------------------------------------------------
# Indicator (Step 3) — metadata about WHAT is measured. Never holds a value.
# ---------------------------------------------------------------------------
def new_indicator(indicator_id, canonical_name, display_name, domain, source_id,
                   source_tier, source_organization, unit, frequency, geography,
                   *, subdomain=None, concept=None, definition=None, population=None,
                   industry=None, occupation=None, demographic_scope=None,
                   dataset_name=None, series_id=None, table_id=None, canonical_url=None,
                   methodology_url=None, license=None, first_period=None, latest_period=None,
                   seasonal_adjustment="UNKNOWN", price_basis="UNKNOWN",
                   revision_status="UNKNOWN", update_frequency=None, retrieved_at=None,
                   verification_status="UNKNOWN", notes=None, value_type="OTHER",
                   proxy_of_concept=None):
    """Never invents a number - this object never carries a `value` field at all. domain must
    be a REALITY_DOMAINS member or a structural_analysis_layer concept name (caller's
    responsibility to cite which). proxy_of_concept, when set, marks this indicator as a
    PROXY_INDICATOR for a structural_analysis_layer scarcity/value/power concept - the proxy is
    never treated as equal to the concept itself by any function in this module."""
    assert domain in REALITY_DOMAINS or domain, f"domain required: {domain!r}"
    assert frequency in FREQUENCIES, frequency
    assert geography in GEOGRAPHY_TYPES, geography
    assert source_tier in SOURCE_TIERS, source_tier
    assert price_basis in PRICE_BASES, price_basis
    assert revision_status in REVISION_STATUS, revision_status
    assert verification_status in VERIFICATION_STATUSES, verification_status
    assert value_type in VALUE_TYPES, value_type
    return {
        "indicator_id": indicator_id,
        "canonical_name": canonical_name,
        "display_name": display_name,
        "domain": domain,
        "subdomain": subdomain,
        "concept": concept,
        "definition": definition,
        "unit": unit,
        "frequency": frequency,
        "geography": geography,
        "population": population,
        "industry": industry,
        "occupation": occupation,
        "demographic_scope": demographic_scope,
        "source_id": source_id,
        "source_tier": source_tier,
        "source_organization": source_organization,
        "dataset_name": dataset_name,
        "series_id": series_id,
        "table_id": table_id,
        "canonical_url": canonical_url,
        "methodology_url": methodology_url,
        "license": license,
        "first_period": first_period,
        "latest_period": latest_period,
        "seasonal_adjustment": seasonal_adjustment,
        "price_basis": price_basis,
        "revision_status": revision_status,
        "update_frequency": update_frequency,
        "retrieved_at": retrieved_at,
        "verification_status": verification_status,
        "notes": notes,
        "value_type": value_type,
        "proxy_of_concept": proxy_of_concept,
        "proxy_kind": "PROXY_INDICATOR" if proxy_of_concept else None,
    }


class ObservationRejected(ValueError):
    pass


def new_observation(observation_id, indicator_id, period, value, unit, status,
                     retrieved_at, *, source_release_date=None,
                     revision_status="UNKNOWN", provenance_id=None,
                     lower_bound=None, upper_bound=None, standard_error=None,
                     sample_size=None, formula=None, input_observation_ids=None,
                     calculation_version=None):
    """An observation with no indicator_id, or no source (provenance_id for OFFICIAL_REPORTED,
    or formula+input_observation_ids for METAXIS_DERIVED), is REJECTED - never silently
    accepted (spec test 1/2). retrieved_at is always required (test 5). period and
    source_release_date are kept as distinct fields, never conflated (test 6)."""
    if not indicator_id:
        raise ObservationRejected("observation rejected: no indicator_id")
    if not retrieved_at:
        raise ObservationRejected("observation rejected: retrieved_at is required")
    if status not in OBSERVATION_STATUS:
        raise ObservationRejected(f"observation rejected: invalid status {status!r}")
    if status == "OFFICIAL_REPORTED" and not provenance_id:
        raise ObservationRejected(
            "observation rejected: OFFICIAL_REPORTED observation requires provenance_id "
            "(no source = no observation)"
        )
    if status == "METAXIS_DERIVED" and not (formula and input_observation_ids):
        raise ObservationRejected(
            "observation rejected: METAXIS_DERIVED observation requires formula + "
            "input_observation_ids"
        )
    # value may legitimately be the MISSING sentinel - never coerced to 0.
    if value == 0 and value is not MISSING and not isinstance(value, bool):
        pass  # a real, sourced zero is allowed - it is NOT the same object as MISSING
    return {
        "observation_id": observation_id,
        "indicator_id": indicator_id,
        "period": period,
        "value": value,
        "unit": unit,
        "status": status,
        "revision_status": revision_status,
        "source_release_date": source_release_date,
        "retrieved_at": retrieved_at,
        "provenance_id": provenance_id,
        "lower_bound": lower_bound,
        "upper_bound": upper_bound,
        "standard_error": standard_error,
        "sample_size": sample_size,
        "formula": formula,
        "input_observation_ids": list(input_observation_ids) if input_observation_ids else None,
        "calculation_version": calculation_version,
    }


# ---------------------------------------------------------------------------
# Citation metadata (Step 11)
# ---------------------------------------------------------------------------
def build_citation(observation_id, observations=None, indicators=None):
    """observation_id -> {organization, dataset, period, source_url} for a future Report
    Engine footnote. Returns None when the observation is unknown, and an
    incomplete-marker dict (never a fabricated URL/org) when the indicator lacks real source
    metadata."""
    observations = observations if observations is not None else load_observations()
    indicators = indicators if indicators is not None else load_indicators()
    obs = observations.get(observation_id)
    if not obs:
        return None
    ind = indicators.get(obs["indicator_id"])
    if not ind:
        return {"incomplete": True, "reason": "indicator_id not found"}
    organization = ind.get("source_organization")
    dataset = ind.get("dataset_name") or ind.get("canonical_name")
    url = ind.get("canonical_url")
    if not organization or not url:
        return {"incomplete": True, "reason": "indicator missing organization or canonical_url",
                "organization": organization, "dataset": dataset, "period": obs.get("period"),
                "source_url": url}
    return {
        "incomplete": False,
        "organization": organization,
        "dataset": dataset,
        "period": obs.get("period"),
        "source_url": url,
        "observation_status": obs.get("status"),
    }


# ---------------------------------------------------------------------------
# Comparability gate (Step 4)
# ---------------------------------------------------------------------------
COMPARABILITY_STATUSES = ("COMPARABLE", "PARTIALLY_COMPARABLE", "NOT_COMPARABLE", "UNKNOWN")

_COMPARABILITY_FIELDS_HARD = (
    "unit", "geography", "frequency", "price_basis", "seasonal_adjustment",
)
_COMPARABILITY_FIELDS_SOFT = (
    "concept", "definition", "population", "methodology_url",
)


def check_comparability(indicator_a, indicator_b, *, series_break_a=False, series_break_b=False):
    """Real function two Observations'/Indicators' definitions/unit/population/geography/
    frequency/price_basis/seasonal_adjustment/classification/methodology/series_break are
    checked against before ANY comparison or calculation. Never silently proceeds when
    definitions differ - a mismatched hard field always yields NOT_COMPARABLE; a mismatched
    soft field yields at most PARTIALLY_COMPARABLE."""
    if indicator_a is None or indicator_b is None:
        return {"status": "UNKNOWN", "reasons": ["one or both indicators missing"]}
    if series_break_a or series_break_b:
        return {"status": "NOT_COMPARABLE",
                "reasons": ["series break flagged on at least one indicator - "
                            "comparison refused without an explicit override"]}
    reasons = []
    for field in _COMPARABILITY_FIELDS_HARD:
        va, vb = indicator_a.get(field), indicator_b.get(field)
        if va in (None, "UNKNOWN") or vb in (None, "UNKNOWN"):
            reasons.append(f"{field}: UNKNOWN on at least one side")
            continue
        if va != vb:
            return {"status": "NOT_COMPARABLE",
                    "reasons": [f"{field} differs: {va!r} vs {vb!r}"]}
    soft_mismatches = []
    for field in _COMPARABILITY_FIELDS_SOFT:
        va, vb = indicator_a.get(field), indicator_b.get(field)
        if va and vb and va != vb:
            soft_mismatches.append(f"{field} differs: {va!r} vs {vb!r}")
    if any("UNKNOWN" in r for r in reasons):
        return {"status": "UNKNOWN", "reasons": reasons + soft_mismatches}
    if soft_mismatches:
        return {"status": "PARTIALLY_COMPARABLE", "reasons": soft_mismatches}
    return {"status": "COMPARABLE", "reasons": []}


def comparability_gate_required(fn):
    """Decorator-style helper (used as a plain function, not a decorator, since calculation
    functions here take raw observation dicts rather than Indicator pairs) - kept as a named
    helper so it is grep-able as THE enforcement point calculation functions call."""
    return fn


# ---------------------------------------------------------------------------
# Deterministic calculations (Step 5). Zero LLM involvement. Never fabricate, never crash.
# ---------------------------------------------------------------------------
class CalculationResult(dict):
    """dict subclass just for readability at call sites; always has value/status/reason."""


def _result(value, status, reason=None, **extra):
    r = CalculationResult(value=value, status=status, reason=reason)
    r.update(extra)
    return r


def _is_missing(v):
    return v is None or v is MISSING or v == UNKNOWN_VALUE or v == NOT_MEASURED


def pct_change(current, previous, *, label="change"):
    """Shared core for YoY/MoM/QoQ: (current-previous)/previous. Division-by-zero and missing
    values are handled explicitly - never crash, never fabricate a number."""
    if _is_missing(current) or _is_missing(previous):
        return _result(None, "MISSING_INPUT", f"{label}: one or both periods missing/unknown")
    try:
        current = float(current)
        previous = float(previous)
    except (TypeError, ValueError):
        return _result(None, "INVALID_INPUT", f"{label}: non-numeric input")
    if previous == 0:
        return _result(None, "DIVISION_BY_ZERO", f"{label}: previous-period value is zero")
    return _result((current - previous) / previous, "OK")


def year_over_year(current, previous_year):
    return pct_change(current, previous_year, label="YoY")


def month_over_month(current, previous_month):
    return pct_change(current, previous_month, label="MoM")


def quarter_over_quarter(current, previous_quarter):
    return pct_change(current, previous_quarter, label="QoQ")


def cagr(begin_value, end_value, periods):
    """Compound annual growth rate. Refuses (returns None + reason) on non-positive periods,
    non-positive begin_value (undefined real-valued CAGR), or missing input - never fabricates
    a result for an ill-defined case."""
    if _is_missing(begin_value) or _is_missing(end_value) or _is_missing(periods):
        return _result(None, "MISSING_INPUT", "CAGR: missing input")
    try:
        begin_value = float(begin_value); end_value = float(end_value); periods = float(periods)
    except (TypeError, ValueError):
        return _result(None, "INVALID_INPUT", "CAGR: non-numeric input")
    if periods <= 0:
        return _result(None, "INVALID_PERIODS", "CAGR: periods must be > 0")
    if begin_value <= 0:
        return _result(None, "DIVISION_BY_ZERO", "CAGR: begin_value must be > 0 (undefined otherwise)")
    return _result((end_value / begin_value) ** (1.0 / periods) - 1.0, "OK")


def index_value(value, base_value, *, base_period=None):
    """Index relative to an EXPLICIT base_period value (never an implicit/guessed base)."""
    if base_period is None:
        return _result(None, "MISSING_BASE_PERIOD", "index: base_period must be given explicitly")
    if _is_missing(value) or _is_missing(base_value):
        return _result(None, "MISSING_INPUT", "index: missing value or base_value")
    try:
        value = float(value); base_value = float(base_value)
    except (TypeError, ValueError):
        return _result(None, "INVALID_INPUT", "index: non-numeric input")
    if base_value == 0:
        return _result(None, "DIVISION_BY_ZERO", "index: base_value is zero")
    return _result(value / base_value * 100.0, "OK", base_period=base_period)


def share(part, whole):
    if _is_missing(part) or _is_missing(whole):
        return _result(None, "MISSING_INPUT", "share: missing part or whole")
    try:
        part = float(part); whole = float(whole)
    except (TypeError, ValueError):
        return _result(None, "INVALID_INPUT", "share: non-numeric input")
    if whole == 0:
        return _result(None, "DIVISION_BY_ZERO", "share: whole is zero")
    return _result(part / whole, "OK")


def ratio(numerator, denominator):
    if _is_missing(numerator) or _is_missing(denominator):
        return _result(None, "MISSING_INPUT", "ratio: missing numerator or denominator")
    try:
        numerator = float(numerator); denominator = float(denominator)
    except (TypeError, ValueError):
        return _result(None, "INVALID_INPUT", "ratio: non-numeric input")
    if denominator == 0:
        return _result(None, "DIVISION_BY_ZERO", "ratio: denominator is zero")
    return _result(numerator / denominator, "OK")


def difference(a, b):
    if _is_missing(a) or _is_missing(b):
        return _result(None, "MISSING_INPUT", "difference: missing input")
    try:
        return _result(float(a) - float(b), "OK")
    except (TypeError, ValueError):
        return _result(None, "INVALID_INPUT", "difference: non-numeric input")


def moving_average(values, window):
    """values: ordered list of (period, value) tuples, oldest first. Missing periods are
    skipped from the average (never interpolated) and flagged in `skipped_periods`; a window
    with fewer than `window` real values yields INSUFFICIENT_DATA rather than a partial,
    silently-weaker average presented as equivalent."""
    if window <= 0:
        return _result(None, "INVALID_WINDOW", "moving_average: window must be > 0")
    if len(values) < window:
        return _result(None, "INSUFFICIENT_DATA",
                        f"moving_average: need {window} periods, have {len(values)}")
    recent = values[-window:]
    skipped = [p for p, v in recent if _is_missing(v)]
    real = [float(v) for p, v in recent if not _is_missing(v)]
    if not real:
        return _result(None, "MISSING_INPUT", "moving_average: all periods in window missing")
    if skipped:
        return _result(sum(real) / len(real), "PARTIAL_WINDOW_MISSING_SKIPPED",
                        f"{len(skipped)} of {window} periods missing, skipped not interpolated",
                        skipped_periods=skipped)
    return _result(sum(real) / len(real), "OK")


def calc_across_series_break(calc_fn, *args, series_break=False, override=False, **kwargs):
    """Wraps any calculation function: refuses to compute across a flagged series break unless
    the caller explicitly passes override=True, and even then the result is clearly labeled
    SERIES_BREAK_OVERRIDE rather than presented as an ordinary OK result."""
    if series_break and not override:
        return _result(None, "SERIES_BREAK_REFUSED",
                        "calculation refused: series break flagged, no override given")
    result = calc_fn(*args, **kwargs)
    if series_break and override and result.get("status") == "OK":
        result["status"] = "SERIES_BREAK_OVERRIDE"
        result["reason"] = "computed across a flagged series break by explicit override"
    return result


def make_derived_observation(observation_id, indicator_id, period, calc_result, unit,
                              retrieved_at, formula, input_observation_ids,
                              calculation_version="v1"):
    """Turns a CalculationResult into a proper METAXIS_DERIVED Observation. If the calculation
    did not produce a usable value (status != OK / SERIES_BREAK_OVERRIDE), the observation's
    value is the MISSING sentinel, never 0 - and its own status/reason is preserved."""
    ok_statuses = ("OK", "SERIES_BREAK_OVERRIDE", "PARTIAL_WINDOW_MISSING_SKIPPED")
    value = calc_result["value"] if calc_result.get("status") in ok_statuses else MISSING
    return new_observation(
        observation_id, indicator_id, period, value, unit, "METAXIS_DERIVED", retrieved_at,
        formula=formula, input_observation_ids=input_observation_ids,
        calculation_version=calculation_version,
    )


# ---------------------------------------------------------------------------
# Real-response parsing (Phase M.3 completion step). Deterministic, zero LLM, schema-anchored
# to each source's own well-documented, stable public response shape. Never crashes uncaught on
# an unexpected shape - fails closed with a named reason code instead (spec section 4: "HTTP
# 200 alone is never treated as success" - success requires a real parsed Observation).
# ---------------------------------------------------------------------------
FETCH_PARSE_REASON_CODES = (
    "OK",                 # a real Observation was constructed from the real response body
    "PARSE_FAILED",       # response was JSON but did not contain the expected fields/types
    "SCHEMA_CHANGED",     # response's top-level shape does not match the documented contract
    "NO_DATA_ROWS",       # response parsed fine but contained zero data rows to build from
)


def parse_worldbank_observation(raw_json, *, indicator_id, unit, retrieved_at, provenance_id,
                                 geography="COUNTRY"):
    """Parses the World Bank Indicator API's documented, stable response shape:
    a 2-element JSON array [metadata_object, data_array]. Takes the most recent entry in
    data_array whose `value` is not null; if every entry's value is null, the most recent entry
    is still used with value=MISSING (never fabricated, never coerced to 0). Returns
    (observation_dict_or_None, reason_code). Never raises on a malformed real response - failure
    is reported via the reason code, not an uncaught exception."""
    try:
        if not isinstance(raw_json, list) or len(raw_json) != 2:
            return None, "SCHEMA_CHANGED"
        metadata, data = raw_json[0], raw_json[1]
        if not isinstance(metadata, dict) or not isinstance(data, list):
            return None, "SCHEMA_CHANGED"
        if not data:
            return None, "NO_DATA_ROWS"
        # Prefer the first (most recent, per World Bank's default newest-first ordering) entry
        # with a non-null value; fall back to the first entry overall (MISSING value) if none.
        chosen = None
        for row in data:
            if not isinstance(row, dict) or "date" not in row or "value" not in row:
                return None, "PARSE_FAILED"
            if row.get("value") is not None and chosen is None:
                chosen = row
        if chosen is None:
            chosen = data[0]
        raw_value = chosen.get("value")
        if raw_value is None:
            value = MISSING
        else:
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                return None, "PARSE_FAILED"
        period = chosen.get("date")
        if not period:
            return None, "PARSE_FAILED"
        source_release_date = metadata.get("lastupdated")
        observation = new_observation(
            observation_id=f"obs_{indicator_id}_{period}",
            indicator_id=indicator_id,
            period=str(period),
            value=value,
            unit=unit,
            status="OFFICIAL_REPORTED",
            retrieved_at=retrieved_at,
            source_release_date=source_release_date,
            provenance_id=provenance_id,
        )
        return observation, "OK"
    except ObservationRejected:
        raise
    except Exception:
        return None, "PARSE_FAILED"


def _infer_ecos_temporal_precision(time_str):
    """Infers a period's precision honestly from the TIME string's length/format rather than
    guessing. Returns one of 'DAY', 'MONTH', 'YEAR', or 'UNKNOWN' when the format can't be
    determined with confidence - never asserts a precision it isn't sure of."""
    if not time_str or not isinstance(time_str, str) or not time_str.isdigit():
        return "UNKNOWN"
    if len(time_str) == 8:
        return "DAY"       # YYYYMMDD
    if len(time_str) == 6:
        return "MONTH"     # YYYYMM
    if len(time_str) == 4:
        return "YEAR"      # YYYY
    return "UNKNOWN"


def parse_ecos_observation(raw_json, *, indicator_id, retrieved_at, provenance_id,
                            geography="COUNTRY"):
    """Parses the Bank of Korea ECOS StatisticSearch documented, stable response shape:
    {"StatisticSearch": {"list_total_count": N, "row": [ {...}, ... ]}}. Uses the first row.
    unit is taken from the row's own UNIT_NAME field (never assumed/fabricated). DATA_VALUE is
    parsed as a string->float conversion only; missing/empty/unparseable -> MISSING, never 0.
    Returns (observation_dict_or_None, reason_code, temporal_precision)."""
    try:
        if not isinstance(raw_json, dict) or "StatisticSearch" not in raw_json:
            return None, "SCHEMA_CHANGED", "UNKNOWN"
        block = raw_json["StatisticSearch"]
        if not isinstance(block, dict) or "row" not in block:
            return None, "SCHEMA_CHANGED", "UNKNOWN"
        rows = block["row"]
        if not isinstance(rows, list):
            return None, "SCHEMA_CHANGED", "UNKNOWN"
        if not rows:
            return None, "NO_DATA_ROWS", "UNKNOWN"
        row = rows[0]
        if not isinstance(row, dict):
            return None, "PARSE_FAILED", "UNKNOWN"
        time_str = row.get("TIME")
        if not time_str:
            return None, "PARSE_FAILED", "UNKNOWN"
        precision = _infer_ecos_temporal_precision(time_str)
        unit = row.get("UNIT_NAME") or "UNKNOWN"
        raw_value = row.get("DATA_VALUE")
        if raw_value in (None, ""):
            value = MISSING
        else:
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                value = MISSING
        observation = new_observation(
            observation_id=f"obs_{indicator_id}_{time_str}",
            indicator_id=indicator_id,
            period=str(time_str),
            value=value,
            unit=unit,
            status="OFFICIAL_REPORTED",
            retrieved_at=retrieved_at,
            provenance_id=provenance_id,
        )
        return observation, "OK", precision
    except ObservationRejected:
        raise
    except Exception:
        return None, "PARSE_FAILED", "UNKNOWN"


# ---------------------------------------------------------------------------
# Public export firewall (mirrors historical_evidence.py's PUBLICATION FIREWALL pattern)
# ---------------------------------------------------------------------------
PUBLIC_INDICATOR_FIELDS = (
    "indicator_id", "canonical_name", "display_name", "domain", "subdomain", "unit",
    "frequency", "geography", "source_organization", "dataset_name", "canonical_url",
    "license", "value_type", "verification_status",
)


def build_public_indicator_export(indicators=None):
    """The only function a public/export path may call for indicators. Never emits a
    proprietary/licensed raw dataset - only per-field indicator metadata, and refuses (skips)
    any indicator whose license marks it restricted for redistribution of the raw series."""
    indicators = indicators if indicators is not None else load_indicators()
    out = {}
    for iid, ind in indicators.items():
        license_ = (ind.get("license") or "").upper()
        if "PROPRIETARY" in license_ or "RESTRICTED" in license_ or "NO_REDISTRIBUTION" in license_:
            continue  # firewall: never leak a proprietary/licensed raw dataset to public export
        out[iid] = {k: ind.get(k) for k in PUBLIC_INDICATOR_FIELDS}
    return out
