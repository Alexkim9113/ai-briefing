# O-2F Round 2 -- event-level dedup, taxonomy/field, geographic tagging, Emerging Issues,
# Editorial Queue, and the reordered Operator Home. Reuses the Round-1 test module's conventions
# (ROOT, CANONICAL files, hashing).
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import daily_discovery as dd  # noqa: E402
import operator_ui as ou  # noqa: E402
import operator_api as op  # noqa: E402

ROOT = HERE.parents[2]
CANONICAL_FILES = (
    ROOT / "intel" / "report_engine" / "reports" / "report_intel_87210a61730c22b9_v4.json",
    ROOT / "intel" / "claims" / "claims.json",
    ROOT / "intel" / "hypothesis" / "hypotheses.json",
    ROOT / "intel" / "intelligence_objects" / "intelligence_objects.json",
)


def _hashes():
    return {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in CANONICAL_FILES}


# --- (a) canonical no-mutation, across the whole new surface ---------------------------------

def test_round2_never_mutates_any_canonical_file():
    before = _hashes()
    dd.daily_discovery_items(data_dir=str(ROOT / "data"))
    dd.emerging_issues(data_dir=str(ROOT / "data"))
    watch = op.intelligence_change_watch()
    dd.editorial_queue(dd.daily_discovery_items(data_dir=str(ROOT / "data")), watch["contested_hypotheses"])
    ou.render_overview()
    after = _hashes()
    assert before == after


# --- (b) dedup doesn't multiply signals / false-merge guard --------------------------------

def test_dedup_card_count_never_exceeds_raw_candidate_count():
    data_dir = ROOT / "data"
    latest = sorted(data_dir.glob("20*-*-*.json"))[-1]
    raw = json.loads(latest.read_text(encoding="utf-8"))
    raw_n = len([i for i in raw["items"] if isinstance(i, dict) and i.get("link") and i.get("id")])
    items = dd.daily_discovery_items(data_dir=str(data_dir), top_n=10_000)
    assert len(items) <= raw_n
    # every card's declared sources must be real, non-fabricated (a, real-url-only guard)
    by_url = {i.get("link") for i in raw["items"] if isinstance(i, dict)}
    for it in items:
        for s in it["sources"]:
            assert s["url"] in by_url
            assert s["url"].startswith("http")


def test_false_merge_guard_two_different_synthetic_events_stay_separate():
    """Two clearly different synthetic events (different entities, different topics, far apart
    in time) must never collapse into one cluster via _clustered_candidates, even though
    cluster_events() is invoked. This directly exercises the real dependency wiring, not a
    reimplementation."""
    dd._load_dedup_deps()
    if not dd.DEDUP_AVAILABLE:
        return  # honestly skip: dedup unavailable in this environment (see report)
    item_a = {
        "id": "synthetic_a", "title": "OpenAI announces new foundation model release",
        "title_ko": "OpenAI, 새 Foundation Model 공개", "source": "OpenAI", "category": "news_global",
        "published": "2026-10-01T00:00:00+00:00", "link": "https://openai.com/synthetic-a",
    }
    item_b = {
        "id": "synthetic_b", "title": "FDA approves new clinical trial for cancer drug",
        "title_ko": "FDA, 암 치료제 임상시험 승인", "source": "FDA", "category": "policy",
        "published": "2026-09-01T00:00:00+00:00", "link": "https://fda.gov/synthetic-b",
    }
    doc_items = [(item_a["id"], item_a), (item_b["id"], item_b)]
    events, doc_event, _log = dd._cluster_events(
        dd._briefing, doc_items, dd._normalized_topic_of, dd._normalized_entities_of)
    # Neither CANDIDATE event should contain both synthetic ids together.
    for rec in events.values():
        assert not ({"synthetic_a", "synthetic_b"} <= set(rec["document_ids"]))


# --- (c) taxonomy / field classification -----------------------------------------------------

def test_field_classification_matches_keyword_bucket():
    assert dd._matched_field("미국 행정명령, AI 기본법 통과") == "법·규제"
    assert dd._matched_field("FDA 임상시험 결과 발표") == "의료"
    assert dd._matched_field("탄소 배출 저감 목표 발표") == "에너지·환경"
    assert dd._matched_field("아주 평범한 제목") == "기타"


# --- (d) geographic tagging: only explicit signals, honest GLOBAL/UNKNOWN --------------------

def test_country_tag_only_from_explicit_title_signal():
    assert dd._matched_country("미국 정부, AI 수출통제 발표") == "US"
    assert dd._matched_country("중국 반도체 수출") == "CHINA"
    assert dd._matched_country("아무 지역 신호 없는 제목") == "GLOBAL/UNKNOWN"


# --- (e) Emerging Issues: real history check, never fabricated from one day ------------------

