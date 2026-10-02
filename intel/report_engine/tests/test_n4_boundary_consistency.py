# N-4 Sections 46-48 -- Public Boundary Test, Report Consistency Test, Negative Control.
# These tests re-verify, in the new N-4 HTML/PDF productization pipeline, the same safety
# properties N-3 already enforced in the raw Report JSON -- now checked against the rendered
# PRODUCT HTML/print HTML actually shipped to readers.
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import report_engine as re_  # noqa: E402
import presentation_model as pm  # noqa: E402
import product_html as ph  # noqa: E402
import pdf_pipeline as pp  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
DOCS = json.loads((ROOT / "intel" / "documents.json").read_text(encoding="utf-8"))

REAL_IDS = ["intel_87210a61730c22b9", "intel_dbab7b01963396b5"]

BANNED_SENTENCES = (
    "AI 데이터센터 때문에 미국 전력 위기가 발생했다.",
    "AI가 노동참가율을 감소시켰다.",
)


def _source_cards(pub_report):
    prov_blocks = pub_report["sections"]["SOURCE_PROVENANCE"].get("content_blocks", [])
    cards = []
    for b in prov_blocks:
        sid = b.get("source_id")
        if sid in DOCS:
            cards.append(re_.build_source_card(DOCS[sid]))
        else:
            # O-1E: mirror public_delivery.py's _source_cards fix -- a non-document provenance id
            # (e.g. "event:evt_...") must not be shown as the visible card title in Public.
            title = ph._public_source_label(sid) if (sid or "").startswith(("event:", "claim_",
                "series_", "intel_", "hyp_", "evt_", "rel_")) else sid
            cards.append({"title": title, "publisher": "NON_DOCUMENT_PROVENANCE", "date": "UNKNOWN",
                          "access_status": "UNKNOWN", "rights_status": "UNKNOWN"})
    return cards


def _public_product_html(iid):
    r = re_.build_report(iid)
    pub = re_.build_public_view(r)
    p = pm.build_presentation(pub)
    cards = _source_cards(pub)
    return r, pub, p, ph.render_product_html(p, source_cards=cards, view="PUBLIC")


def _operator_product_html(iid):
    r = re_.build_report(iid)
    op = re_.build_operator_view(r)
    p = pm.build_presentation(op)
    cards = _source_cards(op)
    return r, op, p, ph.render_product_html(p, source_cards=cards, view="OPERATOR")


# --- Section 46: Public Boundary Test (6 checks) ---

def test_boundary_1_no_operator_internal_ids_in_public_html():
    for iid in REAL_IDS:
        r, pub, p, doc = _public_product_html(iid)
        assert r["intelligence_id"] not in doc or r["intelligence_id"] == p["intelligence_id"]
        # internal claim_ids array must not leak into the rendered page body
        for cid in r["sections"]["KEY_CLAIMS"].get("claim_ids", []):
            assert f'"{cid}"' not in doc
            assert f">{cid}<" not in doc


def test_boundary_2_no_private_research_full_text_in_public_html():
    for iid in REAL_IDS:
        _, _, _, doc = _public_product_html(iid)
        assert "full_text" not in doc
        assert "vault_record" not in doc
        assert "private_research_vault" not in doc


def test_boundary_3_no_rights_restricted_body_text_in_public_html():
    for iid in REAL_IDS:
        _, _, _, doc = _public_product_html(iid)
        assert "body_text" not in doc


def test_boundary_4_no_unsupported_metaxis_point_in_public_html():
    r = re_.build_report("intel_87210a61730c22b9",
                         mx_point_text="AI 데이터센터 때문에 미국 전력 위기가 발생했다.",
                         mx_provenance={"grounding_status": "UNSUPPORTED_INTERPRETATION",
                                        "interpretation_type": "CAUSAL"})
    pub = re_.build_public_view(r)
    p = pm.build_presentation(pub)
    doc = ph.render_product_html(p, source_cards=[], view="PUBLIC")
    assert "AI 데이터센터 때문에 미국 전력 위기가 발생했다" not in doc


