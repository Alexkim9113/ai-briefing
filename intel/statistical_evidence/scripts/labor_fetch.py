"""N-0 SLICE 3 -- AI_LABOR live statistical fetch. Priority order per Te's instruction was
ILO -> World Bank -> OECD -> Korean official stats. ILO's SDMX API requires a dataflow/structure
query this session cannot safely validate without live access outside GitHub Actions (unlike the
World Bank REST API, already proven reliable in M.6). World Bank is used here as the first
PROVEN-reliable fallback, exactly as the instruction allows. The indicator is a plain labor
statistic (labor force participation rate) -- it carries NO AI-attribution by itself; a general
labor indicator change is never promoted to an AI effect (Section 6's explicit constraint)."""
import json
import urllib.request
import urllib.error

INDICATOR = "SL.TLF.ACTI.ZS"  # Labor force participation rate, total (% of population ages 15+)
COUNTRY = "USA"
URL = f"https://api.worldbank.org/v2/country/{COUNTRY}/indicator/{INDICATOR}?date=2010:2022&format=json&per_page=100"


def fetch():
    result = {"url": URL, "indicator": INDICATOR, "country": COUNTRY, "source_family": "WORLD_BANK",
              "ilo_attempted": False,
              "ilo_note": "ILO SDMX structure not validated outside live Actions this round; "
                           "World Bank used as the proven-reliable fallback per instruction's own priority list"}
    try:
        with urllib.request.urlopen(URL, timeout=20) as resp:
            status = resp.status
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        result.update({"http_status": e.code, "fetch_result": "FAILED", "observations": []})
        return result
    except Exception as e:
        result.update({"http_status": None, "fetch_result": "FAILED", "error": str(e), "observations": []})
        return result

    result["http_status"] = status
    if not isinstance(body, list) or len(body) < 2 or not body[1]:
        result.update({"fetch_result": "NO_RESULT", "observations": []})
        return result

    records = body[1]
    observations = []
    for r in records:
        if r.get("value") is None:
            continue
        observations.append({
            "period": r.get("date"), "value": r.get("value"), "unit": "% of population 15+",
            "indicator_name": r.get("indicator", {}).get("value"),
            "country_name": r.get("country", {}).get("value"),
        })
    observations.sort(key=lambda o: o["period"])
    result.update({"fetch_result": "OK" if observations else "NO_RESULT",
                   "observations": observations, "real_data_point_count": len(observations)})
    return result


def main():
    result = fetch()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    with open("labor_fetch_results.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
