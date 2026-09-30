#!/usr/bin/env python3
# PHASE M.5E-6 -- tests for fetch_real_counterevidence.py. Manual def test_...(): + bare assert,
# one file per subprocess (this repo's standing convention, see intel/historical_evidence/tests/
# test_fetch_real_historical_analogy_evidence.py). Zero LLM. No pytest/unittest. Never hits a
# live network -- every fetch here is a MOCKED fetcher function.
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CE_DIR = HERE.parent

sys.path.insert(0, str(CE_DIR))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load("fetch_real_counterevidence", CE_DIR / "fetch_real_counterevidence.py")


# ---------------------------------------------------------------------------------------------
# Helpers to build a fake Crossref "message.items" work + a mocked fetcher, matching
# fetch_crossref.py's real documented envelope shape exactly.
def _work(doi, title, abstract="", year=2020):
    return {
        "DOI": doi,
        "title": [title],
        "author": [{"given": "A.", "family": "Researcher"}],
        "abstract": abstract,
        "published": {"date-parts": [[year, 1, 1]]},
        "container-title": ["Journal of Energy Systems"],
        "URL": f"https://doi.org/{doi}",
        "type": "journal-article",
    }


def _mock_fetcher(items_by_url):
    def fetcher(url):
        for key, items in items_by_url.items():
            if key in url:
                return {
                    "ok": True, "status": "FETCH_OK", "status_code": 200,
                    "resolved_url": url,
                    "data": {"status": "ok", "message": {"items": items}},
                }
        return {"ok": True, "status": "FETCH_OK", "status_code": 200, "resolved_url": url,
                "data": {"status": "ok", "message": {"items": []}}}
    return fetcher


def _doc(title, abstract=None, doi="10.1000/x"):
    return {
        "document_id": f"crossref_{doi.replace('/', '_')}",
        "title": title,
        "abstract_excerpt": abstract,
        "doi": doi,
        "published": "2020-01-01",
        "source_id": "src_crossref",
        "source_name": "Crossref REST API",
        "canonical_url": f"https://doi.org/{doi}",
    }


# ---------------------------------------------------------------------------------------------
# (1) Genuinely counter-narrative candidates per direction get admitted -- at least 2 directions.
def test_genuine_efficiency_offset_candidate_is_admitted():
    doc = _doc(
        "Data Center Power Usage Effectiveness Gains Are Decoupling Energy Use From Compute Growth",
        abstract=(
            "This study finds that data center efficiency gains outpace compute demand growth, "
            "with power usage effectiveness improvements decoupling energy use from workload growth."
        ),
    )
    result = mod.admission_gate_check(doc)
    assert result["verdict"] == "REAL_COUNTEREVIDENCE_ADMITTED", result
    assert result["reason_code"] == "COUNTER_NARRATIVE_CONFIRMED"
    assert result["counterevidence_direction"] == "EFFICIENCY_IMPROVEMENTS"


def test_genuine_demand_overestimation_candidate_is_admitted():
    doc = _doc(
        "Electricity Demand Forecasts for Data Centers Revised Down",
        abstract=(
            "Actual electricity demand growth from data centers has been lower than projected; "
            "forecasters have revised down their demand forecast for the sector."
        ),
    )
    result = mod.admission_gate_check(doc)
    assert result["verdict"] == "REAL_COUNTEREVIDENCE_ADMITTED", result
    assert result["reason_code"] == "COUNTER_NARRATIVE_CONFIRMED"
    assert result["counterevidence_direction"] == "DEMAND_OVERESTIMATION"


def test_genuine_workload_shifting_candidate_is_admitted():
    doc = _doc(
        "Demand Response Programs Shift AI Workloads to Off-Peak Hours",
        abstract=(
            "A demand response program successfully shifted data center workloads to off-peak "
            "hours, which reduced peak load on the regional grid."
        ),
    )
    result = mod.admission_gate_check(doc)
    assert result["verdict"] == "REAL_COUNTEREVIDENCE_ADMITTED", result
    assert result["counterevidence_direction"] == "WORKLOAD_SHIFTING"


def test_genuine_renewable_offset_candidate_is_admitted():
    doc = _doc(
        "Renewable Energy Procurement Offsets Data Center Electricity Consumption",
        abstract=(
            "The operator's renewable power purchase agreement offsets its power use, matched "
            "with renewable energy to offset its data center's electricity consumption."
        ),
    )
    result = mod.admission_gate_check(doc)
    assert result["verdict"] == "REAL_COUNTEREVIDENCE_ADMITTED", result
    assert result["counterevidence_direction"] == "RENEWABLE_PROCUREMENT"


