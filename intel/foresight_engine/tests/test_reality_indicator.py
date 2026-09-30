# PHASE M.3 — Reality & Indicator Intelligence Layer tests. Manual def test_...(): + bare
# assert, this repo's convention (no pytest/unittest). Run standalone via importlib.util in its
# own process (see how run_tests.sh-equivalent invocations in this repo work).
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
SCRIPTS = PKG / "scripts"
sys.path.insert(0, str(PKG))

import reality_indicator as ri  # noqa: E402
import coverage  # noqa: E402
from hypothesis_indicator_bridge import (  # noqa: E402
    link_observable_implication, evaluate_hypothesis_against_observations,
    HYPOTHESIS_TEST_OUTCOMES, build_alternative_explanations,
    assess_reality_signal_for_structural_change,
)
from reality_source_independence import independent_indicator_count  # noqa: E402


def _ind(iid, **overrides):
    base = dict(
        canonical_name=iid, display_name=iid, domain="ECONOMY", source_id="src_" + iid,
        source_tier="TIER_1", source_organization="Org", unit="USD", frequency="ANNUAL",
        geography="COUNTRY", canonical_url=f"https://example.org/{iid}",
        seasonal_adjustment="NOT_ADJUSTED", price_basis="NOMINAL",
    )
    base.update(overrides)
    return ri.new_indicator(iid, **base)


# 1. Observation with no source -> rejected
def test_observation_with_no_source_rejected():
    try:
        ri.new_observation("o1", "ind1", "2025", 1.0, "USD", "OFFICIAL_REPORTED",
                            "2026-01-01T00:00:00Z", provenance_id=None)
        assert False, "should have raised"
    except ri.ObservationRejected:
        pass


# 2. Observation with no indicator_id -> rejected
def test_observation_with_no_indicator_id_rejected():
    try:
        ri.new_observation("o1", None, "2025", 1.0, "USD", "OFFICIAL_REPORTED",
                            "2026-01-01T00:00:00Z", provenance_id="prov1")
        assert False, "should have raised"
    except ri.ObservationRejected:
        pass


# 3. Official source trace works end-to-end: indicator -> dataset -> organization -> URL
def test_official_source_trace_end_to_end():
    ind = _ind("gdp_kr", dataset_name="WDI GDP", source_organization="World Bank",
               canonical_url="https://data.worldbank.org/indicator/NY.GDP.MKTP.CD")
    obs = ri.new_observation("obs_gdp_kr_2024", "gdp_kr", "2024", 1900000000000.0, "USD",
                              "OFFICIAL_REPORTED", "2026-01-01T00:00:00Z", provenance_id="prov1")
    citation = ri.build_citation("obs_gdp_kr_2024", {"obs_gdp_kr_2024": obs}, {"gdp_kr": ind})
    assert citation["incomplete"] is False
    assert citation["organization"] == "World Bank"
    assert citation["dataset"] == "WDI GDP"
    assert citation["source_url"].startswith("https://data.worldbank.org")


# 4. An article-quoted number never becomes PRIMARY_VERIFIED status automatically
def test_article_quoted_number_never_auto_primary_verified():
    ind = _ind("quoted_stat", verification_status="UNKNOWN")
    assert ind["verification_status"] != "PRIMARY_SOURCE_VERIFIED"
    assert ind["verification_status"] in ri.VERIFICATION_STATUSES
    # No function in this module ever flips UNKNOWN -> PRIMARY_SOURCE_VERIFIED automatically -
    # verified by grepping for any auto-assignment (none exists; verification_status is only
    # ever set by the caller's explicit kwarg).
    src = (PKG / "reality_indicator.py").read_text(encoding="utf-8")
    assert 'verification_status"] = "PRIMARY_SOURCE_VERIFIED"' not in src


