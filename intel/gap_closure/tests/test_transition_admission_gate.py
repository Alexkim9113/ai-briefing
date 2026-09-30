# PHASE M.5E-4 -- tests for transition_admission_gate.py and the gated wiring in
# run_admission_transition_energy_gated.py. Manual def test_...(): + bare assert, one file per
# subprocess via importlib.util.spec_from_file_location, matching this repo's standing test
# convention. Zero LLM. No pytest/unittest.
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GAP_CLOSURE_DIR = HERE.parent
EVIDENCE_ADMISSION_DIR = GAP_CLOSURE_DIR.parent / "evidence_admission"
EVIDENCE_NETWORK_DIR = GAP_CLOSURE_DIR.parent / "evidence_network"

sys.path.insert(0, str(GAP_CLOSURE_DIR))
sys.path.insert(0, str(EVIDENCE_ADMISSION_DIR))
sys.path.insert(0, str(EVIDENCE_NETWORK_DIR))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tag = _load("transition_admission_gate", GAP_CLOSURE_DIR / "transition_admission_gate.py")
gated_runner = _load("run_admission_transition_energy_gated",
                      EVIDENCE_ADMISSION_DIR / "run_admission_transition_energy_gated.py")


def _cand(document_id, title, published, source_id="src_federal_register",
          source_name="US Federal Register API", canonical_url=None, abstract=""):
    return {
        "document_id": document_id,
        "title": title,
        "abstract_excerpt": abstract,
        "published": published,
        "source_id": source_id,
        "source_name": source_name,
        "canonical_url": canonical_url or f"https://www.federalregister.gov/d/{document_id}",
        "gap_type_addressed": "TRANSITION_GAP",
    }


# ---------------------------------------------------------------------------------------------
# (a) genuinely clear real TRANSITION-qualifying document: real policy-change language, right
# date, right topic -> TRANSITION_ADMITTED_CANDIDATE.
def test_a_clear_policy_change_is_admitted():
    cand = _cand(
        "fedreg_a1", "Federal Action: New Policy on Data Center Electricity Demand and "
        "Artificial Intelligence Grid Capacity",
        "2026-05-10",
        abstract="This final rule rescinds the prior interconnection process and issues "
                 "guidance on expanding electricity demand for AI data centers.",
    )
    result = tag.classify_candidate(cand)
    assert result["verdict"] == "TRANSITION_ADMITTED_CANDIDATE", result
    assert result["reason_code"] == "STATE_CHANGE_DETECTED"
    assert "POLICY_CHANGE" in result["state_change_categories"] or "REGULATORY_CHANGE" in result["state_change_categories"]


# ---------------------------------------------------------------------------------------------
# (b) merely dated in the window, generic AI news content, no state-change language.
# Honest classifier call: INSUFFICIENT_TRANSITION_EVIDENCE (on-topic + in-window but no
# concrete-change phrase and not clearly speculative either) -- documented here as this
# classifier's chosen outcome for this shape, distinct from (f)'s clearly-speculative case.
def test_b_generic_ai_news_no_state_change_is_insufficient_or_rejected():
    cand = _cand(
        "fedreg_b1", "AI and the Power Grid: A Closer Look at Data Centers and Electricity",
        "2026-04-01",
        abstract="Artificial intelligence continues to be a major topic in energy circles as "
                 "data centers draw attention from the electricity industry.",
    )
    result = tag.classify_candidate(cand)
    assert result["verdict"] in ("INSUFFICIENT_TRANSITION_EVIDENCE", "TRANSITION_REJECTED"), result
    # Documented honest call: this fixture matches no state-change category and no speculative
    # phrase either, so it lands as INSUFFICIENT_TRANSITION_EVIDENCE, not a hard REJECTED.
    assert result["verdict"] == "INSUFFICIENT_TRANSITION_EVIDENCE"
    assert result["reason_code"] == "STATE_CHANGE_AMBIGUOUS"


# ---------------------------------------------------------------------------------------------
# (c) outside the BASELINE-CURRENT window -> TRANSITION_REJECTED (date check fails).
def test_c_out_of_window_date_is_rejected():
    cand = _cand(
        "fedreg_c1", "Federal Action: New Policy on AI Data Center Electricity Demand",
        "2025-09-18",  # before BASELINE_CUTOFF (2026-01-01)
        abstract="This final rule issues guidance expanding grid capacity for AI.",
    )
    result = tag.classify_candidate(cand)
    assert result["verdict"] == "TRANSITION_REJECTED", result
    assert result["reason_code"] == "DATE_OUT_OF_WINDOW"