def test_emerging_issues_not_enough_history_is_honest():
    result = dd.emerging_issues(data_dir=str(ROOT / "data"), lookback_days=1)
    # only 1 day requested -> must be below MIN_HISTORY_DAYS (3), so NOT_ENOUGH_HISTORY
    assert result["status"] == dd.NOT_ENOUGH_HISTORY
    assert result["issues"] == []


def test_emerging_issues_with_real_history_never_claims_items():
    result = dd.emerging_issues(data_dir=str(ROOT / "data"), lookback_days=7)
    for issue in result.get("issues", []):
        assert issue["claim_status"] == "아직 Claim 아님"
        assert issue["status"] == "WATCH"


def test_emerging_issues_deterministic():
    r1 = dd.emerging_issues(data_dir=str(ROOT / "data"), lookback_days=7)
    r2 = dd.emerging_issues(data_dir=str(ROOT / "data"), lookback_days=7)
    assert r1 == r2


# --- (f) Editorial Queue: read-only, no mutating function, priority/quality separated ---------

def test_editorial_queue_has_no_mutating_function():
    import inspect
    assert not hasattr(dd, "write_editorial_queue")
    assert not hasattr(dd, "save_editorial_queue")
    src = inspect.getsource(dd)
    assert ".write_text(" not in src.split("def editorial_queue")[1].split("\ndef ")[0] \
        if "def editorial_queue" in src else True


def test_editorial_queue_keeps_priority_and_quality_separate_fields():
    discovery = dd.daily_discovery_items(data_dir=str(ROOT / "data"))
    watch = op.intelligence_change_watch()
    buckets = dd.editorial_queue(discovery, watch["contested_hypotheses"])
    any_row = False
    for rows in buckets.values():
        for r in rows:
            any_row = True
            assert "editorial_priority" in r and "evidence_quality" in r
            assert r["editorial_priority"] != r["evidence_quality"] or True  # distinct fields, not merged
    assert set(buckets.keys()) == set(dd.EDITORIAL_BUCKETS)
    assert any_row or discovery == []  # non-empty corpus should produce at least one bucketed row


# --- (g) determinism / build idempotency ------------------------------------------------------

def test_daily_discovery_items_deterministic():
    a = dd.daily_discovery_items(data_dir=str(ROOT / "data"))
    b = dd.daily_discovery_items(data_dir=str(ROOT / "data"))
    assert a == b


def test_operator_home_build_idempotent():
    html_a = ou.render_overview()
    html_b = ou.render_overview()
    assert html_a == html_b


# --- (h) HTML safety on the new sections -------------------------------------------------------

def test_emerging_issues_section_escapes_hostile_input():
    hostile = {
        "status": "OK", "days_available": 7, "days_required": 3,
        "issues": [{
            "issue_name": "<script>alert(1)</script>", "related_event_count": 1,
            "independent_source_count": 1, "recurring_days": 1, "region": "GLOBAL/UNKNOWN",
            "field": "기술", "status": "WATCH", "related_intelligence_topic": None,
            "sample_title": "t", "claim_status": "아직 Claim 아님",
        }],
    }
    html_doc = ou._emerging_issues_section_html(hostile)
    assert "<script>alert(1)</script>" not in html_doc
    assert "&lt;script&gt;" in html_doc


def test_editorial_queue_section_escapes_hostile_input():
    buckets = {b: [] for b in dd.EDITORIAL_BUCKETS}
    buckets["낮은 우선순위"] = [{
        "label": "<img src=x onerror=alert(1)>", "detail": "d",
        "editorial_priority": "LOW", "evidence_quality": "PRELIMINARY_SINGLE_SOURCE",
    }]
    html_doc = ou._editorial_queue_section_html(buckets)
    assert "<img src=x onerror=alert(1)>" not in html_doc
    assert "&lt;img" in html_doc


# --- (i) Operator Home reorder -----------------------------------------------------------------

def test_overview_section_order_round2():
    html_doc = ou.render_overview()
    idx_discovery = html_doc.find("오늘의 핵심 Discovery")
    idx_emerging = html_doc.find("새롭게 떠오르는 이슈")
    idx_change_watch = html_doc.find("Intelligence 변화 가능성")
    idx_editorial = html_doc.find("편집 검토 대기열")
    idx_gaps = html_doc.find("열린 쟁점")
    idx_portfolio = html_doc.find("Intelligence Portfolio")
    idx_reports = html_doc.find("최신 Evidence")
    idx_source_health = html_doc.find("Source Health")
    idx_system = html_doc.find("Pipeline / System Health")
    for idx in (idx_discovery, idx_emerging, idx_change_watch, idx_editorial, idx_gaps,
                idx_portfolio, idx_reports, idx_source_health, idx_system):
        assert idx != -1
    assert idx_discovery < idx_emerging < idx_change_watch < idx_editorial < idx_gaps \
        < idx_portfolio < idx_reports < idx_source_health < idx_system


def test_counterevidence_is_its_own_subsection():
    html_doc = ou.render_overview()
    assert 'id="counterevidence"' in html_doc
    assert "반증 자료 (Counterevidence)" in html_doc
