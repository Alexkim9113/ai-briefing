# PRODUCTION EVIDENCE SUPPLY v1.0 — SUBSTEP D verifier (섹션 40-42, 46: 추측 등록 금지,
# 반드시 실제 공식 도메인/Feed 검증). source_pilot_candidates.json의 각 후보를 실제
# 네트워크로 확인하기 위한 코드. 이 세션 환경은 news.google.com뿐 아니라 사실상 모든
# 외부 호스트에 대한 outbound HTTPS를 조직 프록시가 차단한다(curl 실측: whitehouse.gov,
# ec.europa.eu, un.org, congress.gov, courtlistener.com, law.go.kr, gov.kr, kcc.go.kr
# 전부 "CONNECT tunnel failed, response 403") — 그래서 이 스크립트 자체는 fetcher를
# 주입받아야 동작하고, 이 세션 안에서는 검증을 실행할 수 없다(url_resolver.py와 동일한
# 제약/패턴). GitHub Actions 러너(실제 외부 네트워크 접근 가능) 등에서 fetcher를 주입해
# 실행해야 한다.
#
# 검증 절차(fetcher가 있을 때):
#   1) 후보의 official_domain에 실제로 연결되는지(HTTP 200대)
#   2) feed_url_candidate가 실제 RSS/Atom XML을 반환하는지(<rss 또는 <feed 태그 존재)
#   3) 그 피드의 실제 HTTP 응답 도메인이 official_domain과 일치하는지(리다이렉트로 다른
#      도메인으로 새는 경우 자동으로 신뢰하지 않는다)
# 세 가지를 모두 통과해야만 VERIFIED이고, 하나라도 실패/불명확하면 UNVERIFIED로 남긴다
# (추측 승격 금지). VERIFIED가 되어도 이 스크립트는 sources.json을 자동으로 수정하지
# 않는다 — 실제 등록은 사람이 검증 결과를 보고 최종 승인한다(섹션 41: Registry Strict).
import json
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
CANDIDATES_PATH = HERE / "source_pilot_candidates.json"
VERIFICATION_OUTPUT_PATH = HERE / "source_candidate_verification.json"

VERIFICATION_STATUSES = ("VERIFIED", "UNVERIFIED_PENDING_LIVE_CHECK", "VERIFICATION_FAILED")


def _domain_of(url):
    if not url:
        return None
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc[4:] if netloc.startswith("www.") else netloc
    except Exception:
        return None


def load_candidates():
    return json.loads(CANDIDATES_PATH.read_text(encoding="utf-8"))


def verify_candidate(candidate, fetcher):
    """fetcher(url) -> {"status_code": int|None, "final_url": str|None, "body": str|None}.
    fetcher가 None이면 절대 추측하지 않고 현재 상태(UNVERIFIED_PENDING_LIVE_CHECK)를 그대로
    반환한다."""
    result = dict(candidate)
    if fetcher is None:
        result["verification_status"] = "UNVERIFIED_PENDING_LIVE_CHECK"
        return result

    domain_check = None
    try:
        domain_check = fetcher(f"https://{candidate['official_domain']}")
    except Exception:
        domain_check = None
    domain_ok = bool(domain_check and 200 <= (domain_check.get("status_code") or 0) < 400)

    feed_url = candidate.get("feed_url_candidate")
    feed_check = None
    if feed_url:
        try:
            feed_check = fetcher(feed_url)
        except Exception:
            feed_check = None
    feed_ok = False
    feed_domain_matches = False
    if feed_check and 200 <= (feed_check.get("status_code") or 0) < 400:
        body = feed_check.get("body") or ""
        feed_ok = ("<rss" in body.lower()) or ("<feed" in body.lower())
        final_domain = _domain_of(feed_check.get("final_url") or feed_url)
        feed_domain_matches = final_domain == candidate["official_domain"] or (
            final_domain is not None and final_domain.endswith("." + candidate["official_domain"]))

    if domain_ok and feed_ok and feed_domain_matches:
        result["verification_status"] = "VERIFIED"
    elif domain_check is None and feed_check is None:
        result["verification_status"] = "UNVERIFIED_PENDING_LIVE_CHECK"
    else:
        result["verification_status"] = "VERIFICATION_FAILED"
    result["verification_detail"] = {
        "domain_reachable": domain_ok,
        "feed_returns_xml": feed_ok,
        "feed_domain_matches_official_domain": feed_domain_matches,
    }
    assert result["verification_status"] in VERIFICATION_STATUSES
    return result


def run(fetcher=None, write_output=True):
    candidates = load_candidates()
    results = [verify_candidate(c, fetcher) for c in candidates]
    if write_output:
        VERIFICATION_OUTPUT_PATH.write_text(
            json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return results


if __name__ == "__main__":
    # 이 세션 환경에서는 fetcher가 없으므로 모두 UNVERIFIED_PENDING_LIVE_CHECK로만 나온다 —
    # 이것이 정직한 결과다(추측으로 VERIFIED를 만들지 않는다).
    out = run(fetcher=None)
    print(json.dumps(out, ensure_ascii=False, indent=1))