def test_c2_current_bucket_date_is_also_rejected_as_out_of_window():
    cand = _cand(
        "fedreg_c2", "Federal Action: New Policy on AI Data Center Electricity Demand",
        "2026-09-28",  # on/after CURRENT_CUTOFF -- CURRENT bucket, not TRANSITION
        abstract="This final rule issues guidance expanding grid capacity for AI.",
    )
    result = tag.classify_candidate(cand)
    assert result["verdict"] == "TRANSITION_REJECTED"
    assert result["reason_code"] == "DATE_OUT_OF_WINDOW"


# ---------------------------------------------------------------------------------------------
# (d) right date/topic but from a source family already seen (admitted) in the corpus ->
# rejected via the existing_source_families dedup check.
def test_d_already_admitted_source_family_is_rejected():
    cand = _cand(
        "fedreg_d1", "Utility Signs Power Purchase Agreement for AI Data Center Electricity Load",
        "2026-06-01",
        source_id="src_federal_register",
        abstract="The agency signs agreement expanding grid interconnection for AI data centers.",
    )
    existing_families = {("source_id", "src_federal_register")}
    result = tag.classify_candidate(cand, existing_source_families=existing_families)
    assert result["verdict"] == "TRANSITION_REJECTED", result
    assert result["reason_code"] == "DUPLICATE_OR_SAME_SOURCE_FAMILY"


# ---------------------------------------------------------------------------------------------
# (e) clearly duplicate / near-identical title within the same batch -> TRANSITION_REJECTED.
def test_e_near_duplicate_title_in_batch_is_rejected():
    first = _cand(
        "fedreg_e1", "Federal Action to Expand Grid Capacity for AI Data Centers",
        "2026-03-01",
        abstract="This final rule expands generation capacity for AI energy demand.",
    )
    dup = _cand(
        "fedreg_e2", "Federal Action To Expand Grid Capacity for AI Data Centers",  # case/punct variant
        "2026-03-02",
        abstract="This final rule expands generation capacity for AI energy demand.",
    )
    results = tag.classify_batch([first, dup])
    assert results[0]["verdict"] == "TRANSITION_ADMITTED_CANDIDATE", results[0]
    assert results[1]["verdict"] == "TRANSITION_REJECTED", results[1]
    assert results[1]["reason_code"] == "DUPLICATE_OR_SAME_SOURCE_FAMILY"


# ---------------------------------------------------------------------------------------------
# (f) opinion/forecast-only document: speculative language, no concrete stated change -> must
# NOT be admitted.
def test_f_opinion_forecast_only_is_rejected_not_admitted():
    cand = _cand(
        "fedreg_f1", "AI Data Centers Could Reshape Electricity Demand, Analysts Predict",
        "2026-07-15",
        abstract="Experts warn that AI data center electricity demand is expected to surge, "
                 "and some believe the grid may need major upgrades in coming years.",
    )
    result = tag.classify_candidate(cand)
    assert result["verdict"] != "TRANSITION_ADMITTED_CANDIDATE", result
    assert result["verdict"] == "TRANSITION_REJECTED"
    assert result["reason_code"] == "OPINION_FORECAST_ONLY"


# ---------------------------------------------------------------------------------------------
# (g) boundary case: missing/unknown source -> hard REJECTED regardless of otherwise-good text.
def test_g_missing_source_is_rejected():
    cand = _cand(
        "fedreg_g1", "Federal Action to Expand Grid Capacity for AI Data Centers",
        "2026-03-01", source_id="", source_name="",
        abstract="This final rule expands generation capacity for AI energy demand.",
    )
    result = tag.classify_candidate(cand)
    assert result["verdict"] == "TRANSITION_REJECTED", result
    assert result["reason_code"] == "SOURCE_MISSING"


