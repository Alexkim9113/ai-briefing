# PHASE M.5E-5 -- tests for fetch_real_historical_analogy_evidence.py. Manual def test_...(): +
# bare assert, one file per subprocess (this repo's standing convention). Zero LLM. No
# pytest/unittest. Never hits a live network -- every fetch here is a MOCKED fetcher function.
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HIST_EVIDENCE_DIR = HERE.parent

sys.path.insert(0, str(HIST_EVIDENCE_DIR))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load("fetch_real_historical_analogy_evidence",
            HIST_EVIDENCE_DIR / "fetch_real_historical_analogy_evidence.py")


# ---------------------------------------------------------------------------------------------
# Helpers to build a fake Crossref "message.items" work + a mocked fetcher, matching
# fetch_crossref.py's real documented envelope shape exactly.
def _work(doi, title, abstract="", year=2015):
    return {
        "DOI": doi,
        "title": [title],
        "author": [{"given": "A.", "family": "Historian"}],
        "abstract": abstract,
        "published": {"date-parts": [[year, 1, 1]]},
        "container-title": ["Journal of Infrastructure History"],
        "URL": f"https://doi.org/{doi}",
        "type": "journal-article",
    }


def _mock_fetcher(items_by_url):
    """Returns a fetcher function that returns FETCH_OK + the given items for a URL containing
    a matching substring key, or a clean NOT_FOUND-shaped failure otherwise. Never touches the
    network."""
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


# ---------------------------------------------------------------------------------------------
# (1) A paper that's genuinely historical + relevant gets admitted.
def test_genuinely_historical_and_relevant_paper_is_admitted():
    doc = {
        "document_id": "crossref_10.1000_hist1",
        "title": "Rural Electrification and Grid Capacity in the 1930s United States",
        "abstract_excerpt": (
            "This historical case study examines how the Rural Electrification Administration "
            "expanded electricity grid capacity to farm cooperatives in the 1930s and 1940s."
        ),
        "doi": "10.1000/hist1",
        "published": "1998-01-01",
        "source_id": "src_crossref",
        "source_name": "Crossref REST API",
        "canonical_url": "https://doi.org/10.1000/hist1",
    }
    result = mod.admission_gate_check(doc)
    assert result["verdict"] == "REAL_HISTORICAL_EVIDENCE_ADMITTED", result
    assert result["reason_code"] == "HISTORICAL_AND_INFRA_RELEVANT"
    assert "RURAL_ELECTRIFICATION" in result["cross_referenced_analogies"]


# (2) A paper that's a current AI-energy-policy item (not historical) gets rejected with a clear
# reason.
def test_current_ai_energy_policy_item_is_rejected_not_historical():
    doc = {
        "document_id": "crossref_10.1000_current1",
        "title": "Tech Company Announces Investment in New Data Center Electricity Capacity",
        "abstract_excerpt": (
            "This year the company announced a billion investment in new data center power "
            "capacity and signs a power purchase agreement with a regional utility."
        ),
        "doi": "10.1000/current1",
        "published": "2026-06-01",
        "source_id": "src_crossref",
        "source_name": "Crossref REST API",
        "canonical_url": "https://doi.org/10.1000/current1",
    }
    result = mod.admission_gate_check(doc)
    assert result["verdict"] == "REAL_HISTORICAL_EVIDENCE_REJECTED", result
    assert result["reason_code"] == "CURRENT_AI_ENERGY_NEWS_NOT_HISTORICAL"
    assert "current" in result["reason"].lower() or "forward-looking" in result["reason"].lower()


def test_on_topic_but_no_historical_framing_is_rejected_generic():
    doc = {
        "document_id": "crossref_10.1000_generic1",
        "title": "A Survey of Electricity Grid Capacity Planning Methods",
        "abstract_excerpt": "We review current methods for planning electricity grid capacity.",
        "doi": "10.1000/generic1",
        "published": "2020-01-01",
        "source_id": "src_crossref",
        "source_name": "Crossref REST API",
        "canonical_url": "https://doi.org/10.1000/generic1",
    }
    result = mod.admission_gate_check(doc)
    assert result["verdict"] == "REAL_HISTORICAL_EVIDENCE_REJECTED", result
    assert result["reason_code"] == "NOT_HISTORICAL_FRAMING"


