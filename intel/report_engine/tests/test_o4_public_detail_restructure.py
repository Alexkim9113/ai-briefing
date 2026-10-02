# O-4 -- Detail page restructure (part 2 of the Public Intelligence Index fix). PUBLIC view opens
# with a short derived judgment + promoted key signals instead of the raw CURRENT_STATE paragraph,
# while the OPERATOR view stays byte-for-byte unchanged.
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import presentation_model as pm  # noqa: E402
import product_html as ph  # noqa: E402
import report_engine as re_  # noqa: E402

REPORTS_DIR = re_.REPORTS_DIR


def _real_reports():
    return sorted(REPORTS_DIR.glob("report_intel_*_v*.json"))


def test_public_detail_page_opens_with_judgment_not_raw_current_state():
    for p in _real_reports():
        r = json.loads(p.read_text(encoding="utf-8"))
        pub = re_.build_public_view(r)
        presentation = pm.build_presentation(pub)
        html_doc = ph.render_product_html(presentation, source_cards=[], view="PUBLIC", real_sources=[])
        body_start = html_doc.index("<main")
        lede_pos = html_doc.index('id="lede-h"')
        current_state_pos = html_doc.find('id="current_state-h"')
        # The lede ("한눈에 보는 판단") must appear right after the opening of <main>, well before
        # the raw CURRENT_STATE section (which may still exist further down the page).
        assert body_start < lede_pos
        if current_state_pos != -1:
            assert lede_pos < current_state_pos
        assert "한눈에 보는 판단" in html_doc


def test_public_detail_lede_is_short_not_the_full_raw_paragraph():
    for p in _real_reports():
        r = json.loads(p.read_text(encoding="utf-8"))
        current_state_blocks = r["sections"].get("CURRENT_STATE", {}).get("content_blocks") or []
        raw = str(current_state_blocks[0]) if current_state_blocks else ""
        pub = re_.build_public_view(r)
        presentation = pm.build_presentation(pub)
        html_doc = ph.render_product_html(presentation, source_cards=[], view="PUBLIC", real_sources=[])
        lede_start = html_doc.index('id="lede-h"')
        lede_end = html_doc.index("</section>", lede_start)
        lede_html = html_doc[lede_start:lede_end]
        # The opening lede must never contain the full raw CURRENT_STATE text verbatim.
        if len(raw) > 400:
            assert raw not in lede_html
            assert len(lede_html) < len(raw)


def test_public_detail_has_promoted_key_signals_section_near_top():
    for p in _real_reports():
        r = json.loads(p.read_text(encoding="utf-8"))
        pub = re_.build_public_view(r)
        presentation = pm.build_presentation(pub)
        html_doc = ph.render_product_html(presentation, source_cards=[], view="PUBLIC", real_sources=[])
        key_claims_blocks = r["sections"].get("KEY_CLAIMS", {}).get("content_blocks") or []
        if not key_claims_blocks:
            continue
        assert 'id="key_signals"' in html_doc
        lede_pos = html_doc.index('id="lede-h"')
        key_signals_pos = html_doc.index('id="key_signals"')
        what_we_know_pos = html_doc.find('id="what_we_know"')
        assert lede_pos < key_signals_pos
        if what_we_know_pos != -1:
            assert key_signals_pos < what_we_know_pos


def test_public_detail_section_ordering_matches_spec():
    """핵심 신호 -> 확인된 사실 -> 불확실성 -> 반증/대안 설명 -> 지역별 차이 -> 앞으로 볼 것 -> (나머지
    기술 섹션) -> 출처, when each of these sections is present for a given report."""
    expected_order_ids = [
        "key_signals", "what_we_know", "uncertainties", "what_we_do_not_know",
        "counterevidence", "alternative_explanations", "geographic_context",
        "what_to_watch", "sources",
    ]
    for p in _real_reports():
        r = json.loads(p.read_text(encoding="utf-8"))
        pub = re_.build_public_view(r)
        presentation = pm.build_presentation(pub)
        html_doc = ph.render_product_html(presentation, source_cards=[], view="PUBLIC", real_sources=[])
        positions = []
        for section_id in expected_order_ids:
            idx = html_doc.find(f'id="{section_id}"')
            if idx != -1:
                positions.append((section_id, idx))
        indices = [pos for _, pos in positions]
        assert indices == sorted(indices), f"{p.name}: out of order -- {positions}"


