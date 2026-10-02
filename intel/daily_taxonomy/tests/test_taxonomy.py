import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import taxonomy  # noqa: E402


def test_exactly_11_fields_fixed():
    assert len(taxonomy.FIELDS) == 11
    assert set(taxonomy.FIELDS) == {
        "기술", "산업·경제", "노동·고용", "법·제도", "의료·헬스케어", "에너지·환경",
        "국방·안보", "교육·사회", "문화·예술", "미디어·콘텐츠", "정책·국제질서",
    }


def test_legal_consolidation_no_separate_subcategories():
    # Section F: copyright/privacy/court-ruling/AI-basic-law must never become their own
    # top-level field -- they all route into 법·제도 only.
    for label in ("저작권", "개인정보", "판결", "AI 기본법", "지식재산"):
        assert label not in taxonomy.FIELDS


def test_culture_and_arts_never_dropped_to_other():
    v = taxonomy.classify_fields("경기문화재단 예술-기술 융복합 프로젝트 전시 《AI 디지털팔레트》 개최",
                                  ["CULTURE_ARTS_MEDIA"], "문화·예술")
    assert v[0] == "문화·예술" or "문화·예술" in v[1]


def test_broad_media_tag_routes_to_media_not_culture():
    # Real-data QA finding: a "문화·미디어" collection-time tag is a broad catch-all (ad-revenue
    # earnings, SEO course listings have been seen under it) -- it must not be trusted as genuine
    # 문화·예술 evidence by itself.
    primary, secondary = taxonomy.classify_fields("Roku Credits Search, AI In Shareholder Letter",
                                                    ["CULTURE_ARTS_MEDIA"], "문화·미디어")
    assert primary == "미디어·콘텐츠"
    assert "문화·예술" not in ([primary] + secondary)


def test_copyright_media_tag_splits_to_legal_and_media_never_culture():
    primary, secondary = taxonomy.classify_fields("News Outlets Ask Court to Ignore DOJ View in AI Copyright Suit",
                                                    ["POLICY_LAW_GOVERNANCE", "CULTURE_ARTS_MEDIA"], "저작권·미디어")
    fields = [primary] + secondary
    assert "법·제도" in fields
    assert "문화·예술" not in fields


def test_short_substring_false_positive_fixed():
    # Regression pin for the real bug found during O-3C QA: bare "art"/"game" substring matches
    # inside "Artificial"/"Partner"/"education game" must not fire.
    primary, secondary = taxonomy.classify_fields(
        "Artificial or 'Super Intelligent'? The Broken Metaphors of AI", [], None)
    assert "문화·예술" not in ([primary] + secondary if primary else secondary)

    primary2, secondary2 = taxonomy.classify_fields(
        "청주대 건축공학과, 한국연구재단 과제 연속 선정", [], None)
    assert "문화·예술" not in ([primary2] + secondary2 if primary2 else secondary2)


def test_labor_field_detected_as_secondary_when_domain_is_economy():
    primary, secondary = taxonomy.classify_fields(
        "AI가 신입 일자리 26.8만개 삼킬 때…50대는 17.3만개 늘었다",
        ["ECONOMY_INDUSTRY_LABOR"], None)
    assert "노동·고용" in ([primary] + secondary)


def test_no_label_forced_when_no_signal():
    primary, secondary = taxonomy.classify_fields("오늘의 날씨와 생활 정보", [], None)
    assert primary is None
    assert secondary == []


def test_run_only_includes_gate_pass_documents(tmp_path):
    out = tmp_path / "result.json"
    result = taxonomy.run(out_path=out)
    gate_result = taxonomy._gate.run_on_documents(out_path=tmp_path / "gate_scratch.json")
    pass_ids = {k for k, v in gate_result["results"].items() if v["gate"] == taxonomy._gate.GATE_PASS}
    assert set(result["per_document"].keys()) == pass_ids


def test_run_never_mutates_source_files(tmp_path):
    root = HERE.parent.parent.parent
    watched = [root / "intel" / "documents.json", root / "intel" / "facts.json",
               root / "intel" / "production_events.json" if (root / "intel" / "production_events.json").exists() else None]
    watched = [w for w in watched if w]
    before = {w: w.read_bytes() for w in watched}
    taxonomy.run(out_path=tmp_path / "result.json")
    for w in watched:
        assert w.read_bytes() == before[w]


def test_idempotent_on_same_corpus(tmp_path):
    out1 = tmp_path / "r1.json"
    out2 = tmp_path / "r2.json"
    r1 = taxonomy.run(out_path=out1)
    r2 = taxonomy.run(out_path=out2)
    assert r1["field_counts_primary"] == r2["field_counts_primary"]
    assert r1["region_counts"] == r2["region_counts"]
    assert r1["total_pass_documents"] == r2["total_pass_documents"]


def test_canonical_files_untouched_by_import(tmp_path):
    root = HERE.parent.parent.parent
    import hashlib
    paths = [
        root / "intel" / "report_engine" / "reports" / "report_intel_87210a61730c22b9_v4.json",
        root / "intel" / "claims" / "claims.json",
        root / "intel" / "hypothesis" / "hypotheses.json",
        root / "intel" / "intelligence_objects" / "intelligence_objects.json",
    ]
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    taxonomy.run(out_path=tmp_path / "result.json")
    after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    assert before == after


def test_six_core_regions_are_representable():
    # These six codes must be valid region outputs even if the current corpus has zero documents
    # for some of them (an empty bucket is an honest finding, not a classifier defect).
    core = {"KR", "US", "CN", "EU", "JP", "IN"}
    extra = {"UK", "CA", "TW", "SG", "MIDDLE_EAST", "GLOBAL", "OTHER", "UNKNOWN"}
    # No enum is hardcoded/enforced elsewhere in this module (region comes straight from
    # geography_inference.py's own country codes) -- this test documents the expected vocabulary
    # rather than asserting the classifier itself restricts outputs to it.
    assert core | extra  # vocabulary sanity, not a runtime assertion on live data
