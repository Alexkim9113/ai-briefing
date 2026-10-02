# Reader Summary round -- tests for reader_summaries.py and its wiring into product_html.py /
# public_delivery.py. Verifies: schema validity, that every cited hypothesis id actually exists
# with the matching status (so a future hypotheses.json change that invalidates the hand-authored
# text is caught, not silently rendered), that the old generic OPEN-claim placeholder sentence is
# never the opening/representative sentence on Index or Detail PUBLIC pages, that Index/Detail use
# current_judgment_ko, that source_basis never reaches Public HTML, and that no FORECAST-sourced
# value is phrased as a current observation.
import json
import re as _re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import reader_summaries as rsum  # noqa: E402
import report_engine as re_  # noqa: E402
import presentation_model as pm  # noqa: E402
import product_html as ph  # noqa: E402
import public_delivery as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
HYPOTHESES_PATH = ROOT / "intel" / "hypothesis" / "hypotheses.json"
CLAIMS_PATH = ROOT / "intel" / "claims" / "claims.json"

REQUIRED_FIELDS = (
    "current_judgment_ko", "what_we_know_ko", "what_we_dont_know_ko",
    "counterevidence_ko", "watch_next_ko", "source_basis",
)

GENERIC_OPEN_PLACEHOLDER = "현재 확인되지 않았다."

EXPECTED_HYPOTHESIS_STATUS = {
    "hyp_b0a4bbbc9b601728": "SUPPORTED",         # H1
    "hyp_o0_h2_ai_energy_infra": "SUPPORTED",    # H2
    "hyp_o0_h3_ai_energy_infra": "SUPPORTED",    # H3
    "hyp_o0_h4_ai_energy_infra": "SUPPORTED",    # H4
    "hyp_o0_h5_ai_energy_infra": "WEAKENED",     # H5
    "hyp_o0_h6_ai_energy_infra": "WEAKENED",     # H6
    "hyp_b365b95148a3a372": "PARTIALLY_SUPPORTED",  # HL1
    "hyp_c4b0429622eb6dd7": "PARTIALLY_SUPPORTED",  # HL3
    "hyp_b3a8bfef91a47a45": "CONTESTED",             # HL2
    "hyp_8691a1cb2d7c0d45": "WEAKENED",              # HL4
}


def test_schema_has_required_fields_and_correct_types():
    assert rsum.READER_SUMMARIES
    for iid, summary in rsum.READER_SUMMARIES.items():
        for field in REQUIRED_FIELDS:
            assert field in summary, f"{iid}: missing {field}"
        assert isinstance(summary["current_judgment_ko"], str) and summary["current_judgment_ko"]
        for field in ("what_we_know_ko", "what_we_dont_know_ko", "counterevidence_ko",
                      "watch_next_ko", "source_basis"):
            assert isinstance(summary[field], list) and summary[field], f"{iid}: {field} must be a non-empty list"
            assert all(isinstance(x, str) and x for x in summary[field])


def test_hypothesis_status_matches_verification():
    """Section 2 of the Reader Summary brief: every hypothesis_id cited in source_basis that is a
    hyp_ id must exist in hypotheses.json with exactly the status it was verified against. If any
    status has changed since the summary text was authored, this test fails loudly rather than
    letting stale text render silently."""
    hyps = json.loads(HYPOTHESES_PATH.read_text(encoding="utf-8"))
    checked = set()
    for iid, summary in rsum.READER_SUMMARIES.items():
        for ref in summary["source_basis"]:
            if not ref.startswith("hyp_"):
                continue
            assert ref in hyps, f"{iid}: cited hypothesis {ref} does not exist in hypotheses.json"
            expected = EXPECTED_HYPOTHESIS_STATUS.get(ref)
            assert expected, f"{ref}: no expected status recorded in this test -- update EXPECTED_HYPOTHESIS_STATUS"
            actual = hyps[ref].get("status")
            assert actual == expected, (
                f"{ref}: hypotheses.json status is {actual!r} but the Reader Summary text was "
                f"verified against {expected!r} -- STOP, re-verify the summary text before using it"
            )
            checked.add(ref)
    assert checked == set(EXPECTED_HYPOTHESIS_STATUS)