# 5. retrieved_at is always present on any created observation
def test_retrieved_at_always_required():
    try:
        ri.new_observation("o", "ind1", "2025", 1.0, "USD", "OFFICIAL_REPORTED", None,
                            provenance_id="p1")
        assert False
    except ri.ObservationRejected:
        pass
    obs = ri.new_observation("o", "ind1", "2025", 1.0, "USD", "OFFICIAL_REPORTED",
                              "2026-01-01T00:00:00Z", provenance_id="p1")
    assert obs["retrieved_at"] == "2026-01-01T00:00:00Z"


# 6. period and publication_date/source_release_date are distinct fields, never conflated
def test_period_and_source_release_date_distinct():
    obs = ri.new_observation("o", "ind1", "2024-Q4", 1.0, "USD", "OFFICIAL_REPORTED",
                              "2026-01-01T00:00:00Z", provenance_id="p1",
                              source_release_date="2025-01-15")
    assert obs["period"] == "2024-Q4"
    assert obs["source_release_date"] == "2025-01-15"
    assert obs["period"] != obs["source_release_date"]


# 7. Comparability gate blocks a different-unit comparison
def test_comparability_gate_blocks_different_unit():
    a = _ind("a", unit="USD")
    b = _ind("b", unit="KRW")
    result = ri.check_comparability(a, b)
    assert result["status"] == "NOT_COMPARABLE"


# 8. Comparability gate flags a different-population comparison
def test_comparability_gate_flags_different_population():
    a = _ind("a", population="ADULTS_15_64")
    b = _ind("b", population="ADULTS_25_54")
    result = ri.check_comparability(a, b)
    assert result["status"] == "PARTIALLY_COMPARABLE"


# 9. Definition change -> NOT_COMPARABLE / flagged, never silently ignored
def test_definition_change_flagged():
    a = _ind("a", definition="unemployment rate, ILO definition")
    b = _ind("b", definition="unemployment rate, national definition")
    result = ri.check_comparability(a, b)
    assert result["status"] == "PARTIALLY_COMPARABLE"
    assert any("definition" in r for r in result["reasons"])


# 10. Series break detection/handling — calculation across a flagged break refuses or labels
def test_series_break_refused_without_override():
    result = ri.calc_across_series_break(ri.year_over_year, 110, 100, series_break=True)
    assert result["status"] == "SERIES_BREAK_REFUSED"
    assert result["value"] is None


def test_series_break_labeled_with_override():
    result = ri.calc_across_series_break(ri.year_over_year, 110, 100, series_break=True, override=True)
    assert result["status"] == "SERIES_BREAK_OVERRIDE"
    assert result["value"] is not None


# 11. Nominal vs real price_basis distinguished, never conflated in a calculation
def test_nominal_vs_real_price_basis_blocks_comparison():
    a = _ind("a", price_basis="NOMINAL")
    b = _ind("b", price_basis="REAL")
    result = ri.check_comparability(a, b)
    assert result["status"] == "NOT_COMPARABLE"


# 12. Seasonal adjustment difference is detected/flagged in comparability
def test_seasonal_adjustment_difference_flagged():
    a = _ind("a", seasonal_adjustment="SEASONALLY_ADJUSTED")
    b = _ind("b", seasonal_adjustment="NOT_ADJUSTED")
    result = ri.check_comparability(a, b)
    assert result["status"] == "NOT_COMPARABLE"


# 13. YoY/CAGR/etc are deterministic (same inputs -> same outputs, no LLM)
def test_calculations_deterministic():
    r1 = ri.year_over_year(110, 100)
    r2 = ri.year_over_year(110, 100)
    assert r1 == r2
    c1 = ri.cagr(100, 200, 5)
    c2 = ri.cagr(100, 200, 5)
    assert c1 == c2


# 14. Division-by-zero handled without crash or fabrication
def test_division_by_zero_handled():
    assert ri.year_over_year(110, 0)["status"] == "DIVISION_BY_ZERO"
    assert ri.year_over_year(110, 0)["value"] is None
    assert ri.share(5, 0)["status"] == "DIVISION_BY_ZERO"
    assert ri.ratio(5, 0)["status"] == "DIVISION_BY_ZERO"
    assert ri.index_value(5, 0, base_period="2020")["status"] == "DIVISION_BY_ZERO"