# ---------------------------------------------------------------------------------------------
# (h) boundary case: on-topic keyword present but no AI hint at all (e.g. a generic energy
# notice unrelated to AI) -> TRANSITION_REJECTED for topic irrelevance, even with a concrete
# regulatory-change phrase present, since topic relevance is checked before state-change.
def test_h_topic_irrelevant_without_ai_hint_is_rejected():
    cand = _cand(
        "fedreg_h1", "Final Rule on Effluent Limitations for Steam Electric Power Generating Plants",
        "2026-02-01",
        abstract="This final rule finalizes new electricity generation effluent standards.",
    )
    result = tag.classify_candidate(cand)
    assert result["verdict"] == "TRANSITION_REJECTED", result
    assert result["reason_code"] == "TOPIC_NOT_RELEVANT"


def test_i_no_date_at_all_is_rejected():
    cand = _cand(
        "fedreg_i1", "Federal Action to Expand Grid Capacity for AI Data Centers",
        None,
        abstract="This final rule expands generation capacity for AI energy demand.",
    )
    result = tag.classify_candidate(cand)
    assert result["verdict"] == "TRANSITION_REJECTED"
    assert result["reason_code"] == "DATE_OUT_OF_WINDOW"


def test_verdicts_never_include_unknown_string():
    for r in (
        test_and_return_a(), test_and_return_b(), test_and_return_c(), test_and_return_d(),
    ):
        assert r["verdict"] in tag.VERDICTS


def test_and_return_a():
    cand = _cand("z1", "Federal Action: New Policy on Data Center Electricity Demand and "
                        "Artificial Intelligence Grid Capacity", "2026-05-10",
                 abstract="This final rule rescinds the prior process.")
    return tag.classify_candidate(cand)


def test_and_return_b():
    cand = _cand("z2", "AI and the Power Grid: A Closer Look", "2026-04-01",
                 abstract="Artificial intelligence continues to be a topic in energy circles.")
    return tag.classify_candidate(cand)


def test_and_return_c():
    cand = _cand("z3", "Federal Action on AI Data Center Electricity Demand", "2025-09-18",
                 abstract="This final rule issues guidance.")
    return tag.classify_candidate(cand)


def test_and_return_d():
    cand = _cand("z4", "Final Rule on Effluent Limitations for Steam Electric Power Plants",
                 "2026-02-01", abstract="This final rule finalizes new standards.")
    return tag.classify_candidate(cand)


# ---------------------------------------------------------------------------------------------
# classify_batch never silently defaults an ambiguous case to ADMITTED: every non-ADMITTED
# verdict has a non-empty reason.
def test_no_silent_default_to_admitted():
    candidates = [
        _cand("n1", "AI and the Power Grid: A Closer Look", "2026-04-01",
              abstract="Artificial intelligence continues to be a topic in energy circles."),
        _cand("n2", "Final Rule on Effluent Limitations for Steam Electric Power Plants",
              "2026-02-01", abstract="This final rule finalizes new standards."),
    ]
    for r in tag.classify_batch(candidates):
        if r["verdict"] != "TRANSITION_ADMITTED_CANDIDATE":
            assert r["reason"], r
            assert r["reason_code"], r


# ---------------------------------------------------------------------------------------------
# existing_source_families_from_documents(): pure derivation from real document rows.
def test_existing_source_families_from_documents():
    documents = {
        "doc1": {"source_id": "src_federal_register", "canonical_url": "https://www.federalregister.gov/d/1"},
        "doc2": {"source_id": None, "canonical_url": "https://news.example.com/story"},
        "doc3": {},
    }
    families = tag.existing_source_families_from_documents(documents)
    assert ("source_id", "src_federal_register") in families
    assert ("domain", "news.example.com") in families
    assert len(families) == 2


