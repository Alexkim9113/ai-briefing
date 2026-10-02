# O-3 -- tests for the reader-facing Public Intelligence Index summary (no more raw
# CURRENT_STATE dump) and the expanded AI_ATTRIBUTION editorial translation layer, PUBLIC view
# only. Operator view must stay byte-identical in behavior (still raw enums/text).
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import public_delivery as pd  # noqa: E402
import product_html as ph  # noqa: E402
import report_engine as re_  # noqa: E402

REPORTS_DIR = re_.REPORTS_DIR

BANNED_INDEX_SUBSTRINGS = (
    "AI_ATTRIBUTION=", "INSUFFICIENT_EVIDENCE", "guard_trail",
    "canonical_status_diagnostics", "claim_", "hyp_", "evt_", "intel_",
    "[O-1B", "[O-2 round",
)


def _real_reports():
    return sorted(REPORTS_DIR.glob("report_intel_*_v*.json"))


def test_index_card_never_contains_raw_enum_or_id_tokens():
    found_any = False
    for p in _real_reports():
        r = json.loads(p.read_text(encoding="utf-8"))
        entry = pd.build_intelligence_index_entry(p)
        found_any = True
        summary = entry["summary"]
        for token in BANNED_INDEX_SUBSTRINGS:
            assert token not in summary, f"{p.name}: index summary leaked {token!r}: {summary!r}"
        assert len(summary) <= 550, f"{p.name}: index summary too long ({len(summary)} chars)"
    assert found_any


def test_index_card_summary_is_short_and_derived_not_raw_current_state():
    for p in _real_reports():
        r = json.loads(p.read_text(encoding="utf-8"))
        current_state_blocks = r["sections"].get("CURRENT_STATE", {}).get("content_blocks") or []
        raw = current_state_blocks[0] if current_state_blocks else ""
        summary = pd.build_index_card_summary(r)
        assert summary != raw
        assert "현재 판단:" in summary


def test_rendered_index_page_has_pills_and_no_banned_tokens():
    index = pd.build_report_index()
    html_doc = pd._render_index_page(index)
    # Exclude the report_id, which legitimately appears in hrefs/anchors (it is navigation, not
    # the reader-facing summary text) -- the banned-token check applies to the visible summary.
    import re as _re2
    # The summary is the first <p>...</p> inside each <li> (the pills/link <p> tags follow it).
    summaries = _re2.findall(r"<li><h2>.*?</h2><p>(.*?)</p>", html_doc)
    assert summaries
    for token in BANNED_INDEX_SUBSTRINGS:
        for s in summaries:
            assert token not in s, f"{token!r} leaked into rendered index summary: {s!r}"
    assert "보고서 보기" in html_doc
    assert "근거 상태" in html_doc


def test_ai_attribution_translated_to_korean_sentence_in_public_detail_view():
    for p in _real_reports():
        r = json.loads(p.read_text(encoding="utf-8"))
        pub = re_.build_public_view(r)
        import presentation_model as pm
        presentation = pm.build_presentation(pub)
        html_doc = ph.render_product_html(presentation, source_cards=[], view="PUBLIC",
                                           real_sources=[])
        if "AI_ATTRIBUTION=PARTIAL" in json.dumps(r):
            assert "AI_ATTRIBUTION=PARTIAL" not in html_doc
            assert "AI의 영향이 일부 확인되지만" in html_doc
        if "AI_ATTRIBUTION=INDIRECT" in json.dumps(r):
            assert "AI_ATTRIBUTION=INDIRECT" not in html_doc
            assert "간접적으로만 추정" in html_doc


def test_operator_view_keeps_raw_ai_attribution_enum_unchanged():
    for p in _real_reports():
        r = json.loads(p.read_text(encoding="utf-8"))
        text_blob = json.dumps(r)
        if "AI_ATTRIBUTION=PARTIAL" not in text_blob:
            continue
        import presentation_model as pm
        presentation = pm.build_presentation(r)
        html_doc = ph.render_product_html(presentation, source_cards=[], view="OPERATOR",
                                           real_sources=[])
        assert "AI_ATTRIBUTION=PARTIAL" in html_doc
        return
    raise AssertionError("no fixture report contained AI_ATTRIBUTION=PARTIAL to test against")


def test_counterevidence_and_alternative_explanations_sections_still_render_in_public_view():
    for p in _real_reports():
        r = json.loads(p.read_text(encoding="utf-8"))
        pub = re_.build_public_view(r)
        import presentation_model as pm
        presentation = pm.build_presentation(pub)
        html_doc = ph.render_product_html(presentation, source_cards=[], view="PUBLIC",
                                           real_sources=[])
        if r["sections"].get("COUNTEREVIDENCE", {}).get("content_blocks"):
            assert 'id="counterevidence"' in html_doc
        if r["sections"].get("ALTERNATIVE_EXPLANATIONS", {}).get("content_blocks"):
            assert 'id="alternative_explanations"' in html_doc