# ---------------------------------------------------------------------------------------------
# (2) THE MOST IMPORTANT TEST -- directly modeled on the historical-evidence lesson: a document
# that is merely TOPICALLY about the same subject (efficiency / renewables) but is actually about
# the demand-growth narrative itself (efficiency gains being insufficient, or a PPA meeting NEW
# demand) must be rejected with a clear, specific reason code -- never admitted.
def test_efficiency_insufficient_to_offset_growth_is_rejected_as_confirming_growth():
    doc = _doc(
        "AI Data Centers Are Straining the Grid Despite Efficiency Gains",
        abstract=(
            "Even as operators report efficiency gains and more efficient chips, AI data centers "
            "are straining the grid; efficiency improvements have been insufficient to offset "
            "the surging electricity demand from AI workloads."
        ),
    )
    result = mod.admission_gate_check(doc)
    assert result["verdict"] == "REAL_COUNTEREVIDENCE_REJECTED", result
    assert result["reason_code"] == "CONFIRMS_GROWTH_NARRATIVE_NOT_COUNTER", result
    assert result["counterevidence_direction"] is None


def test_renewable_ppa_for_new_demand_is_rejected_not_counterevidence():
    doc = _doc(
        "Tech Company Signs New Solar Power Purchase Agreement to Power Growing Data Center Demand",
        abstract=(
            "The company signed a power purchase agreement for new renewable capacity to meet "
            "growing demand from its expanding data center fleet, as it announces investment in "
            "new data center electricity capacity."
        ),
    )
    result = mod.admission_gate_check(doc)
    assert result["verdict"] == "REAL_COUNTEREVIDENCE_REJECTED", result
    assert result["reason_code"] == "CONFIRMS_GROWTH_NARRATIVE_NOT_COUNTER", result


def test_demand_forecast_revised_upward_is_rejected_not_overestimation():
    doc = _doc(
        "Electricity Demand Forecasts Revised Upward as AI Adoption Accelerates",
        abstract="Grid operators revised their demand forecast upward, as demand exceeded forecasts.",
    )
    result = mod.admission_gate_check(doc)
    assert result["verdict"] == "REAL_COUNTEREVIDENCE_REJECTED", result
    assert result["reason_code"] == "CONFIRMS_GROWTH_NARRATIVE_NOT_COUNTER", result


def test_bare_topical_mention_with_no_stance_is_rejected_topical_only():
    doc = _doc(
        "A Survey of Data Center Energy Efficiency Metrics",
        abstract="This survey reviews common data center energy efficiency and PUE metrics used in industry.",
    )
    result = mod.admission_gate_check(doc)
    assert result["verdict"] == "REAL_COUNTEREVIDENCE_REJECTED", result
    assert result["reason_code"] == "NOT_COUNTER_NARRATIVE_TOPICAL_ONLY", result


def test_off_topic_document_is_rejected_not_topically_relevant():
    doc = _doc(
        "A Historical Study of 19th Century Textile Manufacturing",
        abstract="This paper examines textile manufacturing practices in the 19th century.",
    )
    result = mod.admission_gate_check(doc)
    assert result["verdict"] == "REAL_COUNTEREVIDENCE_REJECTED", result
    assert result["reason_code"] == "NOT_TOPICALLY_RELEVANT", result


# ---------------------------------------------------------------------------------------------
# (3) A non-200 / failed fetch is a clean failure never promoted to success.
def test_failed_fetch_is_never_promoted_to_success():
    def failing_fetcher(url):
        return {"ok": False, "status": "FETCH_FAILED", "status_code": 500, "error": "server error"}

    summary = mod.fetch_and_canonicalize_term("data center energy efficiency improvement",
                                               fetcher=failing_fetcher)
    for r in summary["results"]:
        assert r["overall_status"] == "FETCH_FAILED"
        assert r["documents_canonicalized"] == []


def test_not_found_fetch_is_never_promoted_to_success():
    def not_found_fetcher(url):
        return {"ok": True, "status": "FETCH_OK", "status_code": 200, "resolved_url": url,
                "data": {"status": "ok", "message": {"items": []}}}

    summary = mod.fetch_and_canonicalize_term("electricity demand forecast overestimate revised",
                                               fetcher=not_found_fetcher)
    for r in summary["results"]:
        assert r["overall_status"] == "NOT_FOUND"
        assert r["documents_canonicalized"] == []


