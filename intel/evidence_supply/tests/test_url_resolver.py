import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))
import url_resolver as ur  # noqa: E402


def _clear_cache():
    if ur.REDIRECT_CACHE_PATH.exists():
        ur.REDIRECT_CACHE_PATH.unlink()


def test_is_google_news_redirect():
    assert ur.is_google_news_redirect("https://news.google.com/rss/articles/CBMiXYZ")
    assert not ur.is_google_news_redirect("https://www.reuters.com/technology/abc")
    assert not ur.is_google_news_redirect("")
    assert not ur.is_google_news_redirect(None)


def test_no_fetcher_means_unresolved_never_guessed():
    _clear_cache()
    r = ur.resolve_google_news_url("https://news.google.com/rss/articles/CBMiTEST1", fetcher=None, use_cache=False)
    assert r["resolution_status"] == "UNRESOLVED"
    assert r["resolved_url"] is None
    assert r["resolution_method"] is None


def test_fetcher_http_redirect_resolves():
    _clear_cache()

    def fake_fetcher(url):
        return {"final_url": "https://www.reuters.com/technology/real-article", "html": None}

    r = ur.resolve_google_news_url("https://news.google.com/rss/articles/CBMiTEST2", fetcher=fake_fetcher, use_cache=False)
    assert r["resolution_status"] == "RESOLVED"
    assert r["resolution_method"] == "HTTP_REDIRECT"
    assert r["resolved_domain"] == "reuters.com"
    assert r["discovery_source"] == "GOOGLE_NEWS"


def test_fetcher_returning_another_google_news_url_stays_unresolved():
    _clear_cache()

    def fake_fetcher(url):
        return {"final_url": "https://news.google.com/rss/articles/CBMiOther", "html": None}

    r = ur.resolve_google_news_url("https://news.google.com/rss/articles/CBMiTEST3", fetcher=fake_fetcher, use_cache=False)
    assert r["resolution_status"] == "UNRESOLVED"


def test_canonical_link_fallback():
    _clear_cache()

    def fake_fetcher(url):
        return {"final_url": None, "html": '<html><head><link rel="canonical" href="https://techcrunch.com/2026/09/28/thing"></head></html>'}

    r = ur.resolve_google_news_url("https://news.google.com/rss/articles/CBMiTEST4", fetcher=fake_fetcher, use_cache=False)
    assert r["resolution_status"] == "RESOLVED"
    assert r["resolution_method"] == "CANONICAL_LINK"
    assert r["resolved_domain"] == "techcrunch.com"


def test_cache_prevents_second_fetch():
    _clear_cache()
    calls = {"n": 0}

    def fake_fetcher(url):
        calls["n"] += 1
        return {"final_url": "https://www.bbc.com/news/tech-1", "html": None}

    url = "https://news.google.com/rss/articles/CBMiTEST5"
    r1 = ur.resolve_google_news_url(url, fetcher=fake_fetcher, use_cache=True)
    r2 = ur.resolve_google_news_url(url, fetcher=fake_fetcher, use_cache=True)
    assert calls["n"] == 1
    assert r1 == r2
    _clear_cache()


def test_redirect_url_hash_stable():
    h1 = ur.redirect_url_hash("https://news.google.com/rss/articles/CBMiABC")
    h2 = ur.redirect_url_hash("https://news.google.com/rss/articles/CBMiABC")
    assert h1 == h2
    assert h1 != ur.redirect_url_hash("https://news.google.com/rss/articles/CBMiXYZ")


def test_item_provided_resolved_url_used_without_fetch():
    _clear_cache()
    calls = {"n": 0}

    def fake_fetcher(url):
        calls["n"] += 1
        return {"final_url": "https://should-not-be-used.example", "html": None}

    item = {"resolved_url": "https://apnews.com/article/real"}
    r = ur.resolve_google_news_url("https://news.google.com/rss/articles/CBMiTEST6", item=item, fetcher=fake_fetcher, use_cache=False)
    assert calls["n"] == 0
    assert r["resolution_method"] == "REDIRECT_METADATA"
    assert r["resolved_domain"] == "apnews.com"
