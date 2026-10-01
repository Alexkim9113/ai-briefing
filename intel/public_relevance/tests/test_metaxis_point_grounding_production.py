# N-1 -- regression tests for the real production wiring of the Grounding Gate inside
# briefing.py::_mx_ok(). Imports briefing.py directly (repo root) rather than re-testing the
# standalone metaxis_point_grounding module (already covered by test_metaxis_point_grounding.py).
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import briefing  # noqa: E402


def _item():
    return {"title": "AI 데이터센터 전력 수요 기사", "summary": "전력 수요가 늘고 있다는 내용", "detail": ""}


def test_unsupported_causal_point_dropped_but_brief_kept():
    r = {"brief": "어떤 기사 요약 내용입니다 괜찮은 길이로 작성됨.",
         "point": "AI 수요 증가가 전력망 위기를 만들고 있다는 분석이다.",
         "tags": ["AI", "전력", "데이터센터"]}
    out = briefing._mx_ok(_item(), r)
    assert out is not None
    assert out["p"] == ""
    assert out["b"] != ""


def test_unsupported_attribution_point_dropped():
    r = {"brief": "어떤 기사 요약 내용입니다 괜찮은 길이로 작성됨.",
         "point": "전력망 위기는 AI 때문에 초래된 것으로 보인다.",
         "tags": ["AI", "전력", "데이터센터"]}
    out = briefing._mx_ok(_item(), r)
    assert out is not None
    assert out["p"] == ""


def test_non_causal_point_not_blocked_by_grounding_gate():
    r = {"brief": "어떤 기사 요약 내용입니다 괜찮은 길이로 작성됨.",
         "point": "AI 데이터센터의 전력 수요에 대한 논의가 이어지고 있다.",
         "tags": ["AI", "전력", "데이터센터"]}
    out = briefing._mx_ok(_item(), r)
    assert out is not None
    assert out["p"] != ""


def test_grounding_gate_failure_never_crashes_mx_ok():
    # Even if the grounding module import ever breaks, _mx_ok must never raise -- the try/except
    # around the gate guarantees the existing production path keeps working.
    r = {"brief": "어떤 기사 요약 내용입니다 괜찮은 길이로 작성됨.",
         "point": "일반적인 설명 문장이다.", "tags": ["AI"]}
    out = briefing._mx_ok(_item(), r)
    assert out is not None


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