# 15. Missing observation period handled (no silent interpolation)
def test_missing_period_no_silent_interpolation():
    values = [("2020", 100.0), ("2021", ri.MISSING), ("2022", 120.0)]
    result = ri.moving_average(values, 3)
    assert result["status"] == "PARTIAL_WINDOW_MISSING_SKIPPED"
    assert "2021" in result["skipped_periods"]
    # never interpolated: average is of exactly the 2 real values, not a guessed 2021 value
    assert abs(result["value"] - 110.0) < 1e-9


# 16. Derived value always carries formula + input_observation_ids
def test_derived_value_carries_formula_and_inputs():
    calc = ri.year_over_year(110, 100)
    derived = ri.make_derived_observation(
        "derived_1", "ind1", "2025", calc, "PERCENT", "2026-01-01T00:00:00Z",
        formula="YoY = (current-previous)/previous", input_observation_ids=["o1", "o2"],
    )
    assert derived["formula"]
    assert derived["input_observation_ids"] == ["o1", "o2"]
    assert derived["status"] == "METAXIS_DERIVED"


# 17. Official vs derived status never confused
def test_official_vs_derived_never_confused():
    official = ri.new_observation("o1", "ind1", "2024", 100.0, "USD", "OFFICIAL_REPORTED",
                                   "2026-01-01T00:00:00Z", provenance_id="p1")
    derived = ri.make_derived_observation("o2", "ind1", "2025", ri.year_over_year(110, 100),
                                           "PERCENT", "2026-01-01T00:00:00Z", "YoY", ["o1"])
    assert official["status"] == "OFFICIAL_REPORTED"
    assert derived["status"] == "METAXIS_DERIVED"
    assert official["status"] != derived["status"]


# 18. missing/unknown/zero are three distinct, never-collapsed states
def test_missing_unknown_zero_distinct():
    assert ri.MISSING != 0
    assert ri.MISSING is not None
    assert ri.UNKNOWN_VALUE != 0
    assert ri.UNKNOWN_VALUE != ri.MISSING
    real_zero_obs = ri.new_observation("o1", "ind1", "2024", 0.0, "USD", "OFFICIAL_REPORTED",
                                        "2026-01-01T00:00:00Z", provenance_id="p1")
    assert real_zero_obs["value"] == 0.0
    assert real_zero_obs["value"] is not ri.MISSING
    calc = ri.year_over_year(ri.MISSING, 100)
    assert calc["value"] != 0
    assert calc["value"] is None
    assert calc["status"] == "MISSING_INPUT"


# 19. A data-absence gap classification never implies "phenomenon doesn't exist"
def test_gap_never_implies_phenomenon_absence():
    gaps = coverage.detect_reality_knowledge_gaps({}, {}, known_domains=("LABOR",))
    assert len(gaps) == 1
    assert gaps[0]["gap_class"] == "NOT_DISCOVERED"
    assert "does not exist" not in gaps[0]["reason"] or "does NOT imply" in gaps[0]["reason"]
    assert "does NOT imply the underlying phenomenon does not exist" in gaps[0]["reason"]


# 20. One consistent indicator alone never flips a hypothesis test result to VERIFIED-like
def test_single_consistent_indicator_never_verified_status():
    indicators = {"i1": _ind("i1")}
    link = link_observable_implication("hyp1", "employment falls", ["i1"], indicators)
    obs = [{"observation_id": "o1", "indicator_id": "i1", "value": -0.05}]
    result = evaluate_hypothesis_against_observations(
        link, {"i1": obs}, direction_fn=lambda o: "FOR")
    assert result["outcome"] in HYPOTHESIS_TEST_OUTCOMES
    assert result["outcome"] == "CONSISTENT_WITH"
    assert result["outcome"] not in ("VERIFIED", "CONFIRMED")


