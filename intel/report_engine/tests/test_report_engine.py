import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import report_engine as re_  # noqa: E402
import schema as sc  # noqa: E402
import html_renderer as hr  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]


def _real_objects():
    return json.loads((ROOT / "intel" / "intelligence_objects" / "intelligence_objects.json").read_text(encoding="utf-8"))


# 1. no fabricated evidence
def test_report_never_invents_claim_not_on_intelligence_object():
    objects = _real_objects()
    obj = objects["intel_87210a61730c22b9"]
    r = re_.build_report("intel_87210a61730c22b9")
    claim_ids_in_report = r["sections"]["KEY_CLAIMS"]["claim_ids"]
    assert set(claim_ids_in_report) <= set(obj.get("key_claims") or [])


# 2. claim status never strengthened
def test_claim_sentence_never_exceeds_status():
    claim = {"status": "INSUFFICIENT_EVIDENCE", "claim_type": "DESCRIPTIVE", "scope": "X"}
    sentence = re_.render_claim_sentence(claim)
    assert sentence == sc.CLAIM_STATUS_TEMPLATES["INSUFFICIENT_EVIDENCE"].format(scope="X")
    assert "확인된다" not in sentence and "뒷받침한다" not in sentence


# 3. causal claim never generated without strong support
def test_causal_claim_without_support_forced_to_insufficient_template():
    claim = {"status": "OPEN", "claim_type": "CAUSAL", "scope": "AI 수요 증가가 전력망 위기를 만들었다"}
    sentence = re_.render_claim_sentence(claim)
    assert sentence == sc.CLAIM_STATUS_TEMPLATES["INSUFFICIENT_EVIDENCE"]


def test_causal_claim_with_support_still_uses_supported_template():
    claim = {"status": "SUPPORTED", "claim_type": "CAUSAL", "scope": "X"}
    sentence = re_.render_claim_sentence(claim)
    assert sentence == sc.CLAIM_STATUS_TEMPLATES["SUPPORTED"].format(scope="X")


# 4. SEARCH_RUN_NO_EVIDENCE never rendered as "no counterevidence exists"
def test_search_run_no_evidence_not_rendered_as_absence():
    obj = {"counterevidence": []}
    section = re_.build_counterevidence_section(obj, {"search_outcome": "SEARCH_RUN_NO_EVIDENCE"})
    assert section["search_outcome"] == "SEARCH_RUN_NO_EVIDENCE"
    assert "없다" not in section["search_outcome_note"] or "확인하지 못했다" in section["search_outcome_note"]
    assert "반대 증거가 없다" != section["search_outcome_note"]


# 5. private full text never in Public Report
def test_public_view_never_contains_vault_full_text_key():
    r = re_.build_report("intel_87210a61730c22b9")
    pub = re_.build_public_view(r)
    serialized = json.dumps(pub, ensure_ascii=False)
    assert "full_text" not in serialized
    assert "vault_record" not in serialized


# 6. rights-restricted content never duplicated verbatim (no full-text field exists at all)
def test_source_card_never_carries_full_text_field():
    doc = {"document_id": "d1", "title": "t", "rights_mode": "LINK_ONLY", "category": "papers"}
    card = re_.build_source_card(doc)
    assert "full_text" not in card
    assert "body_text" not in card


# 7. DOI/arXiv-less news never enters Research Evidence
def test_news_without_research_identity_excluded_from_research_section():
    obj = {"research_context": ["d1"]}
    documents = {"d1": {"title": "News about a paper", "category": "papers", "source_id": "src_investing_com"}}
    section = re_.build_research_section(obj, documents)
    assert section["content_blocks"] == []
    assert section["status"] == "INSUFFICIENT_EVIDENCE"


def test_confirmed_research_identity_included():
    obj = {"research_context": ["d1"]}
    documents = {"d1": {"title": "Real paper", "category": "papers", "doi": "10.1/x"}}
    section = re_.build_research_section(obj, documents)
    assert len(section["content_blocks"]) == 1
    assert section["content_blocks"][0]["identity_type"] == "DOI"


# 8. UNKNOWN values never guessed
def test_source_card_unknown_fields_stay_unknown():
    doc = {"document_id": "d1", "title": "t"}
    card = re_.build_source_card(doc)
    assert card["date"] == "UNKNOWN"
    assert card["url"] == "UNKNOWN"


# 9. source link connects to provenance
def test_source_provenance_section_uses_real_provenance_ids():
    r = re_.build_report("intel_87210a61730c22b9")
    obj = _real_objects()["intel_87210a61730c22b9"]
    assert r["sections"]["SOURCE_PROVENANCE"]["source_ids"] == obj.get("provenance", [])


