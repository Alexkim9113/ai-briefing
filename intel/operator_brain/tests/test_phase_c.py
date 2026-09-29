# STAGE 7 PHASE C — synthetic tests (섹션 62): evidence sufficiency, claim ceiling.
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import evidence_sufficiency  # noqa: E402
import pipeline  # noqa: E402
from schema import CLAIM_LADDER, EVIDENCE_SUFFICIENCY_STATES  # noqa: E402


def test_no_results_is_insufficient_not_fabricated_sufficient():
    r = evidence_sufficiency.assess([], "FACT_LOOKUP")
    assert r["state"] == "INSUFFICIENT_EVIDENCE"
    assert r["claim_ceiling"] is None


def test_fact_lookup_with_results_ceiling_is_observed_fact_only():
    r = evidence_sufficiency.assess([{"note_id": "n1"}], "FACT_LOOKUP")
    assert r["state"] == "SUFFICIENT_FOR_FACT_LOOKUP"
    assert r["claim_ceiling"] == "OBSERVED_FACT"


def test_hypothesis_test_without_counter_evidence_never_reaches_full_sufficient():
    # 섹션 3: COUNTER-EVIDENCE BEFORE CONCLUSION - counter evidence가 없으면 절대
    # SUFFICIENT_FOR_HYPOTHESIS_TEST로 격상하지 않는다.
    r = evidence_sufficiency.assess([{"note_id": "n1"}], "HYPOTHESIS_TEST", counter_evidence_results=[])
    assert r["state"] != "SUFFICIENT_FOR_HYPOTHESIS_TEST"
    assert r["state"] == "SUFFICIENT_FOR_LIMITED_INTERPRETATION"


def test_hypothesis_test_with_counter_evidence_can_be_sufficient():
    r = evidence_sufficiency.assess([{"note_id": "n1"}], "HYPOTHESIS_TEST",
                                     counter_evidence_results=[{"note_id": "c1"}])
    assert r["state"] == "SUFFICIENT_FOR_HYPOTHESIS_TEST"


def test_all_states_and_ceilings_are_from_spec_vocabulary():
    for state in [evidence_sufficiency.assess([], "FACT_LOOKUP")["state"],
                  evidence_sufficiency.assess([{"note_id": "n1"}], "FACT_LOOKUP")["state"]]:
        assert state in EVIDENCE_SUFFICIENCY_STATES
    ceiling = evidence_sufficiency.assess([{"note_id": "n1"}], "FACT_LOOKUP")["claim_ceiling"]
    assert ceiling in CLAIM_LADDER


def test_pipeline_ask_includes_evidence_sufficiency_on_real_data():
    record = pipeline.ask("Nvidia 규제 관련 최근 사건은?", "RETRIEVE")
    assert "evidence_sufficiency" in record
    assert record["evidence_sufficiency"]["state"] in EVIDENCE_SUFFICIENCY_STATES
