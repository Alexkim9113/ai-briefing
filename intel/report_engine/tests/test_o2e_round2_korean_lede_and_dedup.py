# O-2E round 2 -- fixes the two remaining Te review items on top of O-4's restructure:
# (1) the PUBLIC lede's opening clause must never be English-leading, and
# (2) the "핵심 신호" section must not render repeated near-identical bullets without dedup/grouping.
# Presentation-layer only: no canonical JSON is touched, no LLM call, deterministic string checks.
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import presentation_model as pm  # noqa: E402
import product_html as ph  # noqa: E402
import report_engine as re_  # noqa: E402

REPORTS_DIR = re_.REPORTS_DIR
_HANGUL_RE = re.compile(r"[가-힣]")
_LATIN_RE = re.compile(r"[A-Za-z]")


def _real_reports():
    return sorted(REPORTS_DIR.glob("report_intel_*_v*.json"))


def _public_html(report_path):
    r = json.loads(report_path.read_text(encoding="utf-8"))
    pub = re_.build_public_view(r)
    presentation = pm.build_presentation(pub)
    return ph.render_product_html(presentation, source_cards=[], view="PUBLIC", real_sources=[])


def test_lede_opening_clause_is_never_english_leading():
    for p in _real_reports():
        html_doc = _public_html(p)
        m = re.search(r'<section class="report-section exec-lede".*?<p>(.*?)</p>', html_doc, re.S)
        assert m, f"no lede found for {p.name}"
        body = re.sub(r"<[^>]+>", "", m.group(1))
        first_clause = re.split(r"(?<=[.!?。])\s+|(?<=[음다]\.)\s+", body.strip())[0]
        hangul = len(_HANGUL_RE.findall(first_clause))
        latin = len(_LATIN_RE.findall(first_clause))
        assert hangul > 0, f"{p.name}: opening clause has no Hangul at all: {first_clause!r}"
        assert hangul >= latin, (
            f"{p.name}: opening clause is Latin/English-leading, not Korean-first: {first_clause!r}"
        )


def test_key_signals_section_has_no_repeated_identical_bullets():
    for p in _real_reports():
        html_doc = _public_html(p)
        m = re.search(r'id="key_signals".*?</section>', html_doc, re.S)
        if not m:
            continue
        # Each top-level <li> under 핵심 신호 must be a distinct line (status+count or distinct
        # text) -- the old behaviour repeated the identical bullet text up to 6 times.
        top_level_lines = re.findall(r"<li>(.*?)(?:<ul>|</li>)", m.group(), re.S)
        cleaned = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", t)).strip() for t in top_level_lines]
        assert len(cleaned) == len(set(cleaned)), (
            f"{p.name}: 핵심 신호 section has duplicate top-level bullets: {cleaned}"
        )


def test_key_signals_dedup_group_shows_count_and_distinct_subjects():
    """For the AI_ENERGY_INFRA v4 report, all 10 KEY_CLAIMS content_blocks render the identical
    generic OPEN placeholder text -- this must collapse to one line with a count, and up to 3
    distinct underlying claim subjects as sub-items, never 10 repeated bullets."""
    target = REPORTS_DIR / "report_intel_87210a61730c22b9_v4.json"
    assert target.exists()
    html_doc = _public_html(target)
    m = re.search(r'id="key_signals".*?</section>', html_doc, re.S)
    assert m
    section = m.group()
    assert "(10건)" in section or re.search(r"\(\d+건\)", section)
    sub_items = re.findall(r"<ul><li>(.*?)</li>", section, re.S)
    assert 1 <= len(sub_items) <= 3


def test_distinct_claim_text_within_a_status_group_is_not_force_collapsed():
    """AI_LABOR v3 has at least one OPEN claim whose rendered text differs from the generic
    placeholder -- it must remain its own separate bullet, not merged away."""
    target = REPORTS_DIR / "report_intel_dbab7b01963396b5_v3.json"
    if not target.exists():
        return
    html_doc = _public_html(target)
    m = re.search(r'id="key_signals".*?</section>', html_doc, re.S)
    assert m
    top_level_lines = re.findall(r"<li>(.*?)(?:<ul>|</li>)", m.group(), re.S)
    cleaned = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", t)).strip() for t in top_level_lines]
    assert len(cleaned) >= 2, "expected more than one distinct 핵심 신호 group/line"
