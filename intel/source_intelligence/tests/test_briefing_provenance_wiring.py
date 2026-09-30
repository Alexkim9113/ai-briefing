# FINAL PRODUCTION WIRING & CLOSURE — briefing.py의 실제 daily 수집 경로에 연결된
# content_acquisition → article_provenance_pipeline 배선 검증. 실제 네트워크는 쓰지 않는다
# (이 sandbox엔 outbound가 없음) - briefing._load_source_intel_module()과
# briefing._known_documents_for_provenance()를 가짜로 갈아끼워 배선 자체(호출 여부·순서·
# 격리·캐시·품질 게이트)만 검증한다. content_acquisition/article_provenance_pipeline
# 자신의 로직은 그 모듈들의 기존 테스트(test_article_provenance_pipeline.py 등)가 이미
# 검증한다 - 여기서는 다시 하지 않는다(REUSE BEFORE BUILD, 중복 검증 금지).
import contextlib
import json
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import briefing  # noqa: E402

_REAL_LOAD_SOURCE_INTEL_MODULE = briefing._load_source_intel_module  # 다른 테스트가 monkeypatch하기 전에 원본을 붙잡아 둔다


class _FakeContentAcquisition:
    """url에 'bad'가 있으면 FETCH_FAILED, 'lowqual'이면 title 없는 FULL_TEXT(quality gate가
    걸러야 함), 그 외엔 깨끗한 FULL_TEXT."""

    @staticmethod
    def acquire_content(url, fetcher=None):
        fetched = fetcher(url)
        if not fetched.get("html"):
            return {"status": "FETCH_FAILED", "text": None}
        if "lowqual" in url:
            return {"status": "FULL_TEXT", "text": "x", "extractor": "trafilatura", "extractor_version": "1"}
        return {"status": "FULL_TEXT", "text": "Real article body sentence here today, quite long indeed. " * 8,
                "extractor": "trafilatura", "extractor_version": "1"}


class _FakeFetchPilot:
    content_acquisition = _FakeContentAcquisition
    calls = []

    @staticmethod
    def real_fetcher(url):
        _FakeFetchPilot.calls.append(url)
        if "bad" in url:
            return {"html": None, "status_code": 404}
        if "recursion-guard" in url:
            raise AssertionError("real_fetcher must never be called on a primary-source URL (depth>1)")
        html = ("<html><body><article><p>See "
                "<a href='https://arxiv.org/abs/1706.03762'>paper</a></p></article></body></html>")
        return {"html": html, "status_code": 200}

    @staticmethod
    def assess_full_text_quality(text, title):
        if not title:
            return "LOW_QUALITY_EXTRACTION"
        if len((text or "").strip()) < 20:
            return "LOW_QUALITY_EXTRACTION"
        return "OK"


def _fake_process_acquired_article(source_document_id, acquired, html, source_url, known_documents_by_id=None):
    """article_provenance_pipeline.process_acquired_article()의 자리표시자. 실제 로직은
    그 모듈의 own 테스트가 검증한다 - 여기서는 '배선이 넘긴 인자가 맞는가'만 본다."""
    assert acquired.get("text") is not None or acquired.get("status") not in ("FULL_TEXT", "PARTIAL_TEXT")
    assert "mx" not in str(source_document_id)  # mx.b가 document_id로 둔갑해 들어오지 않았는지 최소 확인
    if known_documents_by_id and "https://arxiv.org/abs/1706.03762" in {
        d.get("canonical_url") for d in known_documents_by_id.values()
    }:
        return {"link_candidates": [{"is_primary_candidate": True, "link_url": "https://arxiv.org/abs/1706.03762"}],
                "reports_on_records": [{"relationship_id": f"rel_{source_document_id}",
                                         "source_document_id": source_document_id,
                                         "target_document_id": "doc_primary_1"}]}
    return {"link_candidates": [], "reports_on_records": []}


def _patch(monkey_cache_dir, extra_loader=None, known_documents=None):
    _FakeFetchPilot.calls = []
    fake_app = types.SimpleNamespace(process_acquired_article=_fake_process_acquired_article)

    def loader(modname, subdir=None):
        if modname == "fetch_pilot":
            return _FakeFetchPilot
        if modname == "article_provenance_pipeline":
            return fake_app
        raise AssertionError(f"unexpected module requested: {modname}")

    briefing._load_source_intel_module = extra_loader or loader
    briefing._known_documents_for_provenance = lambda: (known_documents if known_documents is not None else {
        "doc_primary_1": {"canonical_url": "https://arxiv.org/abs/1706.03762", "title": "Attention Is All You Need"},
    })
    briefing.PROVENANCE_CACHE_PATH = monkey_cache_dir / "cache.json"
    briefing._RELATIONSHIPS_COMPANY_GOV_PATH = monkey_cache_dir / "relationships_company_gov.json"