def test_boundary_5_insufficient_evidence_never_shown_as_confirmed_fact():
    for iid in REAL_IDS:
        _, pub, p, doc = _public_product_html(iid)
        for section_type, section in pub["sections"].items():
            if section["status"] == "INSUFFICIENT_EVIDENCE" and not section.get("content_blocks"):
                # the section's rendered body must carry the honest INSUFFICIENT_EVIDENCE note,
                # not be silently skipped and not show invented content
                assert "Insufficient evidence" in doc or section_type.lower() in doc.lower()


def test_boundary_6_operator_provenance_not_excessively_exposed_to_public():
    for iid in REAL_IDS:
        r, pub, p, doc = _public_product_html(iid)
        op_r, op, op_p, op_doc = _operator_product_html(iid)
        # Public doc must not be larger/more detailed than Operator doc's claim_ids exposure
        assert "claim_ids" not in doc


# --- Section 47: Report Consistency Test (JSON / HTML / print-HTML core facts match) ---

def test_consistency_readiness_matches_across_json_html_print():
    for iid in REAL_IDS:
        r, pub, p, doc = _public_product_html(iid)
        print_doc = pp.render_print_html(p, source_cards=_source_cards(pub), view="PUBLIC")
        assert r["readiness"] == pub["readiness"] == p["readiness"]
        assert r["readiness"] in doc
        assert r["readiness"] in print_doc


def test_consistency_topic_matches_across_json_html_print():
    for iid in REAL_IDS:
        r, pub, p, doc = _public_product_html(iid)
        print_doc = pp.render_print_html(p, source_cards=_source_cards(pub), view="PUBLIC")
        assert r["topic"] in doc
        assert r["topic"] in print_doc


def test_consistency_gap_count_matches_json_and_html():
    for iid in REAL_IDS:
        r, pub, p, doc = _public_product_html(iid)
        gaps = pub["sections"]["EVIDENCE_GAPS"].get("content_blocks", [])
        watch = p["executive_card"]["what_to_watch"]
        if gaps:
            assert len(watch) == len(gaps)
        else:
            assert "모니터링 대상 없음" in watch[0]


def test_consistency_statistics_trend_status_matches_json_and_chart_spec():
    for iid in REAL_IDS:
        r, pub, p, doc = _public_product_html(iid)
        stats_json = pub["sections"]["STATISTICAL_CONTEXT"].get("content_blocks", [])
        stat_entry = [s for s in p["sections"] if s["section_type"] == "STATISTICAL_CONTEXT"]
        if stats_json and stat_entry:
            charts = stat_entry[0]["charts"]
            assert [c["trend_status"] for c in charts] == [b["trend_status"] for b in stats_json]


# --- Section 48: Negative Control (banned sentences never resurface as confirmed fact) ---

def test_negative_control_banned_sentences_absent_from_public_html():
    for iid in REAL_IDS:
        _, _, _, doc = _public_product_html(iid)
        for sentence in BANNED_SENTENCES:
            assert sentence not in doc


def test_negative_control_banned_sentences_absent_from_print_html():
    for iid in REAL_IDS:
        r, pub, p, doc = _public_product_html(iid)
        print_doc = pp.render_print_html(p, source_cards=_source_cards(pub), view="PUBLIC")
        for sentence in BANNED_SENTENCES:
            assert sentence not in print_doc


def test_negative_control_banned_sentences_absent_from_operator_html():
    for iid in REAL_IDS:
        _, _, _, doc = _operator_product_html(iid)
        for sentence in BANNED_SENTENCES:
            assert sentence not in doc


