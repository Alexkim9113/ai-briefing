# O-2C Priorities 2-6 -- regression tests for: the Public Intelligence Index responsive-overflow
# fix (Priority 2), human-readable Public headlines (Priority 4), inline citations only ever
# pointing at a real, actually-cited source (Priority 5), and the consolidated Evidence Map
# withheld-connection sentence (Priority 6). Priority 3 (accessibility/keyboard nav) and the
# reader-flow section reorder (Priority 4) were verified with a real headless-Chromium/Playwright
# pass outside this test file (no Playwright dependency is added to the pytest suite itself).
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent / "operator_workspace"))
import product_html as ph  # noqa: E402
import public_delivery as pd  # noqa: E402
import presentation_model as pm  # noqa: E402
import report_engine as re_  # noqa: E402
import source_registry as sreg  # noqa: E402

FROZEN_V4_HASH = "beb034796e62d93f9a1921c450dca441812fdd56f99fc42eef46c9a2a9ca9420"
V4_PATH = re_.REPORTS_DIR / "report_intel_87210a61730c22b9_v4.json"
V3_LABOR_PATH = re_.REPORTS_DIR / "report_intel_dbab7b01963396b5_v3.json"


def test_ai_energy_infra_v4_hash_still_frozen():
    assert hashlib.sha256(V4_PATH.read_bytes()).hexdigest() == FROZEN_V4_HASH


# ---- Priority 2: Public Index no longer has an unstyled, overflow-prone page --------------------

def test_public_index_page_has_overflow_wrap_css():
    index_html = pd._render_index_page([])
    assert "overflow-wrap" in index_html
    assert "<style>" in index_html


def test_public_index_renders_a_long_unbroken_summary_token_without_removing_css():
    # Regression for the real bug found by Playwright measurement: a 200+ char slash-joined
    # token (e.g. a section-type list with no spaces) in a report's summary must not strip the
    # page back down to no responsive CSS.
    long_token = "A" + "/".join(["WORD"] * 40)
    entry = {
        "report_id": "report_intel_test_v1", "title": "Test Report", "readiness": "READY",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "summary": f"intro {long_token} outro",
        "available_formats": {"pdf": False},
    }
    html = pd._render_index_page([entry])
    assert long_token in html
    assert "overflow-wrap" in html


# ---- Priority 4: human-readable Public headline, topic_id untouched internally ------------------

def test_known_topics_get_a_human_readable_public_headline():
    assert pm.TOPIC_DISPLAY_TITLES["AI_ENERGY_INFRA"] != "AI_ENERGY_INFRA"
    assert pm.TOPIC_DISPLAY_TITLES["AI_LABOR"] != "AI_LABOR"


def test_build_presentation_uses_human_readable_title_but_keeps_topic_field_unchanged():
    r = json.loads(V4_PATH.read_text(encoding="utf-8"))
    presentation = pm.build_presentation(re_.build_public_view(r))
    assert presentation["topic"] == "AI_ENERGY_INFRA"  # internal identifier never altered
    assert presentation["display_title"] == pm.TOPIC_DISPLAY_TITLES["AI_ENERGY_INFRA"]
    assert "AI_ENERGY_INFRA" not in presentation["display_title"]


def test_index_entry_title_is_also_human_readable():
    entry = pd.build_intelligence_index_entry(V4_PATH)
    assert entry["title"] == pm.TOPIC_DISPLAY_TITLES["AI_ENERGY_INFRA"]
    assert entry["topic"] == "AI_ENERGY_INFRA"  # canonical topic field untouched


def test_unknown_topic_falls_back_to_old_behavior_not_a_crash():
    r = json.loads(V4_PATH.read_text(encoding="utf-8"))
    r = dict(r, topic="SOME_FUTURE_TOPIC")
    presentation = pm.build_presentation(re_.build_public_view(r))
    assert presentation["display_title"] == "SOME_FUTURE_TOPIC Intelligence Report"


# ---- Priority 4: reader-flow section reorder -----------------------------------------------------

