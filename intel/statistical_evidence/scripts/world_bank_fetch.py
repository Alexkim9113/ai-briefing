# M.6 Section 1 -- CONDITIONAL ENTRY GATE. Real live fetch against the World Bank's documented,
# stable public REST API (not a guessed endpoint -- api.worldbank.org/v2 is World Bank's own
# published API). Run only via .github/workflows/statistical-evidence-fetch.yml in GitHub
# Actions, where real network exists; this sandbox cannot reach it (reconfirmed this session).
# Fetches a real time series (not a single timepoint) for one indicator this corpus can use as
# AI_ENERGY_INFRA statistical context: electricity access/consumption-adjacent indicator for the US.
import json
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_PATH = Path("world_bank_fetch_results.json")

# EG.USE.ELEC.KH.PC = Electric power consumption (kWh per capita) -- a real, stable, documented
# World Bank indicator code (not guessed). Country USA. date range gives a real multi-point
# series (T0..Tn), not a single timepoint, per Section's explicit "2-3 values != trend" caution --
# this fetch alone does not declare a trend; that judgment is made separately with INSUFFICIENT_
# SERIES as the honest default if the series design doesn't support one.
INDICATOR = "EG.USE.ELEC.KH.PC"
COUNTRY = "USA"
DATE_RANGE = "2010:2022"
URL = f"https://api.worldbank.org/v2/country/{COUNTRY}/indicator/{INDICATOR}?date={DATE_RANGE}&format=json&per_page=100"

USER_AGENT = "Mozilla/5.0 (compatible; METAXIS-StatisticalEvidence-M6/1.0; +https://github.com)"


def fetch():
    req = urllib.request.Request(URL, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            status_code = resp.getcode()
            raw = resp.read(2_000_000)
            body = raw.decode("utf-8", errors="replace")
    except Exception as e:
        return {"url": URL, "indicator": INDICATOR, "country": COUNTRY, "http_status": None,
                "fetch_result": "FAILED", "error": repr(e), "observations": []}

    result = {"url": URL, "indicator": INDICATOR, "country": COUNTRY, "http_status": status_code,
              "fetch_result": "OK" if status_code == 200 else "FAILED", "observations": []}
    if status_code != 200:
        return result
    try:
        parsed = json.loads(body)
    except Exception as e:
        result["fetch_result"] = "FAILED"
        result["error"] = f"JSON_PARSE_FAILED: {e!r}"
        return result
    # World Bank's documented response shape: [metadata, [records]]
    if not isinstance(parsed, list) or len(parsed) < 2 or parsed[1] is None:
        result["fetch_result"] = "NO_RESULT"
        result["raw_response_head"] = body[:500]
        return result
    records = parsed[1]
    observations = []
    for rec in records:
        if rec.get("value") is not None:
            observations.append({"period": rec.get("date"), "value": rec.get("value"),
                                  "unit": rec.get("unit") or "kWh per capita",
                                  "indicator_name": (rec.get("indicator") or {}).get("value"),
                                  "country_name": (rec.get("country") or {}).get("value")})
    result["observations"] = sorted(observations, key=lambda o: o["period"])
    result["real_data_point_count"] = len(observations)
    return result


def main():
    result = fetch()
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
