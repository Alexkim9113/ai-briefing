# SOURCE 정규화. sources.json(수집 설정, 138개)과 실제 기사에 찍힌 item["source"] 문자열을
# canonical_name + domain 기준으로 하나로 합친다. 기존 JSON의 source 필드는 절대 바꾸지 않고,
# 그 문자열을 source_id로 매핑하는 별도 표만 만든다.
import json
import re
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _slug(s):
    s = re.sub(r"[^0-9a-z가-힣]+", "_", s.lower()).strip("_")
    return s or "unknown"


# 한 도메인 밑에 서로 다른 발행 주체가 여럿 있는 "다세입자" 도메인: 도메인만으로 합치면
# 안 된다(예: YouTube 채널마다 다른 발행자, arXiv/Nature는 학술지 섹션마다 다른 피드).
# 파일럿 1차 실행에서 이 목록이 없어 TEDx/Lex Fridman/a16z 등 12개 유튜브 채널과
# arXiv 9개 분야, Nature 4개 분야가 서로 다른 채널·분야인데도 하나의 SOURCE로 잘못 합쳐졌다(발견한 문제, 보고서 참고).
MULTI_TENANT_DOMAINS = {"youtube.com", "rss.arxiv.org", "arxiv.org", "nature.com", "huggingface.co"}


def _domain_from_url(url):
    """구글 뉴스 검색 URL이면 q= 안의 site:도메인을, 일반 RSS면 그 서버의 도메인을 뽑는다."""
    if "news.google." in url:
        m = re.search(r"site[:%]3?a?[:]?([a-z0-9.\-]+\.[a-z]{2,})", urllib.parse.unquote(url), re.I)
        return m.group(1).lower() if m else None
    try:
        return urllib.parse.urlsplit(url).netloc.lower().removeprefix("www.") or None
    except Exception:
        return None


def load_source_configs(sources_path=None):
    """sources.json에서 (표시 이름, 도메인) 후보를 모은다. 구글 뉴스 키워드 검색(outlet 없음)은
    여러 언론사를 섞어 오므로 여기서는 canonical source로 보지 않는다."""
    cfg = json.loads((sources_path or ROOT / "sources.json").read_text(encoding="utf-8"))
    out = []
    for s in cfg.get("sources", []):
        name = s.get("outlet") or s.get("name")
        if s.get("outlet") is None and "news.google." in s.get("url", ""):
            continue  # 예: "구글뉴스: 인공지능" 같은 키워드 검색은 출처가 아니라 수집 레인
        out.append({"name": name, "domain": _domain_from_url(s.get("url", "")), "config_name": s.get("name")})
    return out


def normalize_sources(item_source_names, sources_path=None):
    """item['source'] 문자열들(실제 관측치) + sources.json 설정을 합쳐 SOURCE 레코드를 만든다.
    반환: (records: {source_id: record}, alias_report: [{alias, source_id, reason}])"""
    configs = load_source_configs(sources_path)
    by_domain, by_name = {}, {}
    records = {}
    alias_report = []

    def get_or_create(name, domain):
        multi_tenant = domain in MULTI_TENANT_DOMAINS
        sid = by_domain.get(domain) if (domain and not multi_tenant) else None
        if sid is None:
            sid = by_name.get(_slug(name))
        if sid is None:
            sid = f"src_{_slug(domain if domain else name)}"
            if multi_tenant:  # 도메인이 같아도 서로 다른 발행자이므로 이름까지 넣어 구분한다
                sid = f"src_{_slug(domain)}_{_slug(name)}"
            records[sid] = {"source_id": sid, "canonical_name": name, "aliases": [],
                             "domain": domain, "source_type": "rss", "country": None, "language": None}
            if domain and not multi_tenant:
                by_domain[domain] = sid
            by_name[_slug(name)] = sid
        else:
            rec = records[sid]
            if name != rec["canonical_name"] and name not in rec["aliases"]:
                rec["aliases"].append(name)
                alias_report.append({"alias": name, "source_id": sid, "canonical_name": rec["canonical_name"],
                                      "reason": "same domain" if domain else "same normalized name"})
            if domain and not rec["domain"]:
                rec["domain"] = domain
                if not multi_tenant:
                    by_domain[domain] = sid
        return sid

    for c in configs:
        if c["name"]:
            get_or_create(c["name"], c["domain"])
    for name in sorted(set(n for n in item_source_names if n)):
        get_or_create(name, None)
    return records, alias_report