# 21. Counter-indicators are preserved alongside supporting ones, never dropped
def test_counter_indicators_preserved_alongside_supporting():
    indicators = {"i1": _ind("i1"), "i2": _ind("i2")}
    link = link_observable_implication("hyp1", "impl", ["i1", "i2"], indicators)
    obs_i1 = [{"observation_id": "o1", "indicator_id": "i1", "value": -0.05}]
    obs_i2 = [{"observation_id": "o2", "indicator_id": "i2", "value": 0.05}]

    def direction(o):
        return "FOR" if o["indicator_id"] == "i1" else "AGAINST"

    result = evaluate_hypothesis_against_observations(
        link, {"i1": obs_i1, "i2": obs_i2}, direction_fn=direction)
    assert result["outcome"] == "MIXED"
    assert len(result["supporting_indicators"]) == 1
    assert len(result["counter_indicators"]) == 1


# 22. Conflicting data from two sources preserved as DATA_CONFLICT, never auto-averaged
def test_conflicting_data_preserved_not_averaged():
    obs_a = {"observation_id": "oa", "indicator_id": "i1", "value": 100.0, "source": "SRC_A"}
    obs_b = {"observation_id": "ob", "indicator_id": "i1", "value": 150.0, "source": "SRC_B"}
    conflict = {"status": "DATA_CONFLICT", "values": [obs_a, obs_b]}
    assert conflict["status"] == "DATA_CONFLICT"
    assert len(conflict["values"]) == 2
    computed_average = (obs_a["value"] + obs_b["value"]) / 2
    assert conflict["values"][0]["value"] != computed_average
    assert conflict["values"][1]["value"] != computed_average
    assert "average" not in conflict


# 23. No causal-language field/status is ever produced by comparing two indicators
def test_no_causal_language_ever_produced():
    a = _ind("a"); b = _ind("b")
    result = ri.check_comparability(a, b)
    assert "causes" not in str(result).lower()
    assert "caused_by" not in str(result).lower()
    for outcome in HYPOTHESIS_TEST_OUTCOMES:
        assert "cause" not in outcome.lower()


# 24. A proprietary/licensed raw dataset never appears in the public-export-facing function
def test_proprietary_dataset_excluded_from_public_export():
    restricted = _ind("restricted", license="PROPRIETARY_NO_REDISTRIBUTION")
    ok = _ind("ok", license="CC-BY-4.0")
    registry = {"restricted": restricted, "ok": ok}
    public = ri.build_public_indicator_export(registry)
    assert "restricted" not in public
    assert "ok" in public


# 25. Attribution/citation metadata is preserved end to end
def test_citation_metadata_preserved_end_to_end():
    ind = _ind("i1", source_organization="Bank of Korea", dataset_name="ECOS 722Y001",
               canonical_url="https://ecos.bok.or.kr/")
    obs = ri.new_observation("o1", "i1", "2024", 3.5, "PERCENT", "OFFICIAL_REPORTED",
                              "2026-01-01T00:00:00Z", provenance_id="p1")
    citation = ri.build_citation("o1", {"o1": obs}, {"i1": ind})
    assert citation["organization"] == "Bank of Korea"
    assert citation["dataset"] == "ECOS 722Y001"
    assert citation["source_url"] == "https://ecos.bok.or.kr/"
    assert citation["period"] == "2024"


def test_citation_refuses_for_incomplete_indicator():
    ind = _ind("i1", source_organization=None, canonical_url=None)
    obs = ri.new_observation("o1", "i1", "2024", 3.5, "PERCENT", "OFFICIAL_REPORTED",
                              "2026-01-01T00:00:00Z", provenance_id="p1")
    citation = ri.build_citation("o1", {"o1": obs}, {"i1": ind})
    assert citation["incomplete"] is True


def test_citation_none_for_unknown_observation():
    assert ri.build_citation("does_not_exist", {}, {}) is None