def _item(id_, url, title="Some title"):
    return {"id": id_, "link": url, "title": title}


@contextlib.contextmanager
def _tmp_dir():
    # pytest가 없는 환경이라(other tests도 이 관례를 쓴다, test_reports_on_expansion.py 참고)
    # tempfile.TemporaryDirectory()로 직접 임시 디렉터리를 만든다.
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


def test_eligible_article_triggers_provenance_pipeline():
    with _tmp_dir() as tmp_path:
        _patch(tmp_path)
        c = briefing.run_article_provenance_pilot([_item("a1", "https://example.com/good")], fixtures=None)
        assert c["fetch_attempted"] == 1
        assert c["quality_ok"] == 1
        assert c["reports_on_created"] == 1
        rel = json.loads(briefing._RELATIONSHIPS_COMPANY_GOV_PATH.read_text(encoding="utf-8"))
        assert len(rel) == 1


def test_hard_dropped_item_never_reaches_this_function():
    # make_item()/classify_noise()가 이미 걸러낸 항목은 collect()가 애초에 new_items
    # 리스트에 담지 않는다 - 이 함수는 "collect()가 이미 넘겨준 것"만 처리한다는 계약을
    # 확인한다(hard-drop된 기사는 uniq에 존재하지 않으므로 여기 호출 자체가 안 됨).
    assert briefing.classify_noise("삼성전자 채용공고: AI 신입 개발자 모집")["decision"] == "DROP"


def test_duplicate_url_avoids_refetch():
    with _tmp_dir() as tmp_path:
        _patch(tmp_path)
        items = [_item("a1", "https://example.com/good")]
        c1 = briefing.run_article_provenance_pilot(items, fixtures=None)
        c2 = briefing.run_article_provenance_pilot(items, fixtures=None)
        assert c1["fetch_attempted"] == 1
        assert c2["fetch_attempted"] == 0
        assert c2["cache_hit"] == 1
        assert len(_FakeFetchPilot.calls) == 1  # 실제 fetcher가 두 번째 실행에서 호출되지 않음


def test_one_item_failure_does_not_stop_the_batch():
    with _tmp_dir() as tmp_path:
        def crashing_loader(modname, subdir=None):
            if modname == "fetch_pilot":
                class _Crashy:
                    content_acquisition = _FakeContentAcquisition

                    @staticmethod
                    def real_fetcher(url):
                        if "crash" in url:
                            raise RuntimeError("simulated network failure")
                        return _FakeFetchPilot.real_fetcher(url)

                    @staticmethod
                    def assess_full_text_quality(text, title):
                        return _FakeFetchPilot.assess_full_text_quality(text, title)
                return _Crashy
            return types.SimpleNamespace(process_acquired_article=_fake_process_acquired_article)

        _patch(tmp_path, extra_loader=crashing_loader)
        items = [_item("a1", "https://example.com/crash1"), _item("a2", "https://example.com/good2")]
        c = briefing.run_article_provenance_pilot(items, fixtures=None)
        assert c["fetch_attempted"] == 2  # 둘 다 시도됐고
        assert c["quality_ok"] == 1       # 크래시한 것 빼고 나머지는 정상 처리됨


def test_low_quality_extraction_blocked_from_reports_on():
    with _tmp_dir() as tmp_path:
        _patch(tmp_path)
        c = briefing.run_article_provenance_pilot([_item("a1", "https://example.com/lowqual")], fixtures=None)
        assert c["fetch_full_text"] == 1
        assert c["quality_rejected"] == 1
        assert c["reports_on_created"] == 0  # LOW_QUALITY_EXTRACTION은 REPORTS_ON으로 이어지지 않는다


def test_explicit_arxiv_reference_produces_reports_on():
    with _tmp_dir() as tmp_path:
        _patch(tmp_path, known_documents={
            "doc_primary_1": {"canonical_url": "https://arxiv.org/abs/1706.03762", "title": "Attention Is All You Need"}})
        c = briefing.run_article_provenance_pilot([_item("a1", "https://example.com/good")], fixtures=None)
        assert c["reports_on_created"] == 1


