import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import metaxis_point_grounding as m  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import briefing  # noqa: E402


def test_interpretation_type_descriptive_default():
    assert m.classify_interpretation_type("AI 데이터센터의 전력 수요에 대한 논의가 이어지고 있다.") == "DESCRIPTIVE"


def test_interpretation_type_causal():
    assert m.classify_interpretation_type("전력망 위기는 AI 때문에 초래된 것으로 보인다.") in ("CAUSAL", "ATTRIBUTIONAL", "FORECAST")


def test_interpretation_type_forecast():
    assert m.classify_interpretation_type("내년 AI 투자는 더 증가할 것으로 전망이다.") == "FORECAST"


def test_build_provenance_record_never_fabricates_ids():
    rec = m.build_provenance_record("mxp_1", "text", {"status": "SOURCE_SUPPORTED"})
    assert rec["claim_ids"] == [] and rec["evidence_ids"] == [] and rec["intelligence_ids"] == []
    assert rec["grounding_status"] == "SOURCE_SUPPORTED"


def test_production_point_carries_provenance_record():
    it = {"title": "AI 데이터센터 전력 수요 기사", "summary": "전력 수요가 늘고 있다는 내용", "detail": "", "id": "test1"}
    r = {"brief": "어떤 기사 요약 내용입니다 괜찮은 길이로 작성됨.",
         "point": "AI 데이터센터의 전력 수요에 대한 논의가 이어지고 있다.", "tags": ["AI"]}
    out = briefing._mx_ok(it, r)
    assert "prov" in out
    assert out["prov"]["point_id"] == "mxp_test1"
    assert out["prov"]["grounding_status"] in m.GROUNDING_STATUSES


def test_provenance_never_leaks_into_public_html_attrs():
    it = {"title": "AI 데이터센터 전력 수요 기사", "summary": "전력 수요가 늘고 있다는 내용", "detail": "", "id": "test2"}
    r = {"brief": "어떤 기사 요약 내용입니다 괜찮은 길이로 작성됨.",
         "point": "AI 데이터센터의 전력 수요에 대한 논의가 이어지고 있다.", "tags": ["AI"]}
    it["mx"] = briefing._mx_ok(it, r)
    attrs = briefing._mx_attrs(it)
    assert "prov" not in attrs
    assert "claim_ids" not in attrs


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