# 26. Zero LLM calls (grep test, matching existing style) — covers reality_indicator.py,
# reality_source_independence.py, hypothesis_indicator_bridge.py, and the scripts/ subdir
# (not covered by test_fixture.py's PKG.glob("*.py"), which only scans the top-level dir).
def test_zero_llm_calls_in_reality_modules():
    forbidden = ("anthropic.Anthropic(", "anthropic.Client(", "openai.OpenAI(", "openai.Client(",
                 "google.generativeai", "genai.configure", "call_claude(")
    files = [PKG / "reality_indicator.py", PKG / "reality_source_independence.py",
             PKG / "hypothesis_indicator_bridge.py"]
    files += sorted(SCRIPTS.glob("*.py"))
    for path in files:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"found forbidden LLM-call symbol {token!r} in {path}"


# ---------------------------------------------------------------------------
# Extra coverage: alternative explanations, reality signal, source independence, comparability
# UNKNOWN, PROXY_INDICATOR marking, public export helper edge cases.
# ---------------------------------------------------------------------------
def test_alternative_explanations_never_evidence_free():
    out = build_alternative_explanations(
        "employment fell in sector X",
        ["AI_AUTOMATION", "ECONOMIC_DOWNTURN", "OFFSHORING"],
        {"AI_AUTOMATION": ["e1"], "ECONOMIC_DOWNTURN": []},  # OFFSHORING has no evidence
    )
    explanations = {o["explanation"] for o in out}
    assert explanations == {"AI_AUTOMATION"}


def test_reality_signal_insufficient_when_no_results():
    result = assess_reality_signal_for_structural_change("sc1", [])
    assert result["signal"] == "REALITY_INSUFFICIENT"


def test_reality_signal_never_auto_mutates_anything():
    result = assess_reality_signal_for_structural_change("sc1", [
        {"outcome": "CONSISTENT_WITH", "supporting_indicators": [], "counter_indicators": [],
         "ambiguous_indicators": [], "observable_implication": "x", "hypothesis_id": "h1",
         "comparability_status": "COMPARABLE"},
    ])
    assert result["signal"] == "REALITY_SUPPORT"
    assert "does not approve/mutate" in result["note"]


def test_comparability_unknown_when_fields_unknown():
    a = _ind("a", geography="UNKNOWN")
    b = _ind("b")
    result = ri.check_comparability(a, b)
    assert result["status"] == "UNKNOWN"


def test_comparability_unknown_for_missing_indicator():
    assert ri.check_comparability(None, _ind("a"))["status"] == "UNKNOWN"


def test_proxy_indicator_never_conflated_with_concept():
    ind = ri.new_indicator(
        "proxy1", "patent_filings", "Patent Filings (proxy)", "INTELLECTUAL_PROPERTY",
        "src1", "TIER_1", "WIPO", "COUNT", "ANNUAL", "COUNTRY",
        proxy_of_concept="KNOWLEDGE_SCARCITY",
    )
    assert ind["proxy_kind"] == "PROXY_INDICATOR"
    assert ind["proxy_of_concept"] == "KNOWLEDGE_SCARCITY"
    assert ind["concept"] != ind["proxy_of_concept"]  # never silently equated


def test_independent_indicator_count_never_exceeds_raw_count():
    indicators = {
        "i1": _ind("i1", source_id="same_src", canonical_url="https://x.org/a"),
        "i2": _ind("i2", source_id="same_src", canonical_url="https://x.org/a"),
        "i3": _ind("i3", source_id="other_src", canonical_url="https://y.org/b"),
    }
    count = independent_indicator_count(["i1", "i2", "i3"], indicators)
    assert count <= 3
    assert count >= 1


def test_reality_coverage_matrix_never_collapses_missing_to_zero_count_field():
    indicators = {"i1": _ind("i1", domain="LABOR")}
    matrix = coverage.build_reality_coverage_matrix(indicators, {})
    assert matrix["by_domain"]["LABOR"] == 1
    assert matrix["indicators_with_zero_observations"] == ["i1"]


# ---------------------------------------------------------------------------
# Real-response parsing (Phase M.3 completion step). SYNTHETIC-SCHEMA-VERIFIED: these fixtures
# are hand-built to match each API's own well-documented, stable real response shape - they are
# NOT captured from a live call (the sandbox cannot reach these hosts), so these tests prove the
# parser is correct against the documented contract, not that the exact live response of any
# particular day parses. A live-network-verified confirmation is a separate, later claim (a real
# GitHub Actions run of fetch_reality_indicators.py), never conflated with this one.
# ---------------------------------------------------------------------------