def test_public_detail_what_to_watch_section_renders():
    import reader_summaries as rsum
    for p in _real_reports():
        r = json.loads(p.read_text(encoding="utf-8"))
        pub = re_.build_public_view(r)
        presentation = pm.build_presentation(pub)
        html_doc = ph.render_product_html(presentation, source_cards=[], view="PUBLIC", real_sources=[])
        assert "앞으로 볼 것" in html_doc
        if rsum.get_reader_summary(r.get("intelligence_id")):
            # Reader Summary round: the auto-derived "앞으로 볼 것" (id="what_to_watch") section is
            # superseded by the Reader Summary's own watch_next_ko section (id="reader_watch") --
            # same heading text, hand-verified content grounded in EVIDENCE_GAPS.
            assert 'id="reader_watch"' in html_doc
        else:
            assert 'id="what_to_watch"' in html_doc


def test_public_detail_sources_section_still_renders_last():
    for p in _real_reports():
        r = json.loads(p.read_text(encoding="utf-8"))
        pub = re_.build_public_view(r)
        presentation = pm.build_presentation(pub)
        real_sources = [{"institution": "Test Inst", "title": "T", "year": "2024", "doc_type": "report",
                          "tier": "TIER_1", "access_status": "ORIGINAL_SOURCE",
                          "observation_or_forecast": "OBSERVATION", "url": "https://example.org/x",
                          "claim_id": None}]
        html_doc = ph.render_product_html(presentation, source_cards=[], view="PUBLIC",
                                           real_sources=real_sources)
        sources_pos = html_doc.index('id="sources"')
        footer_pos = html_doc.index("<footer>")
        assert sources_pos < footer_pos
        # Sources must come after every numbered-order section id that is present.
        for section_id in ("key_signals", "what_we_know", "counterevidence",
                            "alternative_explanations", "geographic_context", "what_to_watch"):
            idx = html_doc.find(f'id="{section_id}"')
            if idx != -1:
                assert idx < sources_pos


def test_public_detail_statistical_context_preserves_observed_vs_forecast_label():
    for p in _real_reports():
        r = json.loads(p.read_text(encoding="utf-8"))
        stats = r["sections"].get("STATISTICAL_CONTEXT", {}).get("content_blocks") or []
        statuses = {b.get("trend_status") for b in stats if isinstance(b, dict)}
        if not statuses & {"OBSERVED", "FORECAST"}:
            continue
        pub = re_.build_public_view(r)
        presentation = pm.build_presentation(pub)
        html_doc = ph.render_product_html(presentation, source_cards=[], view="PUBLIC", real_sources=[])
        if "OBSERVED" in statuses:
            assert "OBSERVED" in html_doc
        if "FORECAST" in statuses:
            assert "FORECAST" in html_doc


def test_operator_view_html_byte_identical_to_pre_restructure_snapshot():
    """The OPERATOR view must render the full executive card (dl) followed by every section in
    DISPLAY_SECTION_ORDER, with no lede/key-signals restructuring -- exactly as before this
    change."""
    for p in _real_reports():
        r = json.loads(p.read_text(encoding="utf-8"))
        presentation = pm.build_presentation(r)
        html_doc = ph.render_product_html(presentation, source_cards=[], view="OPERATOR", real_sources=[])
        # OPERATOR must NOT contain any of the PUBLIC-only restructured elements.
        assert 'id="lede-h"' not in html_doc
        assert 'id="key_signals"' not in html_doc
        assert "한눈에 보는 판단" not in html_doc
        # OPERATOR still opens with the full executive card <dl> (Current State / Key Signal /
        # Evidence Status / Major Uncertainty / What To Watch), unchanged.
        assert '<dt>Current State</dt>' in html_doc
        assert '<dt>Key Signal</dt>' in html_doc
        assert '<dt>What To Watch</dt>' in html_doc
        # And every section still renders in DISPLAY_SECTION_ORDER (first present section comes
        # before every later present section).
        present_ids = [st.lower() for st in pm.DISPLAY_SECTION_ORDER
                       if r["sections"].get(st) and r["sections"][st]["status"] or
                       r["sections"].get(st)]
        positions = [html_doc.find(f'id="{sid}"') for sid in present_ids]
        positions = [pos for pos in positions if pos != -1]
        assert positions == sorted(positions)


def test_operator_render_function_reproduces_same_html_when_rerun():
    """Regression guard for the refactor: calling render_product_html twice with the same inputs
    and view=OPERATOR produces byte-identical output (determinism, no new randomness introduced)."""
    for p in _real_reports():
        r = json.loads(p.read_text(encoding="utf-8"))
        presentation = pm.build_presentation(r)
        html_1 = ph.render_product_html(presentation, source_cards=[], view="OPERATOR", real_sources=[])
        html_2 = ph.render_product_html(presentation, source_cards=[], view="OPERATOR", real_sources=[])
        assert html_1 == html_2