def test_display_section_order_puts_counterevidence_before_what_we_do_not_know():
    order = pm.DISPLAY_SECTION_ORDER
    assert order.index("COUNTEREVIDENCE") < order.index("WHAT_WE_DO_NOT_KNOW")
    assert order.index("ALTERNATIVE_EXPLANATIONS") < order.index("WHAT_WE_DO_NOT_KNOW")
    assert order.index("KEY_QUESTION") == 0
    assert order.index("CURRENT_STATE") == 1
    assert order.index("SOURCE_PROVENANCE") == len(order) - 1
    assert order.index("EVIDENCE_MAP") == len(order) - 2


# ---- Priority 5: inline citations are real, never fabricated/misattributed ----------------------

def _render(report_path):
    r = json.loads(report_path.read_text(encoding="utf-8"))
    pub = re_.build_public_view(r)
    presentation = pm.build_presentation(pub)
    real_sources = sreg.build_sources_for_report(r)
    return ph.render_product_html(presentation, source_cards=None, view="PUBLIC",
                                   real_sources=real_sources), real_sources


def test_ai_energy_infra_public_page_has_at_least_three_real_inline_citations():
    html, real_sources = _render(V4_PATH)
    claim_ids_in_sources = {s["claim_id"] for s in real_sources if s.get("claim_id")}
    citation_anchors = re.findall(r'<sup class="cite"><a href="#source-(\d+)">([^<]+)</a></sup>',
                                   html)
    assert len(citation_anchors) >= 3
    # Every cited #source-N anchor must point at a source position that actually exists.
    for idx, _label in citation_anchors:
        assert 1 <= int(idx) <= len(real_sources)
    # Every claim_id this module cites inline must be one this report's own Sources list actually
    # contains -- never a fabricated or misattributed citation.
    for substring, claim_id in ph._INLINE_CITATIONS["AI_ENERGY_INFRA"]:
        assert claim_id in claim_ids_in_sources, (
            f"inline citation for {substring!r} points at {claim_id}, which is not in this "
            "report's own real_sources"
        )


def test_ai_labor_public_page_has_at_least_three_real_inline_citations():
    html, real_sources = _render(V3_LABOR_PATH)
    claim_ids_in_sources = {s["claim_id"] for s in real_sources if s.get("claim_id")}
    citation_anchors = re.findall(r'<sup class="cite"><a href="#source-(\d+)">([^<]+)</a></sup>',
                                   html)
    assert len(citation_anchors) >= 3
    for substring, claim_id in ph._INLINE_CITATIONS["AI_LABOR"]:
        assert claim_id in claim_ids_in_sources, (
            f"inline citation for {substring!r} points at {claim_id}, which is not in this "
            "report's own real_sources"
        )


def test_no_unresolved_citation_markers_ever_leak_into_rendered_html():
    for path in (V4_PATH, V3_LABOR_PATH):
        html, _ = _render(path)
        assert "@@CITE" not in html


def test_resolve_citations_strips_a_claim_id_not_actually_in_this_reports_sources():
    # Never fabricate/misattribute: a marker for a claim_id absent from real_sources must be
    # dropped, not linked to a wrong/nonexistent anchor.
    doc = "<li>some fact@@CITE:claim_deadbeef00000000@@</li>"
    out = ph._resolve_citations(doc, real_sources=[{"claim_id": "claim_ea000000000000aa", "institution": "X",
                                                      "year": "2020"}])
    assert "@@CITE" not in out
    assert "<sup" not in out


# ---- Priority 6: Evidence Map consolidated withheld-connection sentence -------------------------

def test_evidence_map_withheld_text_is_consolidated_not_repeated_per_node():
    html, _ = _render(V4_PATH)
    # The old phrasing repeated once per non-CLAIM node (8-12+ times in the frozen v4 report); the
    # new phrasing must appear at most once per report.
    assert html.count("internal id withheld in Public view") == 0 or \
           "현재 공개 가능한 연결 정보가 없습니다" in html
    assert html.count("현재 공개 가능한 연결 정보가 없습니다") <= 1


def test_evidence_map_still_shows_real_claim_chains_for_claim_nodes():
    html, _ = _render(V4_PATH)
    assert "<strong>주장</strong>" in html
    assert "<strong>출처</strong>" in html
    assert "<strong>역할</strong>" in html