WORLDBANK_FIXTURE_NORMAL = [
    {"page": 1, "pages": 1, "per_page": 5, "total": 2, "sourceid": "2", "lastupdated": "2026-07-01"},
    [
        {"indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP (current US$)"},
         "country": {"id": "KR", "value": "Korea, Rep."}, "countryiso3code": "KOR",
         "date": "2025", "value": 1870000000000.0, "unit": "", "obs_status": "", "decimal": 0},
        {"indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP (current US$)"},
         "country": {"id": "KR", "value": "Korea, Rep."}, "countryiso3code": "KOR",
         "date": "2024", "value": 1712000000000.0, "unit": "", "obs_status": "", "decimal": 0},
    ],
]

WORLDBANK_FIXTURE_NULL_VALUE = [
    {"page": 1, "pages": 1, "per_page": 5, "total": 1, "sourceid": "2", "lastupdated": "2026-07-01"},
    [
        {"indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP (current US$)"},
         "country": {"id": "KR", "value": "Korea, Rep."}, "countryiso3code": "KOR",
         "date": "2026", "value": None, "unit": "", "obs_status": "", "decimal": 0},
    ],
]


def test_worldbank_parse_normal_response_creates_correct_observation():
    obs, reason = ri.parse_worldbank_observation(
        WORLDBANK_FIXTURE_NORMAL, indicator_id="ind_worldbank_kr_gdp_current_usd", unit="USD",
        retrieved_at="2026-09-30T00:00:00+00:00", provenance_id="prov1",
    )
    assert reason == "OK"
    assert obs["value"] == 1870000000000.0
    assert obs["unit"] == "USD"
    assert obs["period"] == "2025"
    assert obs["status"] == "OFFICIAL_REPORTED"
    assert obs["source_release_date"] == "2026-07-01"
    assert obs["provenance_id"] == "prov1"


def test_worldbank_null_value_becomes_missing_never_zero():
    obs, reason = ri.parse_worldbank_observation(
        WORLDBANK_FIXTURE_NULL_VALUE, indicator_id="ind_x", unit="USD",
        retrieved_at="2026-09-30T00:00:00+00:00", provenance_id="prov1",
    )
    assert reason == "OK"
    assert obs["value"] is ri.MISSING
    assert obs["value"] != 0


def test_worldbank_malformed_shape_fails_closed_never_crashes():
    for bad in [{}, [], [{}], [{}, {}], "not json at all", [{}, "not a list"], None]:
        obs, reason = ri.parse_worldbank_observation(
            bad, indicator_id="ind_x", unit="USD",
            retrieved_at="2026-09-30T00:00:00+00:00", provenance_id="prov1",
        )
        assert obs is None
        assert reason in ("SCHEMA_CHANGED", "PARSE_FAILED", "NO_DATA_ROWS")


def test_worldbank_empty_data_array_is_no_data_rows_not_crash():
    obs, reason = ri.parse_worldbank_observation(
        [{"lastupdated": "2026-01-01"}, []], indicator_id="ind_x", unit="USD",
        retrieved_at="2026-09-30T00:00:00+00:00", provenance_id="prov1",
    )
    assert obs is None
    assert reason == "NO_DATA_ROWS"


ECOS_FIXTURE_NORMAL = {
    "StatisticSearch": {
        "list_total_count": 1,
        "row": [
            {"STAT_CODE": "722Y001", "STAT_NAME": "Base Rate", "ITEM_CODE1": "0101000",
             "ITEM_NAME1": "Base Rate", "UNIT_NAME": "%", "TIME": "20260801",
             "DATA_VALUE": "3.25"},
        ],
    },
}