def test_claim_ids_in_source_basis_exist():
    claims = json.loads(CLAIMS_PATH.read_text(encoding="utf-8"))
    for iid, summary in rsum.READER_SUMMARIES.items():
        for ref in summary["source_basis"]:
            if ref.startswith("claim_"):
                assert ref in claims, f"{iid}: cited claim {ref} does not exist in claims.json"


def _real_reports():
    return sorted(re_.REPORTS_DIR.glob("report_intel_*_v*.json"))


def test_no_generic_placeholder_as_opening_sentence():
    for p in _real_reports():
        r = json.loads(p.read_text(encoding="utf-8"))
        if not rsum.get_reader_summary(r.get("intelligence_id")):
            continue
        pub = re_.build_public_view(r)
        presentation = pm.build_presentation(pub)
        html_doc = ph.render_product_html(presentation, source_cards=[], view="PUBLIC", real_sources=[])
        lede_match = _re.search(r'id="lede-h">([^<]*)</h2><p>(.*?)</p>', html_doc)
        assert lede_match, f"{p.name}: no lede section found"
        opening_text = lede_match.group(2)
        assert GENERIC_OPEN_PLACEHOLDER not in opening_text

        entry = pd.build_intelligence_index_entry(p)
        assert GENERIC_OPEN_PLACEHOLDER not in entry["summary"]


def test_index_and_detail_use_current_judgment_ko():
    for p in _real_reports():
        r = json.loads(p.read_text(encoding="utf-8"))
        summary = rsum.get_reader_summary(r.get("intelligence_id"))
        if not summary:
            continue
        entry = pd.build_intelligence_index_entry(p)
        assert entry["summary"] == summary["current_judgment_ko"]

        pub = re_.build_public_view(r)
        presentation = pm.build_presentation(pub)
        html_doc = ph.render_product_html(presentation, source_cards=[], view="PUBLIC", real_sources=[])
        assert summary["current_judgment_ko"] in html_doc


def test_source_basis_never_rendered_in_public_html():
    for p in _real_reports():
        r = json.loads(p.read_text(encoding="utf-8"))
        summary = rsum.get_reader_summary(r.get("intelligence_id"))
        if not summary:
            continue
        pub = re_.build_public_view(r)
        presentation = pm.build_presentation(pub)
        html_doc = ph.render_product_html(presentation, source_cards=[], view="PUBLIC", real_sources=[])
        for ref in summary["source_basis"]:
            assert ref not in html_doc, f"{p.name}: source_basis id {ref} leaked into Public HTML"

        index = pd.build_report_index()
        index_html = pd._render_index_page(index)
        for ref in summary["source_basis"]:
            assert ref not in index_html


def test_source_basis_never_used_in_operator_workspace():
    """Section 7 of the brief: this module must not be imported anywhere in
    intel/operator_workspace/ -- the Operator Inspector keeps showing full canonical
    hypothesis/claim data, unaffected by this presentation-layer module's existence."""
    ow_dir = ROOT / "intel" / "operator_workspace"
    for py_file in ow_dir.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        assert "reader_summaries" not in text, f"{py_file}: must not import reader_summaries"


def test_forecast_values_not_phrased_as_current_observation():
    """Section 6 (epistemic language check): the forecast sentence (IEA 2030/2035 projection) must
    be clearly marked as a forecast, never phrased as something already observed."""
    energy_summary = rsum.READER_SUMMARIES["intel_87210a61730c22b9"]
    forecast_sentences = [s for s in energy_summary["what_we_know_ko"] if "945TWh" in s or "1,200TWh" in s]
    assert forecast_sentences, "expected a forecast sentence in what_we_know_ko"
    for s in forecast_sentences:
        assert "전망" in s or "예측값" in s
        assert "관측되고 있다" not in s and "발생하고 있다" not in s
