import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))
import verify_source_candidates as vsc  # noqa: E402


def test_no_fetcher_stays_unverified_never_guesses():
    results = vsc.run(fetcher=None, write_output=False)
    assert len(results) == len(vsc.load_candidates())
    assert all(r["verification_status"] == "UNVERIFIED_PENDING_LIVE_CHECK" for r in results)


def test_fetcher_success_marks_verified():
    def fake_fetcher(url):
        if "digital-strategy.ec.europa.eu" in url and url.endswith("rss.xml"):
            return {"status_code": 200, "final_url": url, "body": "<rss version='2.0'></rss>"}
        return {"status_code": 200, "final_url": url, "body": ""}

    results = vsc.run(fetcher=fake_fetcher, write_output=False)
    eu = next(r for r in results if r["candidate_id"] == "cand_eu_commission_ai")
    assert eu["verification_status"] == "VERIFIED"


def test_fetcher_redirect_to_other_domain_not_verified():
    def fake_fetcher(url):
        if url.endswith("rss.xml"):
            return {"status_code": 200, "final_url": "https://some-random-mirror.example/feed",
                    "body": "<rss></rss>"}
        return {"status_code": 200, "final_url": url, "body": ""}

    results = vsc.run(fetcher=fake_fetcher, write_output=False)
    eu = next(r for r in results if r["candidate_id"] == "cand_eu_commission_ai")
    assert eu["verification_status"] == "VERIFICATION_FAILED"


def test_fetcher_non_xml_body_not_verified():
    def fake_fetcher(url):
        return {"status_code": 200, "final_url": url, "body": "<html>not a feed</html>"}

    results = vsc.run(fetcher=fake_fetcher, write_output=False)
    assert all(r["verification_status"] == "VERIFICATION_FAILED" for r in results)


def test_all_candidates_have_required_fields():
    for c in vsc.load_candidates():
        for field in ("candidate_id", "canonical_name", "official_domain", "source_type",
                      "country", "jurisdiction", "feed_url_candidate", "verification_status"):
            assert field in c, f"{c.get('candidate_id')} missing {field}"
        assert c["verification_status"] == "UNVERIFIED_PENDING_LIVE_CHECK"
