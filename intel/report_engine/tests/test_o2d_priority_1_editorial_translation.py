# O-2D Priority 1 -- regression tests for the Editorial Translation Layer: internal
# engineering jargon (Evidence Evaluation Contract, guard_trail, canonical_status_diagnostics,
# sufficiency guards, SEARCH_NOT_RUN, source tier, write path, bare round references like
# "O-1B"/"[v3 update]", etc) must never reach the rendered PUBLIC page, while the OPERATOR page
# must keep the exact original technical text unchanged. This is presentation-only: the
# canonical Report JSON (and its frozen hash) is never touched.
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import product_html as ph  # noqa: E402
import report_engine as re_  # noqa: E402
import report_ops as rops  # noqa: E402

FROZEN_V4_HASH = "beb034796e62d93f9a1921c450dca441812fdd56f99fc42eef46c9a2a9ca9420"
V4_PATH = re_.REPORTS_DIR / "report_intel_87210a61730c22b9_v4.json"
V3_LABOR_PATH = re_.REPORTS_DIR / "report_intel_dbab7b01963396b5_v3.json"

JARGON_PHRASES = [
    "Evidence Evaluation Contract",
    "guard_trail",
    "canonical_status_diagnostics",
    "sufficiency guard",
    "SEARCH_NOT_RUN",
    "UNKNOWN-tier guard",
    "source tier",
    "source-tier",
    "write path",
    "canonical claim",
    "canonical status",
]


def test_ai_energy_infra_v4_hash_still_frozen():
    # Priority 1 is presentation-only -- must never touch the canonical Report JSON.
    assert hashlib.sha256(V4_PATH.read_bytes()).hexdigest() == FROZEN_V4_HASH


def _build_html(path, view):
    r = json.loads(path.read_text(encoding="utf-8"))
    status = rops.build_artifacts_with_failure_isolation(r, {}, view=view)
    assert status["html"] == "HTML_READY"
    return status["html_doc"]


def test_public_html_has_no_dev_jargon_ai_energy_infra():
    html_doc = _build_html(V4_PATH, "PUBLIC")
    for phrase in JARGON_PHRASES:
        assert phrase not in html_doc, f"jargon phrase leaked into Public HTML: {phrase!r}"
    assert "[v3 update]" not in html_doc
    assert "O-1B" not in html_doc


def test_public_html_has_no_dev_jargon_ai_labor():
    html_doc = _build_html(V3_LABOR_PATH, "PUBLIC")
    for phrase in JARGON_PHRASES:
        assert phrase not in html_doc, f"jargon phrase leaked into Public HTML: {phrase!r}"
    assert "O-2 round" not in html_doc


def test_operator_html_keeps_original_technical_text_ai_energy_infra():
    # Operator must see the unmodified canonical narrative -- the translation layer is gated
    # strictly to view == "PUBLIC" and must never touch Operator's rendering.
    html_doc = _build_html(V4_PATH, "OPERATOR")
    for phrase in ["Evidence Evaluation Contract", "guard_trail", "canonical_status_diagnostics",
                   "sufficiency guard", "SEARCH_NOT_RUN"]:
        assert phrase in html_doc, f"Operator lost original technical text: {phrase!r}"


def test_operator_html_keeps_original_technical_text_ai_labor():
    html_doc = _build_html(V3_LABOR_PATH, "OPERATOR")
    assert "UNKNOWN-tier guard" in html_doc


def test_editorial_translation_applies_only_to_public_strip_internal_ids():
    text = "This uses the Evidence Evaluation Contract and a guard_trail."
    operator_out = ph._strip_internal_ids(text, "OPERATOR")
    public_out = ph._strip_internal_ids(text, "PUBLIC")
    assert operator_out == text
    assert "Evidence Evaluation Contract" not in public_out
    assert "guard_trail" not in public_out
    assert "근거 평가 기준" in public_out
    assert "검증 과정" in public_out


def test_editorial_translation_preserves_status_words_and_numbers():
    # Meaning-preservation check: the translation must not drop the actual judgment content
    # (status words, percentages, named sources) around the jargon it replaces.
    text = ("H3 corrected from SUPPORTED to PARTIALLY_SUPPORTED after applying a new "
            "deterministic Evidence Evaluation Contract (source tier / directness / "
            "AI-attribution-strength) and 4 sufficiency guards.")
    out = ph._strip_internal_ids(text, "PUBLIC")
    assert "SUPPORTED" in out and "PARTIALLY_SUPPORTED" in out
    assert "directness" in out and "AI-attribution-strength" in out
    assert "Evidence Evaluation Contract" not in out
