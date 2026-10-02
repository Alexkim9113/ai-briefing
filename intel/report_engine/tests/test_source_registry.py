# Source Reference retrofit (Te's spec 33A-33I) -- regression tests for source_registry.py and
# its wiring into product_html.render_real_sources / public_delivery.
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import source_registry as sreg  # noqa: E402
import product_html as ph  # noqa: E402
import public_delivery as pd  # noqa: E402
import report_engine as re_  # noqa: E402

FROZEN_V4_HASH = "beb034796e62d93f9a1921c450dca441812fdd56f99fc42eef46c9a2a9ca9420"
V4_PATH = re_.REPORTS_DIR / "report_intel_87210a61730c22b9_v4.json"
V2_PATH = re_.REPORTS_DIR / "report_intel_dbab7b01963396b5_v2.json"

INTERNAL_ID_RE = re.compile(r"\b(?:claim_|hyp_|intel_|evt_)[a-zA-Z0-9_]*")


def test_ai_energy_infra_v4_report_hash_frozen_before_any_render():
    assert hashlib.sha256(V4_PATH.read_bytes()).hexdigest() == FROZEN_V4_HASH


def test_build_sources_for_report_returns_only_real_urls_actually_cited():
    r = json.loads(V4_PATH.read_text(encoding="utf-8"))
    sources = sreg.build_sources_for_report(r)
    # The frozen v4 report's own SOURCE_PROVENANCE.source_ids records exactly 4 real (http) URLs;
    # the rest are internal intel/... and event:/hyp: references, which are Operator-only and must
    # never appear in the reader-facing Sources list.
    assert len(sources) == 4
    urls = {s["url"] for s in sources}
    assert "https://www.iea.org/reports/energy-and-ai/executive-summary" in urls
    assert "https://arxiv.org/html/2411.11540v1" in urls
    for s in sources:
        assert s["url"].startswith("http")
        assert not s["url"].startswith("intel/")
        assert "event:" not in s["url"]


def test_ai_labor_v2_report_sources_match_claims_json_and_flag_exposure_vs_displacement():
    r = json.loads(V2_PATH.read_text(encoding="utf-8"))
    sources = sreg.build_sources_for_report(r)
    assert len(sources) == 8
    by_claim = {s["claim_id"]: s for s in sources if s["claim_id"]}
    # 33E negative control: OECD AI Exposure Measure must never be labeled as a displacement/
    # job-loss finding.
    oecd = by_claim["claim_b9370aa7d219d791"]
    assert "EXPOSURE" in oecd["observation_or_forecast"]
    assert "displacement" not in oecd["observation_or_forecast"].lower() or \
        "not" in oecd["observation_or_forecast"].lower()
    # 33E negative control: KDI is a forecast/prediction, never an observed outcome.
    kdi = by_claim["claim_30fdf98bc1a9c818"]
    assert "FORECAST" in kdi["observation_or_forecast"] or "PREDICTIVE" in kdi["observation_or_forecast"]
    assert kdi["tier"] == "SECONDARY"
    # 33E negative control: NBER w31161 is productivity-only, not employment/headcount evidence.
    nber = by_claim["claim_fe878b52922b46a4"]
    assert "not evidence of employment" in nber["observation_or_forecast"] or \
        "PRODUCTIVITY" in nber["observation_or_forecast"].upper() or \
        "headcount" in nber["observation_or_forecast"].lower()
    # 33E negative control: Stanford SIEPR is scoped to early-career 22-25 workers, never
    # generalized to the whole labor market.
    siepr = by_claim["claim_8fd5da8f27c9fc2b"]
    assert "22-25" in siepr["observation_or_forecast"]
    # Fed FEDS Note is adoption-only.
    fed = by_claim["claim_0da20db21fe1463a"]
    assert "ADOPTION" in fed["observation_or_forecast"]
    # ETLA is counterevidence (no significant effect found), never silently promoted.
    etla = by_claim["claim_8e305d0c30d23514"]
    assert "COUNTEREVIDENCE" in etla["observation_or_forecast"]


def test_render_real_sources_produces_clickable_links_and_no_internal_ids():
    r = json.loads(V2_PATH.read_text(encoding="utf-8"))
    sources = sreg.build_sources_for_report(r)
    html_public = ph.render_real_sources(sources, show_internal_ids=False)
    import html as _html
    for s in sources:
        assert f'<a href="{_html.escape(s["url"])}"' in html_public
    assert INTERNAL_ID_RE.search(html_public) is None
    # Operator view intentionally retains claim ids.
    html_operator = ph.render_real_sources(sources, show_internal_ids=True)
    assert "claim_b9370aa7d219d791" in html_operator


def test_public_html_page_for_both_reports_has_real_sources_section_with_no_internal_ids():
    documents_by_id = re_._load(re_.DOCUMENTS_PATH)
    for path in (V4_PATH, V2_PATH):
        html_doc, _ = pd.render_public_page_for_report(path, documents_by_id)
        assert 'id="sources"' in html_doc
        assert '<a href="http' in html_doc
        sources_section = html_doc.split('id="sources"', 1)[1]
        assert INTERNAL_ID_RE.search(sources_section) is None


def test_ai_energy_infra_v4_report_hash_unchanged_after_full_render_pipeline():
    # Rendering must never mutate the canonical, frozen Report JSON file.
    assert hashlib.sha256(V4_PATH.read_bytes()).hexdigest() == FROZEN_V4_HASH


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