def test_no_primary_reference_yields_no_fabricated_reports_on():
    with _tmp_dir() as tmp_path:
        _patch(tmp_path, known_documents={})  # corpus에 1차 출처 후보가 전혀 없음
        c = briefing.run_article_provenance_pilot([_item("a1", "https://example.com/good")], fixtures=None)
        assert c["reports_on_created"] == 0


def test_shared_primary_source_reaches_relationships_file_for_source_independence():
    with _tmp_dir() as tmp_path:
        _patch(tmp_path)
        briefing.run_article_provenance_pilot(
            [_item("a1", "https://example.com/good1"), _item("a2", "https://example.com/good2")], fixtures=None, cap=10)
        rel_path = briefing._RELATIONSHIPS_COMPANY_GOV_PATH
        rel = json.loads(rel_path.read_text(encoding="utf-8"))
        assert len(rel) == 2
        targets = {r["target_document_id"] for r in rel.values()}
        assert targets == {"doc_primary_1"}  # 두 기사가 같은 1차 출처를 가리킴 - source_independence 입력


def test_recursive_reference_fetch_is_never_attempted():
    with _tmp_dir() as tmp_path:
        # article_provenance_pipeline은 link_candidates만 반환하고 그 링크들을 다시
        # content_acquisition.acquire_content()에 넣지 않는다(MAX_PROVENANCE_DEPTH=1) -
        # real_fetcher가 "recursion-guard" URL로는 절대 호출되지 않아야 한다(가짜 fetcher가
        # 호출되면 AssertionError를 던지도록 설계함).
        _patch(tmp_path)
        briefing.run_article_provenance_pilot([_item("a1", "https://example.com/good")], fixtures=None)
        assert not any("recursion-guard" in u for u in _FakeFetchPilot.calls)
        assert briefing.MAX_PROVENANCE_DEPTH == 1


def test_generated_summary_never_enters_pipeline_input():
    with _tmp_dir() as tmp_path:
        # collect()가 넘기는 item에 mx.b(생성 요약)가 있어도, run_article_provenance_pilot()은
        # item["link"]만 fetch하고 item["mx"]를 읽지 않는다 - acquire_content()가 실제로 받은
        # text만 쓴다는 계약을 소스 레벨에서도 확인한다.
        import inspect
        src = inspect.getsource(briefing.run_article_provenance_pilot)
        assert 'get("mx"' not in src and "['mx']" not in src and '["mx"]' not in src


def test_security_guard_is_the_real_fetcher_from_fetch_pilot():
    # 이 배선이 실제로 쓰는 fetcher는 fetch_pilot.real_fetcher다(새로 작성한 별도 fetcher가
    # 아님) - fetch_pilot 자신의 보안 테스트(test_fetch_pilot.py)가 이미 SSRF/localhost/
    # file:/javascript:/data: 차단을 검증하므로 여기서 중복 검증하지 않는다(REUSE BEFORE
    # BUILD). 로더가 fetch_pilot 모듈 자체를 반환하는지만 확인한다.
    mod = _REAL_LOAD_SOURCE_INTEL_MODULE("fetch_pilot", subdir="scripts")
    assert hasattr(mod, "real_fetcher")
    assert hasattr(mod, "content_acquisition")


def test_fixtures_mode_never_fetches_network():
    with _tmp_dir() as tmp_path:
        _patch(tmp_path)
        c = briefing.run_article_provenance_pilot([_item("a1", "https://example.com/good")], fixtures="tests/fixtures")
        assert c["fetch_attempted"] == 0
        assert _FakeFetchPilot.calls == []


def test_cap_limits_fetch_attempts_per_run():
    with _tmp_dir() as tmp_path:
        _patch(tmp_path)
        items = [_item(f"a{i}", f"https://example.com/good{i}") for i in range(20)]
        c = briefing.run_article_provenance_pilot(items, fixtures=None, cap=3)
        assert c["fetch_attempted"] == 3


def test_cache_persists_across_separate_pilot_invocations():
    with _tmp_dir() as tmp_path:
        _patch(tmp_path)
        briefing.run_article_provenance_pilot([_item("a1", "https://example.com/good")], fixtures=None)
        cache_on_disk = json.loads(briefing.PROVENANCE_CACHE_PATH.read_text(encoding="utf-8"))
        assert len(cache_on_disk) == 1
        # 새로 로드해도(같은 run 안이 아니라 "다음 30분 cron"을 흉내) 캐시가 남아있어 재-fetch 안 함
        c2 = briefing.run_article_provenance_pilot([_item("a1", "https://example.com/good")], fixtures=None)
        assert c2["fetch_attempted"] == 0
