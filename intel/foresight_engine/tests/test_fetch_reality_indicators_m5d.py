# PHASE M.5D -- tests for the two NEW World Bank indicator sources added to
# fetch_reality_indicators.py's SOURCES list (electric power consumption per capita, R&D
# expenditure % of GDP). Reuses reality_indicator.py's real, generic
# parse_worldbank_observation() -- these are not a new parser, just new source rows routed
# through the same generic World Bank parsing path (source_id.startswith("worldbank_")).
# Manual def test_...(): + bare assert, run in its own subprocess, matching this repo's
# convention (see intel/foresight_engine/tests/test_fixture.py).
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
sys.path.insert(0, str(PKG))
sys.path.insert(0, str(PKG / "scripts"))

import reality_indicator as ri  # noqa: E402
import fetch_reality_indicators as fri  # noqa: E402

# A real, documented World Bank Indicators API response shape: [metadata, data_rows].
# Values below are illustrative fixture numbers (clearly not live-fetched), used only to prove
# the parser/schema-routing works -- never written into documents.json or any canonical file.
WORLDBANK_SAMPLE_ELECTRIC = [
    {"page": 1, "pages": 1, "per_page": 5, "total": 5},
    [
        {"indicator": {"id": "EG.USE.ELEC.KH.PC", "value": "Electric power consumption (kWh per capita)"},
         "country": {"id": "KR", "value": "Korea, Rep."}, "date": "2023", "value": 10500.4},
        {"indicator": {"id": "EG.USE.ELEC.KH.PC", "value": "Electric power consumption (kWh per capita)"},
         "country": {"id": "KR", "value": "Korea, Rep."}, "date": "2022", "value": None},
    ],
]

WORLDBANK_SAMPLE_RD = [
    {"page": 1, "pages": 1, "per_page": 5, "total": 5},
    [
        {"indicator": {"id": "GB.XPD.RSDV.GD.ZS", "value": "R&D expenditure (% of GDP)"},
         "country": {"id": "KR", "value": "Korea, Rep."}, "date": "2022", "value": 4.93},
    ],
]


def test_new_sources_present_and_distinct_from_m3_gdp_series():
    ids = [s["source_id"] for s in fri.SOURCES]
    assert "worldbank_electric_power_consumption_kr" in ids
    assert "worldbank_rd_expenditure_gdp_kr" in ids
    # never the same indicator code as the M.3 GDP pilot
    elec = next(s for s in fri.SOURCES if s["source_id"] == "worldbank_electric_power_consumption_kr")
    rd = next(s for s in fri.SOURCES if s["source_id"] == "worldbank_rd_expenditure_gdp_kr")
    gdp = next(s for s in fri.SOURCES if s["source_id"] == "worldbank_gdp_kr")
    assert "EG.USE.ELEC.KH.PC" in elec["url"]
    assert "GB.XPD.RSDV.GD.ZS" in rd["url"]
    assert elec["url"] != gdp["url"] and rd["url"] != gdp["url"]
    assert elec["domain"] == "ENERGY"
    assert rd["domain"] == "SCIENCE"


def test_electric_power_consumption_parses_via_generic_worldbank_parser():
    obs, reason = ri.parse_worldbank_observation(
        WORLDBANK_SAMPLE_ELECTRIC, indicator_id="ind_worldbank_kr_electric_power_consumption_pc",
        unit="KWH_PER_CAPITA", retrieved_at="2026-09-30T00:00:00+00:00",
        provenance_id="prov_test_elec", geography="COUNTRY",
    )
    assert reason == "OK"
    assert obs is not None
    assert obs["value"] == 10500.4
    assert obs["period"] == "2023"
    assert obs["status"] == "OFFICIAL_REPORTED"


def test_rd_expenditure_parses_via_generic_worldbank_parser():
    obs, reason = ri.parse_worldbank_observation(
        WORLDBANK_SAMPLE_RD, indicator_id="ind_worldbank_kr_rd_expenditure_gdp_pct",
        unit="PERCENT_OF_GDP", retrieved_at="2026-09-30T00:00:00+00:00",
        provenance_id="prov_test_rd", geography="COUNTRY",
    )
    assert reason == "OK"
    assert obs is not None
    assert obs["value"] == 4.93


def test_run_pilot_routes_all_worldbank_sources_through_worldbank_parser():
    # A fake fetcher returning the right fixture per URL -- proves run_pilot()'s
    # `source_id.startswith("worldbank_")` routing (not a single hardcoded id) reaches every
    # worldbank_* source, not just the original worldbank_gdp_kr.
    def fake_fetcher(url):
        if "EG.USE.ELEC.KH.PC" in url:
            return {"ok": True, "data": WORLDBANK_SAMPLE_ELECTRIC}
        if "GB.XPD.RSDV.GD.ZS" in url:
            return {"ok": True, "data": WORLDBANK_SAMPLE_RD}
        if "NY.GDP.MKTP.CD" in url:
            return {"ok": True, "data": [{"page": 1}, [{"date": "2023", "value": 1.7e12}]]}
        return {"ok": False, "error": "not mocked in this test: ECOS path untouched by M.5D"}

    orig_fetcher = fri.real_json_fetcher
    fri.real_json_fetcher = fake_fetcher
    try:
        summary = fri.run_pilot()
    finally:
        fri.real_json_fetcher = orig_fetcher

    worldbank_results = [r for r in summary["results"] if r["source_id"].startswith("worldbank_")]
    assert len(worldbank_results) == 3
    for r in worldbank_results:
        assert r["fetch_succeeded"] is True
        assert r["observation_created"] is not None, r["source_id"]


def main():
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