# 10. report version stable identity
def test_report_version_increments_without_breaking_intelligence_id():
    r1 = re_.build_report("intel_87210a61730c22b9")
    assert r1["intelligence_id"] == "intel_87210a61730c22b9"
    assert r1["report_id"].startswith(f"report_{r1['intelligence_id']}_v")


# 11. same input -> same canonical content (idempotent snapshot hashes)
def test_same_input_produces_same_snapshot_hashes():
    r1 = re_.build_report("intel_87210a61730c22b9")
    r2 = re_.build_report("intel_87210a61730c22b9")
    assert r1["claim_snapshot"] == r2["claim_snapshot"]
    assert r1["evidence_snapshot"] == r2["evidence_snapshot"]
    assert r1["source_snapshot"] == r2["source_snapshot"]


# 12. Report JSON and HTML agree on core facts
def test_html_rendering_contains_same_readiness_and_topic():
    r = re_.build_report("intel_87210a61730c22b9")
    pub = re_.build_public_view(r)
    doc = hr.render_report_html(pub)
    assert r["topic"] in doc
    assert r["readiness"] in doc


def test_unsupported_metaxis_point_excluded_from_public_view():
    r = re_.build_report("intel_87210a61730c22b9", mx_point_text="AI 수요 증가가 전력망 위기를 만들고 있다는 분석이다.",
                         mx_provenance={"grounding_status": "UNSUPPORTED_INTERPRETATION", "interpretation_type": "ATTRIBUTIONAL"})
    assert r["sections"]["METAXIS_POINT"]["status"] == "INSUFFICIENT_EVIDENCE"
    pub = re_.build_public_view(r)
    assert pub["sections"]["METAXIS_POINT"]["content_blocks"] == []


def test_grounded_metaxis_point_included_in_public_view():
    r = re_.build_report("intel_87210a61730c22b9", mx_point_text="AI 데이터센터의 전력 수요에 대한 논의가 이어지고 있다.",
                         mx_provenance={"grounding_status": "SOURCE_SUPPORTED", "interpretation_type": "DESCRIPTIVE"})
    pub = re_.build_public_view(r)
    assert len(pub["sections"]["METAXIS_POINT"]["content_blocks"]) == 1


def test_diff_reports_detects_new_evidence_on_first_version():
    r = re_.build_report("intel_87210a61730c22b9")
    diffs = re_.diff_reports(None, r)
    assert "NEW_EVIDENCE" in diffs


def test_diff_reports_no_change_between_identical_rebuilds():
    r1 = re_.build_report("intel_87210a61730c22b9")
    r2 = re_.build_report("intel_87210a61730c22b9")
    diffs = re_.diff_reports(r1, r2)
    assert "NEW_EVIDENCE" not in diffs


def test_readiness_never_a_bare_number():
    r = re_.build_report("intel_87210a61730c22b9")
    assert r["readiness"] in sc.REPORT_READINESS_VALUES
    assert not isinstance(r["readiness"], (int, float))


def test_non_causal_point_grounded_via_real_intelligence_object_evidence():
    objects = _real_objects()
    obj = objects["intel_87210a61730c22b9"]
    g = re_.compute_point_grounding_for_report(obj, "AI 데이터센터의 전력 수요에 대한 논의가 이어지고 있다.")
    assert g["status"] in ("EVIDENCE_NETWORK_SUPPORTED", "SOURCE_SUPPORTED", "INTELLIGENCE_OBJECT_SUPPORTED")


def test_non_causal_point_grounding_never_fabricates_refs_for_empty_object():
    g = re_.compute_point_grounding_for_report({"intelligence_id": "x"}, "일반적인 설명 문장이다.")
    assert g["status"] == "UNSUPPORTED_INTERPRETATION"


def test_find_affected_reports_reuses_existing_incremental_update():
    objects = _real_objects()
    affected = re_.find_affected_reports("AI_ENERGY_INFRA", objects)
    assert "intel_87210a61730c22b9" in affected
    assert "intel_dbab7b01963396b5" not in affected


def test_real_sample_report_ai_energy_infra_exists_on_disk():
    path = re_.REPORTS_DIR / "report_intel_87210a61730c22b9_v1.json"
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["topic"] == "AI_ENERGY_INFRA"


def test_real_sample_report_ai_labor_exists_on_disk():
    path = re_.REPORTS_DIR / "report_intel_dbab7b01963396b5_v1.json"
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["topic"] == "AI_LABOR"


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
        except Exception as e:
            failed += 1
            print(f"ERROR {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