# ---------------------------------------------------------------------------------------------
# Wiring test: TRANSITION_REJECTED / INSUFFICIENT candidates never reach admission_gate. Uses a
# STUB admit_fn so real admission_gate.admit_shadow_result() (and documents.json) is never
# touched.
def test_gated_wiring_withholds_rejected_and_insufficient_from_admission_gate():
    calls = []

    def stub_admit_shadow_result(shadow_result):
        calls.append(shadow_result)
        seen_docs = [d for r in shadow_result["results"] for d in r["documents_canonicalized"]]
        return {
            "candidates_seen": len(seen_docs), "admitted": len(seen_docs),
            "duplicate_existing": 0, "rejected": 0, "review_required": 0,
        }

    shadow_result = {
        "results": [
            {
                "gap_type": "TRANSITION_GAP",
                "fetch_status": "FETCH_OK",
                "schema_status": "VALIDATION_OK",
                "documents_canonicalized": [
                    _cand("g_admit", "Federal Action: New Policy on AI Data Center Electricity "
                                     "Demand and Grid Capacity", "2026-05-10",
                          abstract="This final rule rescinds the prior process and issues "
                                   "guidance expanding electricity demand for AI."),
                    _cand("g_reject_date", "Federal Action on AI Data Center Electricity Demand",
                          "2025-09-18", abstract="This final rule issues guidance."),
                    _cand("g_insufficient", "AI and the Power Grid: A Closer Look",
                          "2026-04-01",
                          abstract="Artificial intelligence continues to be a topic in energy circles."),
                ],
            }
        ]
    }

    admission_summary, gate_log_entries, filtered = gated_runner.run_gated_admission(
        shadow_result, documents={}, admit_fn=stub_admit_shadow_result,
    )

    # Exactly one call to the (stub) admission_gate, containing ONLY the admitted candidate.
    assert len(calls) == 1
    passed_ids = [d["document_id"] for r in calls[0]["results"] for d in r["documents_canonicalized"]]
    assert passed_ids == ["g_admit"]
    assert "g_reject_date" not in passed_ids
    assert "g_insufficient" not in passed_ids

    assert admission_summary is not None
    assert admission_summary["candidates_seen"] == 1

    # The gate log records every candidate, including the withheld ones, with a reason.
    verdicts_by_id = {row["document_id"]: row for row in gate_log_entries}
    assert verdicts_by_id["g_admit"]["verdict"] == "TRANSITION_ADMITTED_CANDIDATE"
    assert verdicts_by_id["g_reject_date"]["verdict"] == "TRANSITION_REJECTED"
    assert verdicts_by_id["g_reject_date"]["reason"]
    assert verdicts_by_id["g_insufficient"]["verdict"] == "INSUFFICIENT_TRANSITION_EVIDENCE"
    assert verdicts_by_id["g_insufficient"]["reason"]


def test_gated_wiring_calls_nothing_when_zero_candidates_admitted():
    calls = []

    def stub_admit_shadow_result(shadow_result):
        calls.append(shadow_result)
        return {"candidates_seen": 0, "admitted": 0, "duplicate_existing": 0,
                "rejected": 0, "review_required": 0}

    shadow_result = {
        "results": [
            {
                "gap_type": "TRANSITION_GAP",
                "documents_canonicalized": [
                    _cand("only_rejected", "Federal Action on AI Data Center Electricity Demand",
                          "2025-09-18", abstract="This final rule issues guidance."),
                ],
            }
        ]
    }
    admission_summary, gate_log_entries, filtered = gated_runner.run_gated_admission(
        shadow_result, documents={}, admit_fn=stub_admit_shadow_result,
    )
    assert len(calls) == 0
    assert admission_summary is None
    assert len(gate_log_entries) == 1
    assert gate_log_entries[0]["verdict"] == "TRANSITION_REJECTED"


def run_all():
    tests = [
        test_a_clear_policy_change_is_admitted,
        test_b_generic_ai_news_no_state_change_is_insufficient_or_rejected,
        test_c_out_of_window_date_is_rejected,
        test_c2_current_bucket_date_is_also_rejected_as_out_of_window,
        test_d_already_admitted_source_family_is_rejected,
        test_e_near_duplicate_title_in_batch_is_rejected,
        test_f_opinion_forecast_only_is_rejected_not_admitted,
        test_g_missing_source_is_rejected,
        test_h_topic_irrelevant_without_ai_hint_is_rejected,
        test_i_no_date_at_all_is_rejected,
        test_verdicts_never_include_unknown_string,
        test_no_silent_default_to_admitted,
        test_existing_source_families_from_documents,
        test_gated_wiring_withholds_rejected_and_insufficient_from_admission_gate,
        test_gated_wiring_calls_nothing_when_zero_candidates_admitted,
    ]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"ALL {len(tests)} TESTS PASSED")


if __name__ == "__main__":
    run_all()
