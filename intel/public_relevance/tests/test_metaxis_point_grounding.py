import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import metaxis_point_grounding as m  # noqa: E402


def test_unsupported_causal_claim_blocked():
    g = m.check_point_grounding("기후변화로 인해 이런 장기 강수가 발생하고 있다.")
    assert g["status"] == "UNSUPPORTED_INTERPRETATION"


def test_unsupported_ai_demand_grid_claim_blocked():
    g = m.check_point_grounding("AI 수요 증가가 전력망 위기를 만들고 있다.")
    assert g["status"] == "UNSUPPORTED_INTERPRETATION"


def test_source_supported_claim_allowed():
    g = m.check_point_grounding("원문에 명시된 내용", source_document_evidence=True)
    assert g["status"] == "SOURCE_SUPPORTED"


def test_evidence_network_supported_claim_allowed():
    g = m.check_point_grounding("AI 데이터센터 전력 수요가 증가하고 있다.",
                                 evidence_network_refs=["rel_abc123"])
    assert g["status"] == "EVIDENCE_NETWORK_SUPPORTED"


def test_filter_drops_only_unsupported():
    pairs = [
        ("s1", {"status": "SOURCE_SUPPORTED"}),
        ("s2", {"status": "UNSUPPORTED_INTERPRETATION"}),
        ("s3", {"status": "INTELLIGENCE_OBJECT_SUPPORTED"}),
    ]
    kept = m.filter_publishable_points(pairs)
    assert kept == ["s1", "s3"]


def test_non_causal_sentence_without_any_grounding_still_unsupported():
    g = m.check_point_grounding("오늘 발표된 내용이에요.")
    assert g["status"] == "UNSUPPORTED_INTERPRETATION"


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
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