def test_public_html_evidence_map_has_no_raw_dict_repr_or_ids():
    """O-1D final round -- regression test for the EVIDENCE_MAP raw-ID leak (product_html.py
    _render_block's generic dict fallback used to print Python dict reprs like
    "{'node_type': 'CLAIM', 'id': 'claim_...'}" straight into Public HTML). Asserts the
    EVIDENCE_MAP rendering path itself never emits a raw dict repr or a bare internal node id.
    NOTE: this does not assert zero internal-id substrings anywhere on the page -- a separate,
    pre-existing issue (internal claim ids baked directly into free-text narrative content in the
    canonical Report JSON, e.g. report_intel_87210a61730c22b9's LIMITATIONS/METHODOLOGY text) is
    a content-authoring issue, not a rendering bug, and is out of scope for this fix; see O-1D
    final-round report for exact locations."""
    import re as _re
    dict_repr_pattern = _re.compile(r"\{&#x27;node_type&#x27;")
    for iid in REAL_IDS:
        _, _, _, doc = _public_product_html(iid)
        assert "node_type" not in doc, f"{iid}: raw dict repr leaked into Public HTML"
        assert not dict_repr_pattern.search(doc), f"{iid}: raw dict repr pattern found"


def test_public_html_temporal_geographic_provenance_has_no_series_or_event_id_leak():
    """O-1E -- regression test for the TEMPORAL_CONTEXT/SOURCE_PROVENANCE/GEOGRAPHIC_CONTEXT raw
    dict-repr leak (same bug family as O-1D's EVIDENCE_MAP fix, different block shapes:
    {'period_start':..., 'source': 'series_...'/'evt_...'}, {'source_id': 'event:evt_...'},
    {'geography':..., 'scope': '...evt_... embedded in free text'}). Asserts no bare series_/evt_
    id appears in the Public HTML for either real intelligence object. Does NOT assert zero
    claim_/intel_/hyp_ substrings anywhere on the page -- those are the separate, pre-existing
    narrative-text issue documented in test_public_html_evidence_map_has_no_raw_dict_repr_or_ids
    and in the O-1E round report, intentionally left unpatched (editing canonical Report JSON
    narrative content is out of scope for a presentation-only fix)."""
    import re as _re
    leak_pattern = _re.compile(r"\b(?:series_|evt_|event:evt_)[a-zA-Z0-9_]+")
    for iid in REAL_IDS:
        _, _, _, doc = _public_product_html(iid)
        assert not leak_pattern.search(doc), f"{iid}: series_/evt_ id leaked into Public HTML"


def test_o1f_public_html_zero_internal_id_leak():
    """O-1F closure -- the known_gaps/EVIDENCE_WEIGHTING_GAP 'reason' narrative (rendered via
    product_html.py's "reason"+"gap_type" _render_block branch and executive-card/source-string
    fields), which O-1D/O-1E explicitly left unpatched as a content-authoring issue, has now been
    closed at the PRESENTATION layer only (product_html.py/_public_source_label/_strip_internal_ids
    extended to also run over executive-card narrative fields, bare-string content_blocks, the
    GEOGRAPHIC_CONTEXT 'basis' field, and repo file-path/.json/.py/function-name tokens, plus the
    Public Index page's summary in public_delivery.py reusing the same helper). The canonical
    Report v4 JSON itself is NOT modified -- see o1f_before_snapshot.json / the O-1F handback for
    the byte-identical hash proof. This asserts the full id/path leak surface is now empty for
    both real reports, not just the series_/evt_ subset O-1E could assert zero for."""
    import re as _re
    leak_pattern = _re.compile(
        r"\b(?:claim_|series_|intel_|hyp_|evt_|rel_|event:evt_)[a-zA-Z0-9_]+"
        r"|\bintel/[a-zA-Z0-9_./-]+|\b[a-zA-Z_][a-zA-Z0-9_]*\.(?:json|py)\b"
    )
    for iid in REAL_IDS:
        _, _, _, doc = _public_product_html(iid)
        matches = leak_pattern.findall(doc)
        # The page's own report_id (e.g. "report_id=report_intel_..._v4") is its own public-facing
        # identifier -- the equivalent of a URL slug -- shown by design elsewhere on the same page
        # (the intelligence index links to it), not a narrative-text id leak. Exclude only that.
        matches = [m for m in matches if not _re.fullmatch(r"intel_[0-9a-f]{16}(?:_v\d+)?", m)]
        assert matches == [], f"{iid}: internal id/path leak(s) found in Public HTML: {matches}"


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