# ---------------------------------------------------------------------------------------------
# (4) Zero admitted candidates means admission_gate is never called.
def test_zero_admitted_candidates_never_calls_admission_gate():
    calls = []

    def admit_fn_spy(shadow_result):
        calls.append(shadow_result)
        return {"admitted": 999}  # would be an obviously wrong/fabricated result if ever called

    fetcher = _mock_fetcher({
        "data%20center%20energy": [_work("10.1/a", "AI Data Centers Straining the Grid Despite Efficiency Gains",
                                          abstract="Efficiency gains insufficient to offset surging electricity demand.")],
        "demand%20response": [_work("10.1/b", "A Survey of Data Center Workload Scheduling Methods")],
        "renewable%20energy%20procurement": [_work("10.1/c", "Company Signs New Solar PPA to Meet Growing Data Center Demand",
                                                     abstract="New renewable capacity to meet growing demand.")],
        "electricity%20demand%20forecast": [_work("10.1/d", "A Historical Study of 19th Century Textile Manufacturing")],
    })

    pilot_result, admission_summary = mod.run_and_maybe_admit(
        fetcher=fetcher, admit_fn=admit_fn_spy,
        gate_log_path=HERE / "_tmp_gate_log_zero_admitted.json",
    )
    assert admission_summary is None
    assert calls == []
    assert all(v["verdict"] == "REAL_COUNTEREVIDENCE_REJECTED" for v in pilot_result["gate_verdicts"])

    (HERE / "_tmp_gate_log_zero_admitted.json").unlink(missing_ok=True)


def test_one_admitted_candidate_does_call_admission_gate_exactly_once():
    calls = []

    def admit_fn_spy(shadow_result):
        calls.append(shadow_result)
        assert len(shadow_result["results"]) == 1
        assert len(shadow_result["results"][0]["documents_canonicalized"]) == 1
        return {"admitted": 1, "candidates_seen": 1, "duplicate_existing": 0,
                "rejected": 0, "review_required": 0}

    fetcher = _mock_fetcher({
        "data%20center%20energy": [_work(
            "10.2/real1",
            "Data Center Efficiency Gains Outpace Compute Growth, Decoupling Energy Use",
            abstract="Efficiency gains outpace demand growth, decoupling energy use from workload growth.",
        )],
        "demand%20response": [],
        "renewable%20energy%20procurement": [],
        "electricity%20demand%20forecast": [],
    })

    pilot_result, admission_summary = mod.run_and_maybe_admit(
        fetcher=fetcher, admit_fn=admit_fn_spy,
        gate_log_path=HERE / "_tmp_gate_log_one_admitted.json",
    )
    assert len(calls) == 1
    assert admission_summary is not None
    assert admission_summary["admitted"] == 1

    log_path = HERE / "_tmp_gate_log_one_admitted.json"
    assert log_path.exists()
    log_data = json.loads(log_path.read_text(encoding="utf-8"))
    assert any(v["verdict"] == "REAL_COUNTEREVIDENCE_ADMITTED" for v in log_data)
    log_path.unlink(missing_ok=True)


# Gate log is append-only across runs.
def test_gate_log_is_append_only_across_runs():
    log_path = HERE / "_tmp_gate_log_append_only.json"
    log_path.write_text(json.dumps([{"document_id": "prior_run_row"}]), encoding="utf-8")
    try:
        mod._append_gate_log([{"document_id": "new_row"}], log_path=log_path)
        data = json.loads(log_path.read_text(encoding="utf-8"))
        ids = [row.get("document_id") for row in data]
        assert "prior_run_row" in ids
        assert "new_row" in ids
        assert len(data) == 2
    finally:
        log_path.unlink(missing_ok=True)


def test_never_writes_documents_json_directly():
    src = (CE_DIR / "fetch_real_counterevidence.py").read_text(encoding="utf-8")
    assert "DOCUMENTS_PATH" not in src
    assert not hasattr(mod, "DOCUMENTS_PATH")


def test_reuses_imported_counterevidence_directions_not_reforked():
    # The 4 direction names must come from the imported module, not a locally-redefined dict.
    assert set(mod.COUNTEREVIDENCE_DIRECTIONS.keys()) == {
        "EFFICIENCY_IMPROVEMENTS", "WORKLOAD_SHIFTING", "RENEWABLE_PROCUREMENT",
        "DEMAND_OVERESTIMATION",
    }
