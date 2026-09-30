import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
LOG_PATH = PKG_DIR / "gap_closure_log.json"

REQUIRED_FIELDS = (
    "GAP_ID", "GAP_TYPE", "TOPIC", "WHY_IT_MATTERS", "TARGET_SOURCE_TYPE",
    "ACQUISITION_ATTEMPT", "RESULT", "EVIDENCE_FOUND", "REJECTION_REASON", "REMAINING_GAP",
)


def _load():
    return json.loads(LOG_PATH.read_text(encoding="utf-8"))


def test_log_file_exists_and_is_a_list():
    records = _load()
    assert isinstance(records, list)
    assert len(records) >= 2


def test_every_record_has_exact_required_schema():
    records = _load()
    for r in records:
        assert set(r.keys()) == set(REQUIRED_FIELDS), r.get("GAP_ID")


def test_evidence_found_is_boolean_and_matches_result_honesty():
    # EVIDENCE_FOUND must be a real boolean. Most attempts in this log found nothing (network
    # was never live, or the corpus search came back empty) and must report False -- a True
    # without real evidence would be fabrication. The one exception is the geographic
    # reclassification record, which performed a real, verifiable re-classification of existing
    # corpus documents (no live acquisition needed) and legitimately found real evidence.
    records = _load()
    for r in records:
        assert isinstance(r["EVIDENCE_FOUND"], bool)
        if r["GAP_ID"] == "GAP_AI_ENERGY_INFRA_GEOGRAPHIC_KOREA_001":
            assert r["EVIDENCE_FOUND"] is True
        else:
            assert r["EVIDENCE_FOUND"] is False


def test_no_record_claims_gap_closed():
    records = _load()
    for r in records:
        remaining = r["REMAINING_GAP"].lower()
        assert "gap closed" not in remaining
        assert "closed the gap" not in remaining
        result = r["RESULT"].upper()
        assert "CLOSED" not in result


def test_expected_gap_types_and_topic_present():
    records = _load()
    gap_types = {r["GAP_TYPE"] for r in records}
    assert "TRANSITION_GAP" in gap_types
    assert "STATISTICAL_GAP" in gap_types
    for r in records:
        assert r["TOPIC"] == "AI_ENERGY_INFRA"


def test_gap_ids_are_unique():
    records = _load()
    ids = [r["GAP_ID"] for r in records]
    assert len(ids) == len(set(ids))


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
