# STAGE 7 PHASE I — synthetic tests (섹션 62): epistemic guard, claim ceiling enforcement,
# novelty gate, anti-convergence.
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

from epistemic_guard import (assess_novelty, check_claim_ceiling,  # noqa: E402
                              detect_generic_convergence)


def test_claim_ceiling_capped_when_claude_overclaims():
    result_ceiling, was_capped = check_claim_ceiling("HYPOTHESIS_FUTURES", "OBSERVED_FACT")
    assert result_ceiling == "OBSERVED_FACT"
    assert was_capped is True


def test_claim_ceiling_not_capped_when_within_bounds():
    result_ceiling, was_capped = check_claim_ceiling("OBSERVED_FACT", "OBSERVED_CHANGE")
    assert result_ceiling == "OBSERVED_FACT"
    assert was_capped is False


def test_detect_generic_convergence_catches_known_cliches():
    hits = detect_generic_convergence("결국 인간의 판단이 중요해지고 있다")
    assert hits


def test_detect_generic_convergence_empty_for_specific_claim():
    hits = detect_generic_convergence("Nvidia의 GPU 수출 규제가 대만 파운드리 계약 조건을 바꾸고 있다")
    assert hits == []


def test_novelty_gate_downgrades_when_identical_to_existing_memory():
    existing = ["AI Agent 사용이 증가했다"]
    kind = assess_novelty("NEW_FACT", existing, "AI Agent 사용이 증가했다")
    assert kind == "SUPPORTING_EVIDENCE_FOR_EXISTING_VIEW"


def test_novelty_gate_keeps_kind_when_actually_new():
    existing = ["AI Agent 사용이 증가했다"]
    kind = assess_novelty("NEW_CONNECTION", existing, "AI Agent 확산이 결제 인프라 규제와 연결된다")
    assert kind == "NEW_CONNECTION"


def test_novelty_gate_never_fabricates_unknown_kind():
    try:
        assess_novelty("NOT_A_REAL_KIND", [], "some statement")
        assert False, "should have raised"
    except AssertionError:
        pass