def test_historical_framing_but_off_topic_is_rejected_not_infra_relevant():
    doc = {
        "document_id": "crossref_10.1000_offtopic1",
        "title": "A Historical Case Study of 19th Century Literature",
        "abstract_excerpt": "This historical analysis examines 19th century novels.",
        "doi": "10.1000/offtopic1",
        "published": "2001-01-01",
        "source_id": "src_crossref",
        "source_name": "Crossref REST API",
        "canonical_url": "https://doi.org/10.1000/offtopic1",
    }
    result = mod.admission_gate_check(doc)
    assert result["verdict"] == "REAL_HISTORICAL_EVIDENCE_REJECTED", result
    assert result["reason_code"] == "NOT_INFRA_RELEVANT"


# (3) A non-200 / failed fetch is a clean failure never promoted to success.
def test_failed_fetch_is_never_promoted_to_success():
    def failing_fetcher(url):
        return {"ok": False, "status": "FETCH_FAILED", "status_code": 500, "error": "server error"}

    summary = mod.fetch_and_canonicalize_term("rural electrification grid capacity",
                                               fetcher=failing_fetcher)
    for r in summary["results"]:
        assert r["overall_status"] == "FETCH_FAILED"
        assert r["documents_canonicalized"] == []


def test_not_found_fetch_is_never_promoted_to_success():
    def not_found_fetcher(url):
        return {"ok": True, "status": "FETCH_OK", "status_code": 200, "resolved_url": url,
                "data": {"status": "ok", "message": {"items": []}}}

    summary = mod.fetch_and_canonicalize_term("data center electricity demand history",
                                               fetcher=not_found_fetcher)
    for r in summary["results"]:
        assert r["overall_status"] == "NOT_FOUND"
        assert r["documents_canonicalized"] == []


# (4) Zero admitted candidates means admission_gate is never called.
def test_zero_admitted_candidates_never_calls_admission_gate():
    calls = []

    def admit_fn_spy(shadow_result):
        calls.append(shadow_result)
        return {"admitted": 999}  # would be an obviously wrong/fabricated result if ever called

    # All 3 query terms return only off-topic / non-historical items -> nothing should be
    # admitted, and admit_fn_spy must never be invoked.
    fetcher = _mock_fetcher({
        "rural%20electrification": [_work("10.1/a", "Tech Company Announces Investment This Year")],
        "data%20center": [_work("10.1/b", "A Survey of Electricity Grid Capacity Planning Methods")],
        "infrastructure%20buildout": [_work("10.1/c", "A Historical Case Study of 19th Century Literature")],
    })

    pilot_result, admission_summary = mod.run_and_maybe_admit(
        fetcher=fetcher, admit_fn=admit_fn_spy,
        gate_log_path=HERE / "_tmp_gate_log_zero_admitted.json",
    )
    assert admission_summary is None
    assert calls == []
    assert all(v["verdict"] == "REAL_HISTORICAL_EVIDENCE_REJECTED" for v in pilot_result["gate_verdicts"])

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
        "rural%20electrification": [_work(
            "10.2/real1",
            "Rural Electrification and Grid Capacity Buildout in the 1930s",
            abstract="A historical case study of grid capacity expansion in the 1930s.",
        )],
        # other two terms return nothing relevant
        "data%20center": [],
        "infrastructure%20buildout": [],
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
    assert any(v["verdict"] == "REAL_HISTORICAL_EVIDENCE_ADMITTED" for v in log_data)
    log_path.unlink(missing_ok=True)


# Gate log is append-only across runs (mirrors transition_admission_gate_log.json).
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
    src = (HIST_EVIDENCE_DIR / "fetch_real_historical_analogy_evidence.py").read_text(encoding="utf-8")
    # This module must never itself hold a documents.json path constant or write to one: the
    # only permitted writer of that file, per the repo's standing rule, is
    # admission_gate.admit_shadow_result() -- which this module only ever calls through admit_fn,
    # never reimplements inline.
    assert "DOCUMENTS_PATH" not in src
    assert not hasattr(mod, "DOCUMENTS_PATH")
    assert 'open(' not in src.replace("spec.loader", "")