ECOS_FIXTURE_MISSING_VALUE = {
    "StatisticSearch": {
        "list_total_count": 1,
        "row": [
            {"STAT_CODE": "722Y001", "STAT_NAME": "Base Rate", "ITEM_CODE1": "0101000",
             "ITEM_NAME1": "Base Rate", "UNIT_NAME": "%", "TIME": "20260801",
             "DATA_VALUE": ""},
        ],
    },
}


def test_ecos_parse_normal_response_creates_correct_observation():
    obs, reason, precision = ri.parse_ecos_observation(
        ECOS_FIXTURE_NORMAL, indicator_id="ind_ecos_kr_base_rate",
        retrieved_at="2026-09-30T00:00:00+00:00", provenance_id="prov2",
    )
    assert reason == "OK"
    assert obs["value"] == 3.25
    assert obs["unit"] == "%"
    assert obs["period"] == "20260801"
    assert precision == "DAY"
    assert obs["status"] == "OFFICIAL_REPORTED"
    assert obs["provenance_id"] == "prov2"


def test_ecos_missing_data_value_becomes_missing_never_zero():
    obs, reason, precision = ri.parse_ecos_observation(
        ECOS_FIXTURE_MISSING_VALUE, indicator_id="ind_x",
        retrieved_at="2026-09-30T00:00:00+00:00", provenance_id="prov2",
    )
    assert reason == "OK"
    assert obs["value"] is ri.MISSING
    assert obs["value"] != 0


def test_ecos_malformed_shape_fails_closed_never_crashes():
    for bad in [{}, {"StatisticSearch": {}}, {"StatisticSearch": {"row": "not a list"}},
                {"StatisticSearch": {"row": []}}, None, "not json", 42]:
        obs, reason, precision = ri.parse_ecos_observation(
            bad, indicator_id="ind_x", retrieved_at="2026-09-30T00:00:00+00:00",
            provenance_id="prov2",
        )
        assert obs is None
        assert reason in ("SCHEMA_CHANGED", "PARSE_FAILED", "NO_DATA_ROWS")


def test_m5_worldbank_regression_lock_never_touched():
    # PHASE M.5 Priority 5: ECOS returned SCHEMA_CHANGED on the real live GitHub Actions run
    # (M.3V), and this sandbox has no live network access to observe ECOS's real response body,
    # so no evidence-based ECOS fix was possible this round (left as SCHEMA_CHANGED, untouched).
    # This is a regression lock proving the World Bank path (LIVE VERIFIED in M.3V against a
    # real 2025 Korea GDP value matching this fixture's 1.87e12 USD) was not touched or altered
    # while investigating ECOS. If this test ever fails, the World Bank parser regressed.
    obs, reason = ri.parse_worldbank_observation(
        WORLDBANK_FIXTURE_NORMAL, indicator_id="ind_worldbank_kr_gdp_current_usd", unit="USD",
        retrieved_at="2026-09-30T00:00:00+00:00", provenance_id="prov1",
    )
    assert reason == "OK"
    assert obs["value"] == 1870000000000.0
    assert obs["period"] == "2025"
    assert obs["status"] == "OFFICIAL_REPORTED"

    # ECOS malformed/undocumented-shape fixtures still fail closed exactly as before — no
    # guessed alternate schema was introduced.
    for bad in [{}, {"StatisticSearch": {}}, {"StatisticSearch": {"row": "not a list"}}]:
        eobs, ereason, _ = ri.parse_ecos_observation(
            bad, indicator_id="ind_x", retrieved_at="2026-09-30T00:00:00+00:00",
            provenance_id="prov2",
        )
        assert eobs is None
        assert ereason == "SCHEMA_CHANGED"


def test_ecos_temporal_precision_inferred_honestly():
    assert ri._infer_ecos_temporal_precision("20260801") == "DAY"
    assert ri._infer_ecos_temporal_precision("202608") == "MONTH"
    assert ri._infer_ecos_temporal_precision("2026") == "YEAR"
    assert ri._infer_ecos_temporal_precision("abcxyz12") == "UNKNOWN"
    assert ri._infer_ecos_temporal_precision(None) == "UNKNOWN"
