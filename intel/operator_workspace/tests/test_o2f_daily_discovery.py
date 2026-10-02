# O-2F (scoped) -- Daily Discovery tests. Verifies: items are never fabricated beyond what's in
# the real data/*.json file; nothing is ever written to claims.json; source-tier classification is
# honest; the Operator HTML section escapes hostile input and rejects unsafe URL schemes; and the
# empty state renders correctly.
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import daily_discovery as dd  # noqa: E402
import operator_ui as ou  # noqa: E402

ROOT = HERE.parents[2]
CLAIMS_PATH = ROOT / "intel" / "claims" / "claims.json"


def _claims_hash():
    return hashlib.sha256(CLAIMS_PATH.read_bytes()).hexdigest()


def test_items_never_invent_data_not_in_source():
    """(a) Every returned item's url (and title) must actually appear in the real, latest
    data/*.json file -- nothing fabricated."""
    data_dir = ROOT / "data"
    latest = sorted(data_dir.glob("20*-*-*.json"))[-1]
    raw = json.loads(latest.read_text(encoding="utf-8"))
    by_url = {i.get("link"): i for i in raw["items"] if isinstance(i, dict) and i.get("link")}

    items = dd.daily_discovery_items(data_dir=str(data_dir))
    assert isinstance(items, list)
    for it in items:
        assert it["url"] in by_url
        source_item = by_url[it["url"]]
        assert it["title_ko"] in (source_item.get("title_ko"), source_item.get("title"))
        assert it["url"].startswith("http")


def test_daily_discovery_never_writes_to_claims_json():
    """(b) Calling daily_discovery_items() must never alter claims.json."""
    before = _claims_hash()
    dd.daily_discovery_items(data_dir=str(ROOT / "data"))
    after = _claims_hash()
    assert before == after


def test_source_tier_classification_known_sources():
    """(c) A known government/academic source string classifies Tier 1; an unrecognized outlet
    name classifies Tier 3."""
    assert dd._source_tier("과학기술정보통신부 보도자료") == 1
    assert dd._source_tier("MIT News") == 1
    assert dd._source_tier("arXiv cs.AI") == 1
    assert dd._source_tier("어느 듣보잡 동네 블로그") == 3
    assert dd._source_tier("Some Random Unknown Blog") == 3


def test_source_tier_known_wire_is_tier_2():
    assert dd._source_tier("Reuters") == 2
    assert dd._source_tier("연합뉴스") == 2


def test_html_section_escapes_hostile_title_and_rejects_javascript_url():
    """(d) The rendered section HTML escapes a deliberately hostile title, and _safe_link() never
    turns a javascript: URL into a clickable <a href>."""
    nasty_item = {
        "title_ko": "<script>alert(1)</script>",
        "source": "테스트 소스",
        "date": "2026-10-02",
        "url": "javascript:alert(1)",
        "source_tier": 1,
        "why_it_matters": "Tier 1 출처",
        "related_intelligence": "연관 Intelligence 없음",
        "evidence_status": dd.EVIDENCE_STATUS,
    }
    html_doc = ou._daily_discovery_section_html([nasty_item])
    assert "<script>alert(1)</script>" not in html_doc
    assert "&lt;script&gt;" in html_doc
    assert 'href="javascript:alert(1)"' not in html_doc
    assert "javascript:" not in html_doc or "<a href=" not in html_doc.split("javascript:")[1][:5]


def test_html_section_empty_state():
    """(e) Empty list renders the honest empty-state message, no fabricated cards."""
    html_doc = ou._daily_discovery_section_html([])
    assert "오늘 중요한 Discovery 항목이 확인되지 않았습니다" in html_doc
    assert "kpi-row" not in html_doc


def test_daily_discovery_section_is_first_in_overview():
    html_doc = ou.render_overview()
    idx_discovery = html_doc.find("오늘의 핵심 Discovery")
    idx_change_watch = html_doc.find("오늘의 핵심 신호")
    assert idx_discovery != -1
    assert idx_change_watch != -1
    assert idx_discovery < idx_change_watch
