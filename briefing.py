#!/usr/bin/env python3
"""METAXIS 매일 AI 브리핑: RSS/Atom/JSON 소스를 모아 정적 사이트(site/)를 만든다.

외부 라이브러리 없이 파이썬 표준 라이브러리만 사용한다.
저작권 보호를 위해 원문 전체는 저장하지 않고, 제목 + 짧은 자동 발췌 요약 + 원문 링크만 남긴다.

사용법:
  python briefing.py            # 수집 + 사이트 생성
  python briefing.py build      # 저장된 데이터로 사이트만 다시 생성
  python briefing.py collect --fixtures tests/fixtures   # 네트워크 대신 로컬 파일로 수집(테스트용)
"""
import argparse
import concurrent.futures
import email.utils
import hashlib
import html
import json
import re
import sys
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
SITE_DIR = ROOT / "site"
KST = timezone(timedelta(hours=9))

SUMMARY_CHARS = 180        # 발췌 요약 최대 길이(저작권상 짧게 유지)
DEFAULT_LIMIT = 8          # 소스별 최대 항목 수
FRESH_HOURS = 36           # 이 시간 안에 발행된 글만 오늘 브리핑에 포함
MAX_PER_CAT = 60          # 분야별 하루 최대 항목 수
DEDUPE_DAYS = 7            # 최근 N일 브리핑에 이미 나온 글은 제외
DUP_SIMILARITY = 0.4       # 같은 카테고리에서 제목 글자쌍이 이만큼 겹치면 같은 글로 본다
DUP_SIMILARITY_KO = 0.33   # 한글 제목은 언론사마다 표현이 더 달라 기준을 조금 낮춘다
USER_AGENT = "Mozilla/5.0 (compatible; AI-Briefing-Bot/1.0; +https://github.com)"


# ---------------------------------------------------------------- 수집

def fetch(url, fixtures=None, ua=None):
    if fixtures:
        name = hashlib.sha1(url.encode()).hexdigest()[:12]
        for ext in (".xml", ".json"):
            p = Path(fixtures) / (name + ext)
            if p.exists():
                return p.read_bytes()
        raise FileNotFoundError(f"fixture {name} 없음")
    req = urllib.request.Request(url, headers={"User-Agent": ua or USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()


def local(tag):
    return tag.rsplit("}", 1)[-1].lower()


def child(el, *names):
    for c in el:
        if local(c.tag) in names:
            return c
    return None


def text_of(el, *names):
    c = child(el, *names)
    return (c.text or "").strip() if c is not None else ""


_XML_ENTITY_FIX = re.compile(r"&(?!(?:[a-zA-Z]+|#\d+|#x[0-9a-fA-F]+);)")


def parse_xml(raw):
    try:
        return ET.fromstring(raw)
    except ET.ParseError:
        s = raw.decode("utf-8", errors="replace")
        s = _XML_ENTITY_FIX.sub("&amp;", s)
        for ent, rep in (("&nbsp;", "&#160;"), ("&middot;", "&#183;"), ("&hellip;", "&#8230;"),
                         ("&lsquo;", "&#8216;"), ("&rsquo;", "&#8217;"), ("&ldquo;", "&#8220;"),
                         ("&rdquo;", "&#8221;"), ("&ndash;", "&#8211;"), ("&mdash;", "&#8212;")):
            s = s.replace(ent, rep)
        s = re.sub(r"^<\?xml[^>]*\?>", "", s.lstrip())
        return ET.fromstring(s)


def parse_date(s, tz_hours=0):
    """발행 시각. 시간대 표기가 없으면 소스의 기본 시간대(tz_hours, 예: 한국 9)로 본다."""
    if not s:
        return None
    s = s.strip()
    try:
        d = email.utils.parsedate_to_datetime(s)
    except (TypeError, ValueError):
        d = None
    if d is None:
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone(timedelta(hours=tz_hours)))
    return d


def _rx(block, *names):
    for n in names:
        m = re.search(rf"<(?:\w+:)?{n}\b[^>]*>(.*?)</(?:\w+:)?{n}>", block, re.S | re.I)
        if m:
            v = m.group(1).strip()
            return v[9:-3].strip() if v.startswith("<![CDATA[") and v.endswith("]]>") else v
    return ""


def parse_feed_loose(raw):
    """XML 문법이 깨진 피드용 예비 파서: <item>/<entry> 블록에서 필요한 값만 정규식으로 뽑는다."""
    s = raw.decode("utf-8", errors="replace")
    items = []
    for m in re.finditer(r"<(item|entry)\b[^>]*>(.*?)</\1>", s, re.S | re.I):
        b = m.group(2)
        link = _rx(b, "link")
        if not link:
            h = re.search(r"<link\b[^>]*href=[\"']([^\"']+)", b, re.I)
            link = h.group(1) if h else _rx(b, "guid")
        items.append({"title": html.unescape(_rx(b, "title")), "link": html.unescape(link),
                      "desc": html.unescape(_rx(b, "description", "summary", "encoded", "content")),
                      "date": _rx(b, "pubDate", "date", "published", "updated"), "thumb": ""})
    return items


def parse_feed(raw):
    """RSS 2.0 / RSS 1.0(RDF) / Atom 을 공통 형식으로 변환."""
    try:
        root = parse_xml(raw)
    except ET.ParseError:
        return parse_feed_loose(raw)
    items = []
    if local(root.tag) == "feed":  # Atom
        for e in root:
            if local(e.tag) != "entry":
                continue
            link = ""
            for l in e:
                if local(l.tag) == "link" and l.get("rel", "alternate") == "alternate":
                    link = l.get("href", "")
                    break
            desc = text_of(e, "summary") or text_of(e, "content")
            group = child(e, "group")  # YouTube media:group
            if group is not None:
                desc = desc or text_of(group, "description")
            items.append({"title": text_of(e, "title"), "link": link, "desc": desc,
                          "date": text_of(e, "published", "updated"), "thumb": ""})
    else:  # RSS 2.0 / RDF
        nodes = root.iter()
        for e in nodes:
            if local(e.tag) != "item":
                continue
            link = text_of(e, "link") or (child(e, "guid").text if child(e, "guid") is not None else "")
            desc = text_of(e, "description", "encoded", "summary")
            items.append({"title": text_of(e, "title"), "link": (link or "").strip(), "desc": desc,
                          "date": text_of(e, "pubdate", "date", "published", "updated"), "thumb": ""})
    return items


def parse_hf_papers(raw):
    items = []
    for row in json.loads(raw):
        p = row.get("paper", row)
        pid = p.get("id", "")
        items.append({"title": p.get("title", ""), "link": f"https://huggingface.co/papers/{pid}",
                      "desc": p.get("summary", ""), "date": row.get("publishedAt") or p.get("publishedAt", ""),
                      "thumb": "", "score": p.get("upvotes", 0)})
    items.sort(key=lambda x: -x.get("score", 0))
    return items


def parse_europepmc(raw):
    items = []
    for r in json.loads(raw).get("resultList", {}).get("result", []):
        if r.get("pmid"):
            link = f"https://europepmc.org/article/MED/{r['pmid']}"
        elif r.get("doi"):
            link = f"https://doi.org/{r['doi']}"
        else:
            continue
        items.append({"title": r.get("title", ""), "link": link, "desc": r.get("abstractText", ""),
                      "date": r.get("firstPublicationDate", ""), "thumb": ""})
    return items


# ---------------------------------------------------------------- 요약

_COMMENT = re.compile(r"<!--.*?(-->|$)", re.S)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_ARXIV_PREFIX = re.compile(r"^arXiv:\S+\s+Announce Type:\s*\S+\s*(Abstract:)?\s*", re.I)
_SENT = re.compile(r"(?<=[.!?。])\s+|(?<=다\.)\s*|(?<=요\.)\s*")


def clean_text(s):
    s = html.unescape(s or "")  # 이스케이프된 HTML(&lt;p&gt;)도 태그로 인식하도록 먼저 풀기
    s = _COMMENT.sub(" ", s)
    s = _TAG.sub(" ", s)
    s = html.unescape(s)
    s = _WS.sub(" ", s).strip()
    return _ARXIV_PREFIX.sub("", s)


def summarize(desc, title):
    """무료 자동 요약: 본문 앞부분에서 완결된 문장을 SUMMARY_CHARS 이내로 발췌."""
    text = clean_text(desc)
    if not text or text == title or (text.startswith(title[:40]) and len(text) < len(title) + 40):
        return ""
    out = ""
    for sent in _SENT.split(text):
        sent = sent.strip()
        if not sent:
            continue
        if len(out) + len(sent) + 1 > SUMMARY_CHARS:
            break
        out = (out + " " + sent).strip()
    if not out:  # 첫 문장이 너무 길면 단어 경계에서 자름
        out = text[:SUMMARY_CHARS].rsplit(" ", 1)[0].rstrip(",;:·") + "…"
    return out


def is_ai_related(item, keywords, title_only=False):
    blob = (item["title"] if title_only else item["title"] + " " + clean_text(item["desc"])[:400]).lower()
    for k in keywords:
        k = k.lower()
        if k.isascii() and len(k) <= 3:
            if re.search(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])", blob):
                return True
        elif k in blob:
            return True
    return False


def norm_link(link):
    u = urllib.parse.urlsplit(link)
    q = [(k, v) for k, v in urllib.parse.parse_qsl(u.query) if not k.lower().startswith("utm_")]
    return urllib.parse.urlunsplit((u.scheme, u.netloc.lower(), u.path.rstrip("/"), urllib.parse.urlencode(q), ""))


def item_id(link, title):
    return hashlib.sha1((norm_link(link) or title).encode()).hexdigest()[:16]


_TITLE_SUFFIX = re.compile(r"\s+-\s+[^-]{1,40}$")


# ---------------------------------------------------------------- 파이프라인

def load_config():
    return json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))


def recent_items(today, days=DEDUPE_DAYS):
    """지난 며칠치 항목(중복 판단용)."""
    out = []
    for i in range(1, days + 1):
        p = DATA_DIR / f"{(today - timedelta(days=i)).isoformat()}.json"
        if p.exists():
            out += json.loads(p.read_text(encoding="utf-8"))["items"]
    return out


_BRACKET = re.compile(r"^\s*(\[[^\]]{1,12}\]|【[^】]{1,12}】|\([^)]{1,8}\))\s*")


def title_key(title):
    t = html.unescape(title).lower()
    while _BRACKET.match(t):  # [단독], [영상] 같은 말머리는 비교에서 뺀다
        t = _BRACKET.sub("", t, count=1)
    return re.sub(r"\W+", "", t)


_HANGUL = re.compile(r"[가-힣]")


def grams(key):
    g = frozenset(key[i:i + 2] for i in range(len(key) - 1)) or frozenset([key])
    return g, bool(_HANGUL.search(key))


def similar(a, b):
    """제목 글자쌍(2-gram) 겹침 비율. 같은 사건을 언론사마다 조금씩 다르게 쓴 제목을 잡는다."""
    (ga, ko_a), (gb, ko_b) = a, b
    if not ga or not gb:
        return False
    threshold = DUP_SIMILARITY_KO if ko_a and ko_b else DUP_SIMILARITY
    return len(ga & gb) / len(ga | gb) >= threshold


class Deduper:
    """같은 링크·같은 제목은 전체에서, 비슷한 제목은 같은 카테고리 안에서 걸러낸다."""

    def __init__(self):
        self.ids, self.keys, self.by_cat = set(), set(), {}

    def is_dup(self, it):
        key = title_key(it["title"])
        if it["id"] in self.ids or key[:60] in self.keys:
            return True
        g = grams(key)
        return any(similar(g, o) for o in self.by_cat.get(it["category"], ()))

    def add(self, it):
        key = title_key(it["title"])
        self.ids.add(it["id"])
        self.keys.add(key[:60])
        self.by_cat.setdefault(it["category"], []).append(grams(key))


def label(src):
    return f'{src["name"]} · {src["field"]}' if src.get("field") else src["name"]


_SLOW_HOST_LOCK = threading.Lock()


def fetch_youtube(url, ua=None):
    """유튜브 RSS는 채널 주소가 가끔 404를 내므로, 같은 채널의 '업로드 목록' 주소와 재시도로 보완한다."""
    urls = [url]
    m = re.search(r"channel_id=UC([\w-]+)", url)
    if m:
        urls.append(f"https://www.youtube.com/feeds/videos.xml?playlist_id=UU{m.group(1)}")
    err = None
    for attempt in range(3):
        for u in urls:
            try:
                return fetch(u, None, ua)
            except Exception as e:
                err = e
        time.sleep(3 * (attempt + 1))
    raise err


def collect_source(src, fixtures):
    host = urllib.parse.urlsplit(src["url"]).netloc
    if "nature.com" in host and not fixtures:
        with _SLOW_HOST_LOCK:  # 같은 사이트에 동시에 여러 번 요청하면 차단되므로 순서대로 천천히
            raw = fetch(src["url"], fixtures, src.get("ua"))
            time.sleep(2)
    elif "youtube.com" in host and not fixtures:
        raw = fetch_youtube(src["url"], src.get("ua"))
    else:
        raw = fetch(src["url"], fixtures, src.get("ua"))
    kind = src.get("type")
    if kind == "hf_papers":
        return parse_hf_papers(raw)
    if kind == "europepmc":
        return parse_europepmc(raw)
    return parse_feed(raw)


def translate_ko(text):
    """무료 구글 번역(키 없음)으로 제목을 한국어로. 실패하면 빈 문자열."""
    u = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=ko&dt=t&q=" + urllib.parse.quote(text)
    try:
        j = json.loads(fetch(u))
        return "".join(seg[0] for seg in j[0] if seg and seg[0]).strip()
    except Exception:
        return ""


def add_translations(items, fixtures=None, max_n=200):
    """해외 글(한글이 없는 제목)에 번역 제목(title_ko)을 붙인다. 논문 제목은 원문 그대로 둔다."""
    todo = [i for i in items if i["category"] != "papers" and not i.get("title_ko") and not _HANGUL.search(i["title"])][:max_n]
    if fixtures or not todo:
        return
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for it, ko in zip(todo, pool.map(translate_ko, [i["title"] for i in todo])):
            if ko and ko != it["title"] and _HANGUL.search(ko):
                it["title_ko"] = ko


def make_item(src, it, keywords, now):
    """피드 항목 하나를 브리핑 항목으로. 조건에 안 맞으면 None."""
    title = clean_text(it["title"])
    if not title or not it["link"]:
        return None
    if src.get("url", "").startswith("https://news.google.com"):
        title = _TITLE_SUFFIX.sub("", title)  # "제목 - 언론사" 에서 언론사 꼬리 제거
    d = parse_date(it["date"], src.get("tz", 0))
    if d and d > now + timedelta(minutes=10):  # 발행 시각이 미래로 찍힌 글은 수집 시각으로 맞춘다
        d = now
    if src.get("keywords") and not is_ai_related(it, src["keywords"], src.get("title_only")):
        return None  # 분야 키워드(예: 법·교육·에너지)가 있는 글만
    if (src.get("filter") or src.get("require_ai")) and not is_ai_related(it, keywords):
        return None
    return {
        "id": item_id(it["link"], title), "title": title, "link": it["link"],
        "source": label(src), "field": src.get("field", ""),
        "category": src["category"], "published": d.isoformat() if d else None,
        "summary": summarize(it["desc"], title),
        "thumb": "",  # 저작권 보호: 원본의 썸네일·사진은 수집하지 않는다
        "_d": d,
    }


def collect(fixtures=None, now=None):
    cfg = load_config()
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(KST).date()
    cutoff = now - timedelta(hours=FRESH_HOURS)
    history = Deduper()  # 최근 7일 동안 이미 올린 글
    for it in recent_items(today):
        history.add(it)
    keywords = cfg.get("ai_keywords", [])

    results, status = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(collect_source, s, fixtures): s for s in cfg["sources"]}
        for fut in concurrent.futures.as_completed(futs):
            src = futs[fut]
            try:
                raw_items = fut.result()
            except Exception as e:  # 한 소스가 실패해도 나머지는 계속
                status.append({"name": label(src), "ok": False, "count": 0, "error": f"{type(e).__name__}: {e}"[:200]})
                continue
            kept = []
            for it in raw_items:
                item = make_item(src, it, keywords, now)
                if not item:
                    continue
                d = item["_d"]
                if src.get("max_age_days"):  # 새 영상이 드문 채널: 더 긴 기간 허용(최근 7일 브리핑과 중복은 제외)
                    if d and d < now - timedelta(days=src["max_age_days"]):
                        continue
                elif d and d < cutoff and src["category"] != "papers":  # 논문은 주말·발표 지연이 있어 기간 제한 없이 최근 7일 중복만 제외
                    continue
                if history.is_dup(item):
                    continue
                del item["_d"]
                kept.append(item)
                if len(kept) >= src.get("limit", DEFAULT_LIMIT):
                    break
            status.append({"name": label(src), "ok": True, "count": len(kept), "fetched": len(raw_items)})
            results.extend(kept)

    DATA_DIR.mkdir(exist_ok=True)
    path = DATA_DIR / f"{today.isoformat()}.json"
    # 오늘 이미 올린 글을 먼저 두고, 새 글은 그것들·서로와 겹치지 않을 때만 더한다
    old = json.loads(path.read_text(encoding="utf-8"))["items"] if path.exists() else []
    new = sorted(results, key=lambda x: x["published"] or "", reverse=True)
    today_seen, uniq = Deduper(), []
    for it in old + new:
        if today_seen.is_dup(it):
            continue
        today_seen.add(it)
        uniq.append(it)
    uniq.sort(key=lambda x: x["published"] or "", reverse=True)
    per_cat = Counter()  # 30분마다 쌓이므로 분야별 하루 최대 개수를 넘으면 오래된 것부터 뺀다
    uniq = [i for i in uniq if (per_cat.update([i["category"]]) or per_cat[i["category"]] <= MAX_PER_CAT)]
    add_translations(uniq, fixtures)
    data = {"date": today.isoformat(), "generated_at": now.astimezone(KST).isoformat(timespec="minutes"),
            "items": uniq, "status": sorted(status, key=lambda s: s["name"])}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(s["ok"] for s in status)
    print(f"[collect] {today} 항목 {len(uniq)}개, 소스 {ok}/{len(status)} 성공 → {path.relative_to(ROOT)}")
    return data


_WHEN = re.compile(r"when(?::|%3A)\d+d", re.I)


def backfill(start, fixtures=None, now=None):
    """지난 날짜의 글을 거슬러 모은다. 구글 뉴스는 날짜별 검색, 나머지는 피드에 남아 있는 글에서 고른다."""
    cfg = load_config()
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(KST).date()
    days = [start + timedelta(days=i) for i in range((today - start).days)]
    if not days:
        return
    lo = datetime.combine(start, datetime.min.time(), KST)
    hi = datetime.combine(today, datetime.min.time(), KST)
    keywords = cfg.get("ai_keywords", [])
    seen = Deduper()
    for f in sorted(DATA_DIR.glob("*.json")):
        for it in json.loads(f.read_text(encoding="utf-8"))["items"]:
            seen.add(it)

    def urls(src):
        u = src["url"]
        if "news.google.com" in u and _WHEN.search(u):
            return [(d, _WHEN.sub(f"after:{d.isoformat()}+before:{(d + timedelta(days=1)).isoformat()}", u)) for d in days]
        if src.get("type") == "hf_papers":
            return [(d, f"{u}?date={d.isoformat()}") for d in days]
        return [(None, u)]

    def grab(src):
        out = []
        for day, u in urls(src):
            try:
                raw = fetch_youtube(u, src.get("ua")) if "youtube.com" in u and not fixtures else fetch(u, fixtures, src.get("ua"))
                kind = src.get("type")
                items = parse_hf_papers(raw) if kind == "hf_papers" else parse_europepmc(raw) if kind == "europepmc" else parse_feed(raw)
            except Exception as e:
                print(f"[backfill] {label(src)} {day or ''} 실패: {e}", file=sys.stderr)
                continue
            per_day = Counter()
            for it in items:
                item = make_item(src, it, keywords, now)
                if not item or not item["_d"] or not (lo <= item["_d"] < hi):
                    continue
                k = day or item["_d"].astimezone(KST).date()
                if per_day[k] >= src.get("limit", DEFAULT_LIMIT):
                    continue
                per_day[k] += 1
                out.append(item)
            if "news.google.com" in u:
                time.sleep(1)
        return out

    found = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for items in pool.map(grab, cfg["sources"]):
            found += items
    by_day = {}
    for it in sorted(found, key=lambda x: x["published"], reverse=True):
        if seen.is_dup(it):
            continue
        seen.add(it)
        by_day.setdefault(it.pop("_d").astimezone(KST).date(), []).append(it)
    for f in sorted(DATA_DIR.glob("*.json")):  # 새 글이 없던 날도 번역 제목은 채운다
        by_day.setdefault(datetime.fromisoformat(f.stem).date(), [])
    for day, items in sorted(by_day.items()):
        path = DATA_DIR / f"{day.isoformat()}.json"
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else \
            {"date": day.isoformat(), "generated_at": f"{day.isoformat()}T23:59+09:00", "items": [], "status": []}
        merged = sorted(data["items"] + items, key=lambda x: x["published"] or "", reverse=True)
        per_cat = Counter()
        data["items"] = [i for i in merged if (per_cat.update([i["category"]]) or per_cat[i["category"]] <= MAX_PER_CAT)]
        add_translations(data["items"], fixtures)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[backfill] {day}: +{len(items)} → {len(data['items'])}개 {dict(Counter(i['category'] for i in data['items']))}")


# ---------------------------------------------------------------- 키워드

STOP = set("""the a an and or of to in for on with by from at is are was were be as its it this that new how why what
ai 및 등 위한 대한 통해 있는 있다 한다 한 수 것 더 위해 에서 으로 로 를 을 이 가 은 는 의 도 와 과 vs via using based
towards toward into about over our your their can not no we you us more model models""".split())


def top_keywords(items, n=12):
    c = Counter()
    for it in items:
        words = set(re.findall(r"[A-Za-z][A-Za-z0-9.+-]{1,}|[가-힣]{2,}", it["title"]))
        for w in words:
            wl = w.lower().strip(".-")
            if wl in STOP or len(wl) < 2:
                continue
            c[w if not w.isascii() or w.isupper() or w[0].isupper() else wl] += 1
    return [w for w, k in c.most_common(n) if k >= 2]


# ---------------------------------------------------------------- 사이트 생성

CSS = """
:root{--bar:#2a0b17;--bar-text:#f3e6eb;--bg:#fff;--card:#fff;--text:#1f1a1c;--muted:#6f6468;--line:#eee3e7;
--accent:#7a1f3d;--soft:#f7eaef;--shadow:0 6px 18px rgba(42,11,23,.12)}
@media (prefers-color-scheme:dark){:root{--bg:#141012;--card:#1d1619;--text:#f2e9ec;--muted:#b3a4aa;--line:#33262c;
--accent:#e58fae;--soft:#3a2530;--shadow:0 6px 18px rgba(0,0,0,.4)}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 "Pretendard Variable",Pretendard,-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;-webkit-font-smoothing:antialiased;word-break:keep-all;overflow-wrap:break-word;-webkit-text-size-adjust:100%}
a{color:inherit;text-decoration:none}
.serif{font-family:"Pretendard Variable",Pretendard,sans-serif;letter-spacing:-.01em}
.wrap{max-width:1200px;margin:0 auto;padding:0 20px}
.bar{background:var(--bar);color:var(--bar-text)}
.bar .wrap{display:flex;align-items:center;gap:28px;height:64px}
.logo{display:flex;align-items:center;gap:10px;font-size:20px;font-weight:800;letter-spacing:.14em;white-space:nowrap}
.logo svg{flex:none}
.bar nav{display:flex;gap:22px;flex:1;justify-content:center;font-size:14.5px;overflow-x:auto;scrollbar-width:none}
.bar nav a{opacity:.72;padding:4px 0;border-bottom:2px solid transparent;white-space:nowrap}
.bar nav a:hover,.bar nav a.on{opacity:1;border-color:var(--bar-text)}
.search{display:flex;align-items:center;gap:8px;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.14);border-radius:99px;padding:7px 14px;width:230px}
.search input{background:none;border:0;outline:0;color:var(--bar-text);font:inherit;font-size:14px;width:100%}
.search input::placeholder{color:rgba(243,230,235,.55)}
.eyebrow{font-size:14px;font-weight:600;color:var(--muted);margin:26px 0 0;letter-spacing:.01em}
.hero{display:grid;grid-template-columns:1.12fr 1fr;gap:56px;padding:14px 0 28px}
.hero h2{font-size:32px;line-height:1.35;font-weight:700;letter-spacing:-.02em;color:var(--accent);margin:0 0 18px}
.badge{display:inline-block;vertical-align:middle;background:var(--accent);color:#fff;font:600 12px/1 "Pretendard Variable",Pretendard,sans-serif;padding:7px 12px;border-radius:99px;margin-left:10px;position:relative;top:-3px;box-shadow:var(--shadow)}
.thumb{position:relative;display:block;overflow:hidden;border-radius:16px;aspect-ratio:16/9;box-shadow:var(--shadow);background:#2a0b17}
.thumb .art{position:absolute;inset:0;width:100%;height:100%;transition:transform .5s}
.thumb:hover .art{transform:scale(1.04)}
.thumb .ico{display:none}
.trend .thumb .ico{display:grid;place-items:center;position:absolute;inset:0;color:#fff}
.trend .thumb .ico svg{width:30%;height:30%;filter:drop-shadow(0 1px 3px rgba(0,0,0,.3))}
.thumb .tag{position:absolute;left:14px;bottom:14px;display:inline-flex;align-items:center;gap:6px;color:#fff;font-size:13px;font-weight:600;
background:rgba(0,0,0,.28);border:1px solid rgba(255,255,255,.22);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);padding:5px 12px 5px 9px;border-radius:99px}
.thumb .tag svg{width:16px;height:16px}
.meta{display:flex;flex-wrap:wrap;align-items:center;gap:6px 16px;font-size:13px;color:var(--muted)}
.meta svg{width:14px;height:14px;vertical-align:-2px;margin-right:4px}
.hero .meta{margin:16px 0 10px}
.hero p.sum{font-size:17px;color:var(--muted);margin:0 0 16px}
.actions{display:flex;align-items:center;gap:14px}
.read{color:var(--accent);font-weight:600;padding:6px}
.read:hover{text-decoration:underline}
.circle{width:36px;height:36px;border-radius:50%;border:0;background:var(--soft);color:var(--accent);display:grid;place-items:center;cursor:pointer;box-shadow:0 2px 6px rgba(42,11,23,.12)}
.side-h{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:14px}
.side-h h2{font-size:16px;margin:0;font-weight:600}.side-h a{font-size:13px;color:var(--muted)}
.trend{display:grid;grid-template-columns:150px 1fr;gap:16px;margin-bottom:16px}
.trend .thumb{border-radius:12px}.trend .thumb .tag{display:none}
.trend h3{font-size:16.5px;line-height:1.45;font-weight:600;color:var(--accent);margin:0 0 4px}
.trend p{margin:0 0 4px;font-size:13px;color:var(--muted);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.kw{display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:18px 0;border-top:1px solid var(--line)}
.kw strong{font-size:14px;margin-right:4px}.kw span{background:var(--soft);color:var(--accent);border-radius:99px;padding:3px 12px;font-size:13px}
.kw .info{background:none;color:var(--muted);margin-left:auto;padding:0}
.tabs{position:sticky;top:0;z-index:2;background:var(--bg);display:flex;gap:8px;overflow-x:auto;padding:12px 0;border-bottom:1px solid var(--line);scrollbar-width:none}
.tabs button{border:1px solid var(--line);background:var(--card);color:var(--text);border-radius:99px;padding:7px 16px;font:inherit;font-size:14px;cursor:pointer;white-space:nowrap}
.tabs button.on{background:var(--accent);border-color:var(--accent);color:#fff}
section.cat>h2{font-size:24px;font-weight:700;margin:34px 0 16px;color:var(--accent)}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:28px 24px}
.card h3{font-size:17px;line-height:1.5;font-weight:600;margin:14px 0 6px}
.card h3 a:hover,.trend h3 a:hover,.hero h2 a:hover{text-decoration:underline}
.card p{margin:0 0 8px;font-size:14px;color:var(--muted);display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.list{display:grid;grid-template-columns:1fr 1fr;gap:0 40px;margin-top:18px}
.row{padding:14px 0 12px;border-bottom:1px solid var(--line)}.row h3{margin:0 0 4px;font-size:16px}.row p{-webkit-line-clamp:2;margin-bottom:6px}
.empty{color:var(--muted);font-size:14px}
footer{margin-top:56px;line-height:1.7;padding-top:30px;padding-bottom:44px;border-top:1px solid var(--line);font-size:13px;color:var(--muted)}
footer.wrap{margin-top:64px}
.foot{display:flex;justify-content:space-between;gap:40px;flex-wrap:wrap}.fbrand p{margin:6px 0 0}.fbrand .copy{font-size:12px;opacity:.85}
.flogo{display:inline-flex;align-items:center;gap:8px;font-weight:800;letter-spacing:.14em;color:var(--text);font-size:16px}.flogo svg{width:24px;height:24px}.flogo rect{stroke:var(--accent)}.flogo path{fill:var(--accent)}
.connect{display:flex;flex-direction:column;gap:6px;min-width:140px}.connect h4{margin:0 0 4px;font-size:12px;font-weight:600;letter-spacing:.08em;color:var(--muted)}
.connect a{color:var(--text);font-size:15px}.connect a:hover{color:var(--accent);text-decoration:underline}
details summary{cursor:pointer}ul.st{columns:3;padding-left:18px}ul.st .bad{color:#c2410c}
ul.days{list-style:none;padding:0;max-width:640px}ul.days li{padding:12px 0;border-bottom:1px solid var(--line)}ul.days a{color:var(--accent)}
[hidden]{display:none!important}
@media (max-width:960px){.hero{grid-template-columns:1fr;gap:32px}.grid{grid-template-columns:repeat(2,1fr)}
.bar .wrap{flex-wrap:wrap;height:auto;padding-top:12px;padding-bottom:12px;gap:10px 16px}
.bar nav{order:2;flex:1 0 100%;justify-content:flex-start;gap:20px;margin:0 -16px;padding:2px 16px}
.search{order:3;width:100%}.search input{font-size:16px}}
@media (max-width:600px){body{font-size:16px;line-height:1.65}.wrap{padding:0 16px}
.logo{font-size:18px}.eyebrow{margin-top:18px;font-size:13px}.hero{padding:8px 0 16px;gap:28px}.hero h2{font-size:23px;line-height:1.4;margin-bottom:14px}
.badge{margin:8px 0 0;top:0;display:table}.hero .thumb{aspect-ratio:16/8}.hero p.sum{font-size:16px;line-height:1.7}
.trend{grid-template-columns:88px 1fr;gap:14px;padding-bottom:14px;border-bottom:1px solid var(--line)}.trend .thumb{aspect-ratio:1}
.trend h3{font-size:16px}.trend .meta span:last-child{display:none}
.kw{gap:6px}.kw .info{margin-left:0;width:100%;padding-top:4px}
.tabs{padding:10px 0;margin:0 -16px;padding-left:16px;padding-right:16px}.tabs button{padding:9px 16px;font-size:15px}
section.cat>h2{font-size:21px;margin:26px 0 8px}
.grid,.list{grid-template-columns:1fr;gap:0}
.card:not(.row){display:grid;grid-template-columns:96px 1fr;column-gap:14px;padding:14px 0;border-bottom:1px solid var(--line)}
.card:not(.row) .thumb{grid-row:1/span 3;aspect-ratio:1;border-radius:12px;box-shadow:none}
.card .thumb .tag{display:none}.card .thumb .ico{display:grid;place-items:center;position:absolute;inset:0;color:#fff}.card .thumb .ico svg{width:36%;height:36%;filter:drop-shadow(0 1px 3px rgba(0,0,0,.3))}
.card h3{font-size:16px;line-height:1.5;margin:0 0 4px}.card p{font-size:14px;-webkit-line-clamp:2;margin-bottom:6px}
.row{padding:14px 0}.meta{font-size:12.5px}
ul.st{columns:1}footer{margin-top:36px}}
.thumb img.art{object-fit:cover;display:block}
.ko{display:block;color:var(--muted);font-size:.84em;font-weight:500;line-height:1.5;margin-top:3px;letter-spacing:0}
.bar nav a[data-go]{display:inline}
.rows{display:grid;grid-template-columns:1fr 1fr;gap:0 40px}
.rows article{padding:14px 0 12px;border-bottom:1px solid var(--line)}
.rows h3{margin:0 0 4px;font-size:16px;line-height:1.5;font-weight:600}.rows h3 a:hover{text-decoration:underline}
.rows p{margin:0 0 6px;font-size:14px;color:var(--muted);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.pager{display:flex;flex-wrap:wrap;justify-content:center;gap:6px;margin:22px 0 4px}
.pager a,.pager button,.pager span{min-width:38px;height:38px;padding:0 12px;border-radius:99px;border:1px solid var(--line);background:var(--card);color:var(--text);font:inherit;font-size:14px;display:inline-grid;place-items:center;cursor:pointer}
.pager .on{background:var(--accent);border-color:var(--accent);color:#fff}.pager span{border:0;cursor:default;min-width:20px;padding:0}
.more{display:inline-block;margin-top:12px;color:var(--accent);font-weight:600;font-size:14px}.more:hover{text-decoration:underline}
.ph{display:flex;align-items:baseline;justify-content:space-between;gap:12px;flex-wrap:wrap;margin:36px 0 8px}
.btn-w{display:inline-block;margin-left:14px;background:var(--accent);color:#fff;font-weight:600;font-size:14px;padding:8px 16px;border-radius:99px}.btn-w:hover{opacity:.9}
.ph h1{font-size:28px;font-weight:700;color:var(--accent);margin:0}.ph span{color:var(--muted);font-size:14px}
.editor-h{display:flex;justify-content:space-between;align-items:baseline;margin:30px 0 14px}
.editor-h h2{font-size:22px;margin:0;color:var(--accent);font-weight:700}.editor-h a{font-size:13.5px;color:var(--muted)}
.egrid{display:grid;grid-template-columns:repeat(3,1fr);gap:24px;margin-bottom:26px}
.egrid h3{font-size:17px;line-height:1.5;margin:12px 0 4px;font-weight:600}.egrid p{margin:0 0 6px;font-size:14px;color:var(--muted);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.elist article{display:grid;grid-template-columns:220px 1fr;gap:20px;padding:18px 0;border-bottom:1px solid var(--line)}
.elist .thumb{border-radius:12px;box-shadow:none}.elist h3{font-size:19px;margin:0 0 6px;line-height:1.45}.elist p{margin:0 0 8px;color:var(--muted);font-size:14.5px}
.post{max-width:760px;margin:0 auto;padding-bottom:10px}
.post h1{font-size:34px;line-height:1.35;letter-spacing:-.02em;color:var(--accent);margin:40px 0 10px}
.post .meta{margin-bottom:26px}
.post .body{font-size:17.5px;line-height:1.85}
.post .body h2{font-size:24px;margin:36px 0 10px}.post .body h3{font-size:20px;margin:28px 0 8px}
.post .body img{display:block;max-width:100%;height:auto;border-radius:12px;margin:22px auto}
.post .body blockquote{margin:20px 0;padding:4px 18px;border-left:3px solid var(--accent);color:var(--muted)}
.post .body a{color:var(--accent);text-decoration:underline}
.credits li{margin-bottom:6px;font-size:14px}
@media (max-width:960px){.egrid{grid-template-columns:1fr 1fr}}
@media (max-width:600px){.rows{grid-template-columns:1fr}.rows h3{font-size:16px}
.egrid{grid-template-columns:1fr;gap:18px}.elist article{grid-template-columns:110px 1fr;gap:14px}.elist .thumb{aspect-ratio:1}.elist h3{font-size:16.5px}
.elist .thumb .tag{display:none}.ph h1{font-size:23px}.post h1{font-size:25px;margin-top:26px}.post .body{font-size:17px}
.pager a,.pager button{min-width:40px;height:40px}}
"""

JS = """
const PER=8,tabs=document.querySelectorAll('.tabs button'),secs=document.querySelectorAll('section.cat'),boxes=document.querySelectorAll('.rows[data-pg]');
function pageLinks(p,n){const s=new Set([0,n-1,p-1,p,p+1]);let h=p>0?`<button data-p="${p-1}" aria-label="이전">‹</button>`:'',last=-1;
 for(let i=0;i<n;i++){if(!s.has(i))continue;if(i-last>1)h+='<span>…</span>';h+=`<button data-p="${i}" class="${i===p?'on':''}">${i+1}</button>`;last=i;}
 return h+(p<n-1?`<button data-p="${p+1}" aria-label="다음">›</button>`:'');}
boxes.forEach(box=>{const items=[...box.children],pager=box.nextElementSibling,n=Math.ceil(items.length/PER);
 box._go=(p,scroll)=>{items.forEach((a,i)=>a.hidden=Math.floor(i/PER)!==p);pager.hidden=false;pager.innerHTML=n>1?pageLinks(p,n):'';
  pager.querySelectorAll('button').forEach(b=>b.onclick=()=>box._go(+b.dataset.p,true));
  if(scroll)box.closest('section').scrollIntoView({behavior:'smooth'});};
 box._go(0);});
function show(c){tabs.forEach(x=>x.classList.toggle('on',x.dataset.cat===c));secs.forEach(s=>s.hidden=c!=='all'&&s.dataset.cat!==c);}
tabs.forEach(b=>b.onclick=()=>show(b.dataset.cat));
document.querySelectorAll('a[data-tab]').forEach(a=>a.onclick=e=>{e.preventDefault();show(a.dataset.tab);document.querySelector('.tabs').scrollIntoView({behavior:'smooth'});});
const q=document.querySelector('.search input');
if(q)q.oninput=()=>{const v=q.value.trim().toLowerCase();
 if(!v){boxes.forEach(b=>b._go(0));secs.forEach(s=>s.hidden=false);show('all');return;}
 show('all');boxes.forEach(b=>{[...b.children].forEach(a=>a.hidden=!a.dataset.q.includes(v));b.nextElementSibling.hidden=true;});
 secs.forEach(s=>s.hidden=!s.querySelector('article:not([hidden])'));};
document.querySelectorAll('.share').forEach(b=>b.onclick=async()=>{const u=b.dataset.url;
 try{if(navigator.share)await navigator.share({url:u,title:b.dataset.title});else{await navigator.clipboard.writeText(u);b.title='링크 복사됨';}}catch(e){}});
"""

WRITE_JS = r"""
const REPO=document.getElementById('w').dataset.repo,VK='metaxis_vault',enc=new TextEncoder(),dec=new TextDecoder();
const $=s=>document.querySelector(s),views=['#v-setup','#v-lock','#v-list','#v-edit'];
let TOKEN=null,POSTS=[],cur=null,imgs={},seq=0;
function view(id){views.forEach(v=>$(v).hidden=v!==id);}
function msg(el,t,bad){const m=$(el);m.textContent=t;m.style.color=bad?'#c2410c':'';}
const b64=u8=>{let s='';for(let i=0;i<u8.length;i+=8192)s+=String.fromCharCode.apply(null,u8.subarray(i,i+8192));return btoa(s);};
const unb64=s=>Uint8Array.from(atob(s),c=>c.charCodeAt(0));
async function kdf(pin,salt){const k=await crypto.subtle.importKey('raw',enc.encode(pin),'PBKDF2',false,['deriveKey']);
 return crypto.subtle.deriveKey({name:'PBKDF2',salt,iterations:600000,hash:'SHA-256'},k,{name:'AES-GCM',length:256},false,['encrypt','decrypt']);}
function vault(){try{return JSON.parse(localStorage.getItem(VK)||'null');}catch(e){return null;}}
function saveVault(v){try{localStorage.setItem(VK,JSON.stringify(v));}catch(e){}}
async function gh(path,opt={}){const r=await fetch('https://api.github.com/repos/'+REPO+path,{...opt,
 headers:{Authorization:'Bearer '+TOKEN,Accept:'application/vnd.github+json','Content-Type':'application/json'}});
 if(!r.ok)throw new Error(r.status+' '+(await r.text()).slice(0,160));return r.status===204?null:r.json();}
async function commit(files,message){const tree=[];
 for(const f of files){if(f.del){tree.push({path:f.path,mode:'100644',type:'blob',sha:null});continue;}
  const b=await gh('/git/blobs',{method:'POST',body:JSON.stringify({content:f.b64,encoding:'base64'})});tree.push({path:f.path,mode:'100644',type:'blob',sha:b.sha});}
 for(let t=0;;t++){const ref=await gh('/git/ref/heads/main'),c=await gh('/git/commits/'+ref.object.sha);
  const tr=await gh('/git/trees',{method:'POST',body:JSON.stringify({base_tree:c.tree.sha,tree})});
  const nc=await gh('/git/commits',{method:'POST',body:JSON.stringify({message,tree:tr.sha,parents:[ref.object.sha]})});
  try{await gh('/git/refs/heads/main',{method:'PATCH',body:JSON.stringify({sha:nc.sha})});return;}
  catch(e){if(t>=3)throw e;await new Promise(r=>setTimeout(r,2000));}}}
function pinOk(p){return /^\d{4}$/.test(p);}
$('#setup-go').onclick=async()=>{const tok=$('#tok').value.trim(),p1=$('#pin1').value,p2=$('#pin2').value;
 if(!tok)return msg('#setup-msg','토큰을 붙여넣어 주세요.',1);if(!pinOk(p1))return msg('#setup-msg','비밀번호는 숫자 4자리예요.',1);
 if(p1!==p2)return msg('#setup-msg','비밀번호 두 번 입력한 값이 달라요.',1);
 msg('#setup-msg','확인 중…');TOKEN=tok;
 try{const r=await gh('');if(!r.permissions||!r.permissions.push)throw new Error('이 토큰에는 쓰기 권한이 없어요.');}
 catch(e){TOKEN=null;return msg('#setup-msg','토큰을 확인할 수 없어요: '+e.message,1);}
 const salt=crypto.getRandomValues(new Uint8Array(16)),iv=crypto.getRandomValues(new Uint8Array(12));
 const ct=new Uint8Array(await crypto.subtle.encrypt({name:'AES-GCM',iv},await kdf(p1,salt),enc.encode(tok)));
 saveVault({salt:b64(salt),iv:b64(iv),ct:b64(ct),fails:0});$('#tok').value='';openList();};
$('#pin').oninput=async()=>{const p=$('#pin').value;if(!pinOk(p))return;const v=vault();
 try{TOKEN=dec.decode(await crypto.subtle.decrypt({name:'AES-GCM',iv:unb64(v.iv)},await kdf(p,unb64(v.salt)),unb64(v.ct)));
  v.fails=0;saveVault(v);$('#pin').value='';openList();}
 catch(e){v.fails=(v.fails||0)+1;$('#pin').value='';
  if(v.fails>=5){localStorage.removeItem(VK);msg('#lock-msg','5번 틀려서 이 기기의 로그인 정보를 지웠어요. 처음 설정을 다시 해주세요.',1);setTimeout(start,2500);}
  else{saveVault(v);msg('#lock-msg',`비밀번호가 달라요. (${v.fails}/5)`,1);}}};
$('#reset').onclick=()=>{if(confirm('이 기기에 저장된 로그인 정보를 지울까요?')){localStorage.removeItem(VK);start();}};
async function openList(){view('#v-list');msg('#list-msg','글 목록을 불러오는 중…');
 try{POSTS=await (await fetch('posts.json?'+Date.now())).json();}catch(e){POSTS=[];}
 msg('#list-msg','');renderList();}
function renderList(){$('#plist').innerHTML=POSTS.map((p,i)=>`<li><b>${esc(p.title)}</b> <span class="meta">${p.date.slice(0,10)}</span>
  <button data-e="${i}">수정</button> <button data-d="${i}">삭제</button></li>`).join('')||'<li class="meta">아직 쓴 글이 없어요.</li>';
 $('#plist').querySelectorAll('[data-e]').forEach(b=>b.onclick=()=>edit(POSTS[+b.dataset.e]));
 $('#plist').querySelectorAll('[data-d]').forEach(b=>b.onclick=()=>del(POSTS[+b.dataset.d]));}
function esc(s){return String(s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function newId(){const d=new Date(),z=n=>String(n).padStart(2,'0');return `${d.getFullYear()}${z(d.getMonth()+1)}${z(d.getDate())}-${z(d.getHours())}${z(d.getMinutes())}${z(d.getSeconds())}`;}
$('#new').onclick=()=>edit(null);
function edit(p){cur=p?{...p}:{id:newId(),title:'',body:'',cover:'',images:[],date:''};imgs={};seq=(cur.images||[]).length;
 $('#title').value=cur.title;$('#body').value=cur.body;msg('#edit-msg','');drawThumbs();view('#v-edit');}
function drawThumbs(){const all=[...(cur.images||[]).map(n=>({n,src:'img/'+n})),...Object.entries(imgs).map(([n,src])=>({n,src}))];
 $('#thumbs').innerHTML=all.map(x=>`<figure><img src="${x.src}" alt=""><label><input type="radio" name="cover" value="${x.n}" ${cur.cover==='img/'+x.n?'checked':''}> 대표 사진</label></figure>`).join('');
 $('#thumbs').querySelectorAll('input').forEach(r=>r.onchange=()=>cur.cover='img/'+r.value);}
async function shrink(file){const bmp=await createImageBitmap(file),s=Math.min(1,1600/bmp.width),c=document.createElement('canvas');
 c.width=Math.round(bmp.width*s);c.height=Math.round(bmp.height*s);c.getContext('2d').drawImage(bmp,0,0,c.width,c.height);return c.toDataURL('image/jpeg',.82);}
$('#file').onchange=async e=>{const ta=$('#body');for(const f of e.target.files){if(!f.type.startsWith('image/'))continue;
 const name=`${cur.id}-${++seq}.jpg`;imgs[name]=await shrink(f);if(!cur.cover)cur.cover='img/'+name;
 const at=ta.selectionStart||ta.value.length,ins=`\n\n![사진](img/${name})\n\n`;ta.value=ta.value.slice(0,at)+ins+ta.value.slice(at);ta.selectionStart=ta.selectionEnd=at+ins.length;}
 e.target.value='';drawThumbs();};
$('#cancel').onclick=()=>{view('#v-list');renderList();};
$('#publish').onclick=async()=>{const title=$('#title').value.trim(),body=$('#body').value.trim();
 if(!title||!body)return msg('#edit-msg','제목과 내용을 모두 써 주세요.',1);
 const used=n=>body.includes('img/'+n)||cur.cover==='img/'+n,files=[];
 const keep=(cur.images||[]).filter(used);(cur.images||[]).filter(n=>!used(n)).forEach(n=>files.push({path:'posts/img/'+n,del:1}));
 for(const [n,d] of Object.entries(imgs))if(used(n)){files.push({path:'posts/img/'+n,b64:d.split(',')[1]});keep.push(n);}
 if(cur.cover&&!keep.includes(cur.cover.slice(4)))cur.cover=keep.length?'img/'+keep[0]:'';
 const post={id:cur.id,title,body,cover:cur.cover,images:keep,date:cur.date||new Date().toISOString(),updated:new Date().toISOString()};
 files.push({path:`posts/${cur.id}.json`,b64:b64(enc.encode(JSON.stringify(post,null,1)))});
 $('#publish').disabled=true;msg('#edit-msg','올리는 중…');
 try{await commit(files,'에디터 글: '+title);msg('#edit-msg','게시했어요! 1~2분 뒤 사이트에 보여요.');
  const i=POSTS.findIndex(p=>p.id===post.id);if(i>=0)POSTS[i]=post;else POSTS.unshift(post);cur=post;imgs={};drawThumbs();}
 catch(e){msg('#edit-msg','올리지 못했어요: '+e.message,1);}finally{$('#publish').disabled=false;}};
async function del(p){if(!confirm(`'${p.title}' 글을 삭제할까요?`))return;msg('#list-msg','삭제하는 중…');
 try{await commit([{path:`posts/${p.id}.json`,del:1},...(p.images||[]).map(n=>({path:'posts/img/'+n,del:1}))],'에디터 글 삭제: '+p.title);
  POSTS=POSTS.filter(x=>x.id!==p.id);msg('#list-msg','삭제했어요. 1~2분 뒤 사이트에서 사라져요.');
  renderList();}
 catch(e){msg('#list-msg','삭제하지 못했어요: '+e.message,1);}}
function start(){TOKEN=null;view(vault()?'#v-lock':'#v-setup');msg('#lock-msg','');if(vault())$('#pin').focus();}
start();
"""

WEEKDAYS = "월화수목금토일"
CARDS_PER_CAT = 6  # 분야별로 표지 카드로 보여줄 개수(나머지는 목록)
ICON_CLOCK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>'
ICON_SRC = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 5h16v14H4z"/><path d="M8 9h8M8 13h5"/></svg>'
ICON_SHARE = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4"/></svg>'
ICON_SEARCH = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>'
LOGO = ('<svg width="30" height="30" viewBox="0 0 32 32"><rect x="1" y="1" width="30" height="30" rx="8" fill="none" stroke="#e58fae" stroke-width="1.6"/>'
        '<path d="M16 7c.9 4.6 2.4 6.1 7 7-4.6.9-6.1 2.4-7 7-.9-4.6-2.4-6.1-7-7 4.6-.9 6.1-2.4 7-7z" fill="#f3e6eb"/></svg>')
FAVICON = ("data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 32 32%22>"
           "<rect width=%2232%22 height=%2232%22 rx=%227%22 fill=%22%232a0b17%22/>"
           "<path d=%22M16 6c1 5 2.7 6.7 8 8-5.3 1.3-7 3-8 8-1-5-2.7-6.7-8-8 5.3-1.3 7-3 8-8z%22 fill=%22%23f3e6eb%22/></svg>")


def esc(s):
    return html.escape(s or "", quote=True)


def fmt_time(iso):
    if not iso:
        return ""
    d = datetime.fromisoformat(iso).astimezone(KST)
    return d.strftime("%m.%d %H:%M")


def site_cfg():
    s = load_config().get("site", {})
    url = (f'https://{s["domain"]}' if s.get("domain") else s.get("url", "")).rstrip("/")
    return {"name": s.get("name", "METAXIS"), "url": url, "domain": s.get("domain", ""),
            "description": s.get("description", ""), "google": s.get("google_verification", ""),
            "naver": s.get("naver_verification", ""), "repo": s.get("repo", "Alexkim9113/ai-briefing"),
            "email": s.get("contact_email", ""), "instagram": s.get("instagram", ""), "x": s.get("x", "")}


def connect_links(sc, base):
    contact = f'mailto:{sc["email"]}' if sc.get("email") else f"{base}policy.html#contact"
    links = [("Contact", contact, False)]
    if sc.get("instagram"):
        links.append(("Instagram", sc["instagram"], True))
    if sc.get("x"):
        links.append(("X", sc["x"], True))
    links.append(("정책", f"{base}policy.html", False))
    return "".join(f'<a href="{esc(u)}"{" target=_blank rel=noopener" if ext else ""}>{n}</a>' for n, u, ext in links)


def page(title, body, base="", cats=None, search=True, desc=None, path="", jsonld=None, og_type="website", index=True,
         active="", script="", image=None):
    sc = site_cfg()
    canonical = f'{sc["url"]}/{path}'
    desc = desc or sc["description"]
    on = lambda k: ' class="on" aria-current="page"' if k == active else ""
    nav = f'<a href="{base}index.html"{on("home")}>홈</a>'
    if cats:
        nav += "".join(f'<a href="{base}{c}/"{on(c)}>{esc(n)}</a>' for c, n in cats.items())
    nav += f'<a href="{base}editor/"{on("editor")}>에디터</a>'
    box = (f'<label class="search">{ICON_SEARCH}<input type="search" placeholder="뉴스, 주제 검색" aria-label="검색"></label>'
           if search else "")
    verify = ""
    if sc["google"]:
        verify += f'<meta name="google-site-verification" content="{esc(sc["google"])}">'
    if sc["naver"]:
        verify += f'<meta name="naver-site-verification" content="{esc(sc["naver"])}">'
    ld = "".join(f'<script type="application/ld+json">{json.dumps(j, ensure_ascii=False)}</script>' for j in (jsonld or []))
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{esc(canonical)}">
<meta name="robots" content="{"index,follow,max-image-preview:large" if index else "noindex"}">
<meta property="og:type" content="{og_type}"><meta property="og:site_name" content="{esc(sc["name"])}">
<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{esc(canonical)}"><meta property="og:image" content="{esc(image or sc["url"] + "/og.png")}">
{"" if image else '<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">'}<meta property="og:locale" content="ko_KR">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(desc)}"><meta name="twitter:image" content="{esc(image or sc["url"] + "/og.png")}">
<meta name="theme-color" content="#2a0b17">{verify}
<link rel="icon" href="{FAVICON}"><link rel="apple-touch-icon" href="{base}apple-touch-icon.png">
<link rel="alternate" type="application/rss+xml" title="{esc(sc["name"])} RSS" href="{sc["url"]}/feed.xml">
<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">
<style>{CSS}</style>{ld}</head><body>
<header class="bar"><div class="wrap"><a class="logo serif" href="{base}index.html" aria-label="{esc(sc["name"])} 홈">{LOGO}<span>{esc(sc["name"])}</span></a><nav aria-label="주요 메뉴">{nav}</nav>{box}</div></header>
<main class="wrap">{body}</main>
<footer class="wrap foot"><div class="fbrand"><a class="flogo" href="{base}index.html">{LOGO}<span>{esc(sc["name"])}</span></a>
<p class="copy">© {datetime.now(KST).year} {esc(sc["name"])}. 기사·논문·영상 등 이 사이트에 소개된 모든 정보의 저작권은 원작자에게 있습니다.</p></div>
<div class="connect"><h4>CONNECT</h4>{connect_links(sc, base)}</div></footer>
<script>{JS}{script}</script></body></html>"""


# 표지 아이콘: 기사 제목·요약의 단어로 주제를 골라 직접 그린 아이콘을 넣는다(외부 이미지 없음)
TOPICS = [
    ("의료", ["의료", "병원", "환자", "진단", "헬스", "신약", "바이오", "clinical", "medical", "health", "patient", "drug", "surgical", "hospital", "disease", "protein", "cancer"],
     '<path d="M9 3h6v6h6v6h-6v6H9v-6H3V9h6z"/>'),
    ("법·정책", ["법", "규제", "정책", "정부", "국회", "소송", "저작권", "기본법", "law", "legal", "regulation", "policy", "court", "lawsuit", "copyright", "government", "ai act"],
     '<path d="M12 3v18M5 21h14M4 7h16M7 7l-3 7a3 3 0 0 0 6 0zM17 7l-3 7a3 3 0 0 0 6 0z"/>'),
    ("반도체", ["반도체", "칩", "gpu", "엔비디아", "nvidia", "hbm", "tsmc", "삼성전자", "sk하이닉스", "chip", "semiconductor", "datacenter", "데이터센터"],
     '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/><rect x="10" y="10" width="4" height="4"/>'),
    ("로봇", ["로봇", "휴머노이드", "피지컬", "자율주행", "드론", "robot", "humanoid", "autonomous", "drone", "embodied"],
     '<rect x="5" y="8" width="14" height="11" rx="3"/><path d="M12 4v4M9 13h.01M15 13h.01M9 16h6M2 13h3M19 13h3"/><circle cx="12" cy="3" r="1"/>'),
    ("에너지·환경", ["에너지", "전력", "환경", "기후", "탄소", "배터리", "energy", "climate", "carbon", "grid", "battery", "solar", "environment"],
     '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>'),
    ("문화·예술", ["예술", "음악", "영화", "콘텐츠", "창작", "게임", "웹툰", "music", "art", "film", "creative", "game", "culture", "museum"],
     '<path d="M12 3a9 9 0 1 0 0 18c1.5 0 2-1 2-2 0-1.5-1.5-1.8-1.5-3s1-2 2.5-2H18a3 3 0 0 0 3-3c0-4.4-4-8-9-8z"/><circle cx="7.5" cy="11" r="1"/><circle cx="10" cy="7" r="1"/><circle cx="15" cy="7" r="1"/>'),
    ("교육", ["교육", "학생", "학교", "대학", "교사", "education", "student", "school", "teacher", "university"],
     '<path d="M2 9l10-5 10 5-10 5z"/><path d="M6 11v5c3 2 9 2 12 0v-5M22 9v6"/>'),
    ("보안", ["보안", "해킹", "사이버", "개인정보", "security", "cyber", "privacy", "attack", "hack"],
     '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/>'),
    ("투자·기업", ["투자", "매출", "주가", "상장", "인수", "펀딩", "시장", "스타트업", "funding", "investment", "startup", "revenue", "stock", "ipo", "valuation", "acquire"],
     '<path d="M3 20h18M5 16l4-5 4 3 6-8"/><path d="M15 6h4v4"/>'),
    ("언어모델", ["llm", "gpt", "챗gpt", "chatgpt", "claude", "gemini", "언어모델", "챗봇", "language model", "chatbot", "agent", "에이전트"],
     '<path d="M4 5h16v11H9l-5 4z"/><path d="M8 9h8M8 12h5"/>'),
]
TOPICS.append(("신제품·서비스", ["출시", "공개", "플랫폼", "서비스", "선보", "launch", "release", "unveil", "app", "feature"],
               '<path d="M14 4c3-1 5-1 6 0 1 1 1 3 0 6l-7 7-6-6z"/><path d="M7 11l-3 1-1 3 4-1M13 17l-1 3-3 1 1-4"/><circle cx="15.5" cy="8.5" r="1.5"/>'))
TOPIC_DEFAULT = {"papers": ("연구", '<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5M9 13h7M9 17h5"/>'),
                 "talks": ("강연", '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="M10 9l5 3-5 3z"/>'),
                 "policy": ("법·정책", TOPICS[1][2])}
TOPIC_SPARK = '<path d="M12 3c1 5 3 7 8 8-5 1-7 3-8 8-1-5-3-7-8-8 5-1 7-3 8-8z"/>'


def topic_of(it):
    text = (it["title"] + " " + (it.get("summary") or "")[:120]).lower()
    best, score = None, 0
    for name, words, icon in TOPICS:
        n = sum(1 for w in words if (re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", text) if w.isascii() else w in text))
        if n > score:
            best, score = (name, icon), n
    return best or TOPIC_DEFAULT.get(it["category"], ("AI", TOPIC_SPARK))


# 표지 그림: 기사마다 다른 추상 그라데이션(자체 생성 SVG)과 주제 아이콘. 외부 이미지는 쓰지 않는다.
ART_PALETTES = {
    "의료": ("#0f2a33", ["#2bb3a3", "#6fd3c3", "#1d6f8c"]), "법·정책": ("#1f1830", ["#7a5cc2", "#c9a5ff", "#4b3a8c"]),
    "반도체": ("#0d1b2e", ["#3b82f6", "#7dd3fc", "#1e3a8a"]), "로봇": ("#1a1f2b", ["#64748b", "#cbd5e1", "#38bdf8"]),
    "에너지·환경": ("#10261c", ["#34d399", "#bef264", "#0f766e"]), "문화·예술": ("#2a1026", ["#f472b6", "#fbbf24", "#a855f7"]),
    "교육": ("#2a1d0c", ["#f59e0b", "#fde68a", "#b45309"]), "보안": ("#101826", ["#475569", "#94a3b8", "#0ea5e9"]),
    "투자·기업": ("#0f2419", ["#22c55e", "#86efac", "#15803d"]), "언어모델": ("#2a0b17", ["#e58fae", "#a33a5c", "#f9c6d6"]),
    "신제품·서비스": ("#2b1208", ["#fb923c", "#fca5a5", "#c2410c"]), "연구": ("#141a33", ["#6366f1", "#a5b4fc", "#312e81"]),
    "영상": ("#2b0d0d", ["#ef4444", "#fca5a5", "#7f1d1d"]), "AI": ("#2a0b17", ["#a33a5c", "#e58fae", "#5b1a33"]),
}


def cover_svg(seed, topic):
    base, cols = ART_PALETTES.get(topic, ART_PALETTES["AI"])
    r = int(seed[:12], 16) if seed else 7
    blobs = ""
    for k in range(4):
        r, x = divmod(r, 160)
        r, y = divmod(r, 90)
        r, rad = divmod(r, 30)
        blobs += f'<circle cx="{x}" cy="{y}" r="{28 + rad}" fill="{cols[k % 3]}" opacity="{.55 + (k % 2) * .25}"/>'
    fid = "f" + (seed[:8] if seed else "0")
    return (f'<svg class="art" viewBox="0 0 160 90" preserveAspectRatio="xMidYMid slice" aria-hidden="true">'
            f'<defs><filter id="{fid}" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="14"/></filter></defs>'
            f'<rect width="160" height="90" fill="{base}"/><g filter="url(#{fid})">{blobs}</g></svg>')


def meta_html(it, cats, with_cat=False):
    t = fmt_time(it.get("published"))
    parts = [f"<span>{ICON_SRC}{esc(it['source'])}</span>"]
    if t:
        parts.append(f"<span>{ICON_CLOCK}{t}</span>")
    if with_cat:
        parts.append(f"<span>{esc(cats.get(it['category'], ''))}</span>")
    return '<div class="meta">' + "".join(parts) + "</div>"


def title_link(it):
    ko = f'<span class="ko">{esc(it["title_ko"])}</span>' if it.get("title_ko") else ""  # 해외 글: 원문 제목 아래 자동 번역 제목
    return f'<a href="{esc(it["link"])}" target="_blank" rel="noopener">{esc(it["title"])}</a>{ko}'


def pick_featured(items):
    """헤드라인 1개 + 주요 소식 4개. 요약이 있는 뉴스를 우선하고 분야가 겹치지 않게 고른다."""
    pri = {"news_ko": 0, "news_global": 1, "policy": 2, "talks": 3, "papers": 4}
    ranked = sorted(items, key=lambda i: (not i.get("summary"), pri.get(i["category"], 9)))
    if not ranked:
        return None, []
    hero, trend, used = ranked[0], [], set()
    for rnd in (0, 1):  # 1차: 분야별 하나씩, 2차: 남은 자리 채우기
        for i in ranked[1:]:
            if len(trend) == 4:
                break
            if i in trend or (rnd == 0 and i["category"] in used):
                continue
            trend.append(i)
            used.add(i["category"])
    return hero, trend


# 표지 사진: 저작권 없는 퍼블릭 도메인(CC0) 사진을 주제별로 골라 static/photos 에 저장해 두고 자동으로 붙인다.
# 기사 원본의 사진은 가져오지 않는다. 사진 목록과 출처는 static/photos/credits.json.
TOPIC_SLUG = {"AI": "ai", "반도체": "chip", "에너지·환경": "energy", "투자·기업": "invest", "신제품·서비스": "launch",
              "언어모델": "llm", "의료": "medical", "로봇": "robot", "보안": "security", "영상": "video",
              "법·정책": "law", "교육": "edu", "연구": "research", "문화·예술": "art"}
PER_PAGE = 8  # 목록 한 페이지에 보여줄 글 수


def load_photos():
    p = ROOT / "static" / "photos" / "credits.json"
    if not p.exists():
        return [], {}, []
    credits = json.loads(p.read_text(encoding="utf-8"))
    by = {}
    for c in credits:
        if c.get("topic"):
            by.setdefault(TOPIC_SLUG.get(c["topic"], "ai"), []).append(c["file"])
    tagged = [(c["file"], [t.lower() for t in c.get("tags", [])]) for c in credits if c.get("tags")]
    return credits, by, tagged


PHOTO_CREDITS, PHOTOS, PHOTO_TAGS = load_photos()


def _hit(tag, text):
    if tag.isascii() and len(tag) <= 3:
        return re.search(r"(?<![a-z0-9])" + re.escape(tag) + r"(?![a-z0-9])", text) is not None
    return tag in text


def photo_for(it, used=None):
    """기사 제목(번역 제목 포함)·요약과 사진 태그가 가장 많이 겹치는 사진. 없으면 주제별 사진."""
    title = (it["title"] + " " + it.get("title_ko", "")).lower()
    summ = (it.get("summary") or "")[:200].lower()
    best, files = 0, []
    for f, tags in PHOTO_TAGS:
        score = sum(3 if _hit(t, title) else 1 if _hit(t, summ) else 0 for t in tags)
        if score > best:
            best, files = score, [f]
        elif score == best and score:
            files.append(f)
    if not files:
        topic, _ = topic_of(it)
        files = PHOTOS.get(TOPIC_SLUG.get(topic, "ai")) or PHOTOS.get("ai") or []
    if not files:
        return None
    start = int((it.get("id") or "0")[:8] or "0", 16) % len(files)
    f = files[start]
    for k in range(len(files)):  # 같은 화면에 같은 사진이 두 번 나오지 않게
        cand = files[(start + k) % len(files)]
        if used is None or cand not in used:
            f = cand
            break
    if used is not None:
        used.add(f)
    return f


def thumb_html(it, base="", used=None, href=None, blank=True):
    topic, icon = topic_of(it)
    svg_icon = (f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" '
                f'stroke-linecap="round" stroke-linejoin="round">{icon}</svg>')
    if it.get("cover"):  # 에디터가 직접 올린 사진
        art = f'<img class="art" src="{base}editor/{esc(it["cover"])}" alt="" loading="lazy">'
    else:
        f = photo_for(it, used)
        art = (f'<img class="art" src="{base}photos/{f}" alt="" loading="lazy" width="960" height="540">' if f
               else cover_svg(it.get("id", ""), topic))
    tgt = ' target="_blank" rel="noopener"' if blank else ""
    tag = "" if it.get("cover") or it.get("editor") else f'<span class="tag">{svg_icon}{esc(topic)}</span>'
    return f'<a class="thumb" href="{esc(href or it["link"])}"{tgt} tabindex="-1" aria-hidden="true">{art}{tag}</a>'


def row_html(it, cats, with_cat=False):
    summ = f"<p>{esc(it['summary'])}</p>" if it.get("summary") else ""
    q = esc((it["title"] + " " + it.get("title_ko", "") + " " + it["source"] + " " + (it.get("summary") or "")).lower())
    return f'<article data-q="{q}"><h3 class="serif">{title_link(it)}</h3>{summ}{meta_html(it, cats, with_cat)}</article>'


def pager_html(p, n, href):
    """정적 페이지 번호. href(i)는 i번째(0부터) 페이지 주소."""
    if n <= 1:
        return ""
    show = {0, n - 1, p - 1, p, p + 1}
    h, last = [], -1
    if p > 0:
        h.append(f'<a href="{href(p - 1)}" aria-label="이전">‹</a>')
    for i in range(n):
        if i not in show:
            continue
        if i - last > 1:
            h.append("<span>…</span>")
        h.append(f'<a href="{href(i)}"{" class=on aria-current=page" if i == p else ""}>{i + 1}</a>')
        last = i
    if p < n - 1:
        h.append(f'<a href="{href(p + 1)}" aria-label="다음">›</a>')
    return '<nav class="pager" aria-label="페이지">' + "".join(h) + "</nav>"


# ---------------------------------------------------------------- 에디터 글

POSTS_DIR = ROOT / "posts"
_MD_IMG = re.compile(r"^!\[([^\]]*)\]\(([^)\s]+)\)$")
_MD_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_MD_BOLD = re.compile(r"\*\*(.+?)\*\*")
_BARE_URL = re.compile(r"(?<![\"=>])(https?://[^\s<]+)")


def load_posts():
    posts = []
    for f in sorted(POSTS_DIR.glob("*.json")):
        try:
            p = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if not re.fullmatch(r"[\w-]{1,40}", p.get("id", "")) or not p.get("title"):
            continue
        p["summary"] = post_summary(p.get("body", ""))
        posts.append(p)
    posts.sort(key=lambda p: p.get("date", ""), reverse=True)
    return posts


def post_summary(body, n=120):
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", body)
    t = _MD_LINK.sub(r"\1", t)
    t = re.sub(r"[#*>`-]+", " ", t)
    t = _WS.sub(" ", t).strip()
    return t if len(t) <= n else t[:n].rstrip() + "…"


def inline_md(s):
    s = esc(s)
    s = _MD_BOLD.sub(r"<strong>\1</strong>", s)
    s = _MD_LINK.sub(lambda m: f'<a href="{m.group(2)}" target="_blank" rel="noopener">{m.group(1)}</a>', s)
    return _BARE_URL.sub(lambda m: f'<a href="{m.group(1)}" target="_blank" rel="noopener">{m.group(1)}</a>', s)


def render_md(body):
    """에디터 글 본문: 빈 줄로 문단, ## 제목, - 목록, > 인용, ![](사진), **굵게**, [글](링크)."""
    out = []
    for block in re.split(r"\n\s*\n", body.replace("\r", "").strip()):
        lines = [l for l in block.split("\n") if l.strip()]
        if not lines:
            continue
        first = lines[0].strip()
        m = _MD_IMG.match(first)
        if m and len(lines) == 1:
            src = m.group(2)
            if src.startswith("img/") and re.fullmatch(r"img/[\w.-]+", src) or src.startswith("https://"):
                out.append(f'<img src="{esc(src)}" alt="{esc(m.group(1))}" loading="lazy">')
            continue
        if first.startswith("### "):
            out.append(f"<h3>{inline_md(first[4:])}</h3>")
            lines = lines[1:]
        elif first.startswith("## ") or first.startswith("# "):
            out.append(f"<h2>{inline_md(first.split(' ', 1)[1])}</h2>")
            lines = lines[1:]
        if not lines:
            continue
        if all(l.lstrip().startswith(("- ", "* ")) for l in lines):
            out.append("<ul>" + "".join(f"<li>{inline_md(l.lstrip()[2:])}</li>" for l in lines) + "</ul>")
        elif all(l.lstrip().startswith(">") for l in lines):
            out.append("<blockquote>" + "<br>".join(inline_md(l.lstrip()[1:].strip()) for l in lines) + "</blockquote>")
        else:
            out.append("<p>" + "<br>".join(inline_md(l) for l in lines) + "</p>")
    return "\n".join(out)


def post_item(p):
    """에디터 글을 표지·목록에서 기사처럼 다루기 위한 형태."""
    return {"id": hashlib.sha1(p["id"].encode()).hexdigest(), "title": p["title"], "link": f'editor/{p["id"]}.html',
            "source": "METAXIS 에디터", "category": "editor", "published": p.get("date"),
            "summary": p["summary"], "cover": p.get("cover", ""), "editor": True}


def post_card(p, base):
    it = post_item(p)
    href = base + it["link"]
    return (f'<article>{thumb_html(it, base, href=href, blank=False)}<h3 class="serif"><a href="{href}">{esc(p["title"])}</a></h3>'
            f'<p>{esc(p["summary"])}</p><div class="meta"><span>{ICON_CLOCK}{fmt_time(p.get("date"))}</span></div></article>')


def render_editor_pages(posts, cats, sc):
    out = SITE_DIR / "editor"
    (out / "img").mkdir(parents=True, exist_ok=True)
    for f in (POSTS_DIR / "img").glob("*") if (POSTS_DIR / "img").exists() else []:
        (out / "img" / f.name).write_bytes(f.read_bytes())
    pages = []
    n = max(1, -(-len(posts) // PER_PAGE))
    href = lambda i: "index.html" if i == 0 else f"{i + 1}.html"
    for pg in range(n):
        chunk = posts[pg * PER_PAGE:(pg + 1) * PER_PAGE]
        rows = "".join(
            f'<article>{thumb_html(post_item(p), "../", href=p["id"] + ".html", blank=False)}<div>'
            f'<h3 class="serif"><a href="{p["id"]}.html">{esc(p["title"])}</a></h3><p>{esc(p["summary"])}</p>'
            f'<div class="meta"><span>{ICON_CLOCK}{fmt_time(p.get("date"))}</span></div></div></article>' for p in chunk)
        rows = rows or '<p class="empty">아직 올라온 에디터 글이 없어요. 오른쪽 위 <b>운영자 글쓰기</b>를 눌러 첫 글을 올려 보세요.</p>'
        body = (f'<div class="ph"><h1 class="serif">에디터</h1><span>{esc(sc["name"])}가 직접 쓴 글 {len(posts)}편'
                f'<a class="btn-w" href="write.html">✎ 운영자 글쓰기</a></span></div>'
                f'<div class="elist">{rows}</div>{pager_html(pg, n, href)}')
        path = "editor/" + ("" if pg == 0 else f"{pg + 1}.html")
        title = f"에디터 글{'' if pg == 0 else f' {pg + 1}쪽'} | {sc['name']}"
        (out / href(pg)).write_text(page(title, body, "../", cats, search=False, path=path, active="editor",
                                         desc=f"{sc['name']} 에디터가 직접 쓴 AI 칼럼과 분석 글"), encoding="utf-8")
        pages.append(path)
    for p in posts:
        path = f"editor/{p['id']}.html"
        cover = f'{sc["url"]}/editor/{p["cover"]}' if p.get("cover") else f'{sc["url"]}/og.png'
        ld = [{"@context": "https://schema.org", "@type": "Article", "headline": p["title"][:110], "image": cover,
               "datePublished": p.get("date"), "dateModified": p.get("updated", p.get("date")),
               "author": {"@type": "Organization", "name": sc["name"]}, "publisher": {"@type": "Organization", "name": sc["name"]},
               "mainEntityOfPage": f'{sc["url"]}/{path}'}]
        body = (f'<article class="post"><h1 class="serif">{esc(p["title"])}</h1>'
                f'<div class="meta"><span>{esc(sc["name"])} 에디터</span><span>{ICON_CLOCK}{fmt_time(p.get("date"))}</span>'
                f'<button class="circle share" data-url="{sc["url"]}/{path}" data-title="{esc(p["title"])}" title="공유" aria-label="공유">{ICON_SHARE}</button></div>'
                f'<div class="body">{render_md(p.get("body", ""))}</div>'
                f'<p style="margin-top:40px"><a class="more" href="index.html">← 에디터 글 목록</a></p></article>')
        (out / f"{p['id']}.html").write_text(page(f"{p['title']} | {sc['name']}", body, "../", cats, search=False,
                                                  path=path, desc=p["summary"], jsonld=ld, og_type="article",
                                                  active="editor", image=cover), encoding="utf-8")
        pages.append(path)
    (out / "posts.json").write_text(json.dumps(
        [{k: p.get(k) for k in ("id", "title", "body", "cover", "images", "date", "updated")} for p in posts],
        ensure_ascii=False), encoding="utf-8")
    write = (WRITE_HTML.replace("{REPO}", esc(sc["repo"])))
    (out / "write.html").write_text(page(f"글쓰기 | {sc['name']}", write, "../", cats, search=False, path="editor/write.html",
                                         index=False, active="editor", script=WRITE_JS), encoding="utf-8")
    return pages


WRITE_HTML = """<div class="post" id="w" data-repo="{REPO}"><h1 class="serif">에디터 글쓰기</h1>
<section id="v-setup" hidden><p>이 기기에서 처음 쓰는 거라 한 번만 설정이 필요해요.</p>
<ol class="meta" style="display:block;line-height:1.9"><li><a class="more" href="https://github.com/settings/personal-access-tokens/new" target="_blank" rel="noopener">GitHub 토큰 만들기 페이지</a>를 열어요.</li>
<li>Repository access에서 <b>Only select repositories</b> → <b>ai-briefing</b> 선택</li>
<li>Permissions → Repository permissions → <b>Contents: Read and write</b></li>
<li>맨 아래 Generate token을 누르고 나온 토큰을 복사해서 아래에 붙여넣어요.</li></ol>
<p><input id="tok" class="inp" placeholder="github_pat_로 시작하는 토큰" autocomplete="off"></p>
<p><input id="pin1" class="inp pin" inputmode="numeric" maxlength="4" type="password" placeholder="비밀번호 4자리">
<input id="pin2" class="inp pin" inputmode="numeric" maxlength="4" type="password" placeholder="한 번 더"></p>
<p><button id="setup-go" class="btn">저장하고 시작</button> <span id="setup-msg" class="meta"></span></p>
<p class="meta">토큰은 이 기기 안에만 비밀번호로 잠가서 저장돼요. 비밀번호를 5번 틀리면 자동으로 지워져요.</p></section>
<section id="v-lock" hidden><p>비밀번호 4자리를 입력하세요.</p>
<p><input id="pin" class="inp pin" inputmode="numeric" maxlength="4" type="password" autocomplete="off" placeholder="••••"></p>
<p id="lock-msg" class="meta"></p><p><button id="reset" class="linkbtn">이 기기 로그인 정보 지우기</button></p></section>
<section id="v-list" hidden><p><button id="new" class="btn">새 글 쓰기</button> <span id="list-msg" class="meta"></span></p><ul id="plist" class="plist"></ul></section>
<section id="v-edit" hidden><p><input id="title" class="inp" placeholder="제목"></p>
<p><textarea id="body" class="inp" rows="16" placeholder="내용을 쓰세요. 빈 줄로 문단을 나눠요. ## 로 시작하면 소제목, **굵게**, [글자](https://주소) 는 링크가 돼요."></textarea></p>
<p><label class="btn ghost">사진 넣기<input id="file" type="file" accept="image/*" multiple hidden></label>
<span class="meta">사진은 커서 위치에 들어가요. 직접 찍었거나 사용 권리가 있는 사진만 올려주세요.</span></p>
<div id="thumbs" class="thumbs"></div>
<p><button id="publish" class="btn">게시하기</button> <button id="cancel" class="btn ghost">목록으로</button> <span id="edit-msg" class="meta"></span></p></section>
</div>
<style>.inp{width:100%;font:inherit;font-size:16px;padding:12px 14px;border:1px solid var(--line);border-radius:12px;background:var(--card);color:var(--text)}
.pin{width:160px;letter-spacing:.4em;text-align:center}.pin::placeholder{letter-spacing:normal}textarea.inp{line-height:1.7;resize:vertical}
.btn{font:inherit;font-weight:600;border:0;border-radius:99px;padding:10px 20px;background:var(--accent);color:#fff;cursor:pointer;display:inline-block}
.btn.ghost{background:var(--soft);color:var(--accent)}.btn:disabled{opacity:.5}.linkbtn{background:none;border:0;color:var(--muted);text-decoration:underline;cursor:pointer;font:inherit;font-size:13px}
.thumbs{display:flex;flex-wrap:wrap;gap:12px;margin:8px 0 16px}.thumbs figure{margin:0;width:140px}.thumbs img{width:140px;height:90px;object-fit:cover;border-radius:8px}
.thumbs label{font-size:12.5px;color:var(--muted)}.plist{list-style:none;padding:0}.plist li{padding:12px 0;border-bottom:1px solid var(--line)}
.plist button{font:inherit;font-size:13px;border:1px solid var(--line);background:var(--card);color:var(--text);border-radius:99px;padding:4px 12px;cursor:pointer;margin-left:6px}</style>"""


def render_home(data, cats, posts):
    d = datetime.fromisoformat(data["date"])
    items = data["items"]
    by_cat = {c: [] for c in cats}
    for it in items:
        by_cat.setdefault(it["category"], []).append(it)
    parts, used = [], set()
    hero, trend = pick_featured(items)
    if hero:  # 사진은 헤드라인과 주요 소식에만
        summ = f'<p class="sum">{esc(hero["summary"])}</p>' if hero.get("summary") else ""
        side = "".join(
            f'<div class="trend">{thumb_html(i, "", used)}<div><h3 class="serif">{title_link(i)}</h3>'
            + (f"<p>{esc(i['summary'])}</p>" if i.get("summary") else "")
            + f"{meta_html(i, cats, True)}</div></div>" for i in trend)
        parts.append(
            f'<div class="hero"><div><h2 class="serif">{title_link(hero)}<span class="badge">오늘의 헤드라인</span></h2>'
            f'{thumb_html(hero, "", used)}{meta_html(hero, cats, True)}{summ}'
            f'<div class="actions"><a class="read" href="{esc(hero["link"])}" target="_blank" rel="noopener">원문 보기 →</a>'
            f'<button class="circle share" data-url="{esc(hero["link"])}" data-title="{esc(hero["title"])}" title="공유" aria-label="공유">{ICON_SHARE}</button></div></div>'
            f'<aside><div class="side-h"><h2>주요 소식</h2><a href="#all" data-tab="all">전체 보기</a></div>{side}</aside></div>')
    if posts:
        parts.append('<div class="editor-h"><h2 class="serif">에디터 글</h2><a href="editor/">전체 보기 →</a></div>'
                     f'<div class="egrid">{"".join(post_card(p, "") for p in posts[:3])}</div>')
    info = f'{d.month}월 {d.day}일 ({WEEKDAYS[d.weekday()]}) · 총 {len(items)}건 · {esc(data["generated_at"][11:16])} 업데이트'
    parts.append('<div class="kw"><strong>오늘의 키워드</strong>'
                 + "".join(f"<span>#{esc(k)}</span>" for k in top_keywords(items))
                 + f'<span class="info">{info}</span></div>')
    tabs = ['<button class="on" data-cat="all" id="all">전체</button>']
    tabs += [f'<button data-cat="{c}">{esc(n)} {len(by_cat.get(c, []))}</button>' for c, n in cats.items()]
    parts.append('<div class="tabs">' + "".join(tabs) + "</div>")
    for c, name in cats.items():  # 나머지는 그림 없이 최신순 8개씩, 페이지를 넘겨 본다
        rows = sorted(by_cat.get(c, []), key=lambda x: x.get("published") or "", reverse=True)
        body = (f'<div class="rows" data-pg>{"".join(row_html(it, cats) for it in rows)}</div><div class="pager"></div>'
                if rows else '<p class="empty">오늘은 새 소식이 없습니다.</p>')
        parts.append(f'<section class="cat" data-cat="{c}" id="{c}"><h2 class="serif">{esc(name)}</h2>{body}'
                     f'<a class="more" href="{c}/">{esc(name)} 지난 기록 모두 보기 →</a></section>')
    sc = site_cfg()
    heading = f'<h1 class="eyebrow">{day_title(data["date"])} 오늘의 AI 브리핑</h1>'
    title = f"{sc['name']} | 오늘의 AI 뉴스·논문·정책 브리핑 · {day_title(data['date'])}"
    ld = day_jsonld(data, f"{sc['url']}/")
    ld.insert(0, {"@context": "https://schema.org", "@type": "WebSite", "name": sc["name"], "url": sc["url"] + "/",
                  "description": sc["description"], "inLanguage": "ko"})
    return page(title, heading + "\n".join(parts), "", cats, desc=day_desc(data, cats), path="", jsonld=ld, active="home")


def render_category(c, name, items, cats, sc):
    """카테고리 아카이브: 지금까지 모은 글 전부를 최신순 8개씩 페이지로 나눈다."""
    out = SITE_DIR / c
    out.mkdir(parents=True, exist_ok=True)
    n = max(1, -(-len(items) // PER_PAGE))
    href = lambda i: "index.html" if i == 0 else f"{i + 1}.html"
    paths = []
    for pg in range(n):
        chunk = items[pg * PER_PAGE:(pg + 1) * PER_PAGE]
        rows = "".join(row_html(it, cats) for it in chunk) or '<p class="empty">아직 모인 글이 없어요.</p>'
        body = (f'<div class="ph"><h1 class="serif">{esc(name)}</h1><span>지금까지 {len(items)}건 · {pg + 1}/{n}쪽</span></div>'
                f'<div class="rows">{rows}</div>{pager_html(pg, n, href)}')
        path = f"{c}/" + ("" if pg == 0 else f"{pg + 1}.html")
        title = f"AI {name}{'' if pg == 0 else f' {pg + 1}쪽'} | {sc['name']}"
        ld = [{"@context": "https://schema.org", "@type": "CollectionPage", "name": f"AI {name}", "url": f'{sc["url"]}/{path}',
               "inLanguage": "ko", "isPartOf": {"@type": "WebSite", "name": sc["name"], "url": sc["url"] + "/"},
               "mainEntity": {"@type": "ItemList", "itemListElement": [
                   {"@type": "ListItem", "position": k + 1, "url": it["link"], "name": it["title"]} for k, it in enumerate(chunk)]}}]
        desc = f"{sc['name']}가 모은 AI {name} {len(items)}건을 최신순으로 봅니다." + (f" 최신: {chunk[0]['title']}" if chunk else "")
        (out / href(pg)).write_text(page(title, body, "../", cats, search=False, path=path, desc=desc[:155], jsonld=ld,
                                         active=c), encoding="utf-8")
        paths.append(path)
    return paths


def day_title(date):
    d = datetime.fromisoformat(date)
    return f"{d.year}년 {d.month}월 {d.day}일 ({WEEKDAYS[d.weekday()]})"


def day_desc(data, cats):
    cnt = Counter(i["category"] for i in data["items"])
    parts = ", ".join(f"{n} {cnt[c]}건" for c, n in cats.items() if cnt.get(c))
    hero, _ = pick_featured(data["items"])
    s = f'{day_title(data["date"])} AI 브리핑: {parts}.' + (f' 헤드라인: {hero["title"]}' if hero else "")
    return s[:155]


def day_jsonld(data, url):
    sc = site_cfg()
    return [{"@context": "https://schema.org", "@type": "CollectionPage", "name": f'{day_title(data["date"])} AI 브리핑',
             "url": url, "inLanguage": "ko", "datePublished": data["date"], "dateModified": data.get("generated_at", data["date"]),
             "isPartOf": {"@type": "WebSite", "name": sc["name"], "url": sc["url"] + "/"},
             "mainEntity": {"@type": "ItemList", "numberOfItems": len(data["items"]),
                            "itemListElement": [{"@type": "ListItem", "position": n + 1, "url": it["link"], "name": it["title"]}
                                                for n, it in enumerate(data["items"][:30])]}}]


def write_feed(latest, sc):
    items = []
    for it in latest[:60]:
        pub = email.utils.format_datetime(datetime.fromisoformat(it["published"])) if it.get("published") else ""
        items.append(f'<item><title>{esc(it["title"])}</title><link>{esc(it["link"])}</link><guid isPermaLink="false">{it["id"]}</guid>'
                     f'<category>{esc(it["source"])}</category>{"<pubDate>" + pub + "</pubDate>" if pub else ""}'
                     f'<description>{esc(it.get("summary") or "")}</description></item>')
    now = email.utils.format_datetime(datetime.now(timezone.utc))
    xml = (f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{esc(sc["name"])} - AI 브리핑</title>'
           f'<link>{sc["url"]}/</link><description>{esc(sc["description"])}</description><language>ko</language>'
           f'<lastBuildDate>{now}</lastBuildDate>{"".join(items)}</channel></rss>')
    (SITE_DIR / "feed.xml").write_text(xml, encoding="utf-8")


def build(keep_days=None):
    cfg = load_config()
    cats = cfg["categories"]
    sc = site_cfg()
    files = sorted(DATA_DIR.glob("*.json"), reverse=True)
    if not files:
        print("[build] 데이터가 없습니다. 먼저 collect 를 실행하세요.", file=sys.stderr)
        return
    (SITE_DIR / "data").mkdir(parents=True, exist_ok=True)
    latest, every, seen = None, {c: [] for c in cats}, set()
    for i, f in enumerate(files):
        data = json.loads(f.read_text(encoding="utf-8"))
        (SITE_DIR / "data" / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")  # 원본 데이터도 함께 공개(백업·이전용)
        if i == 0:
            latest = data
        for it in data["items"]:  # 모든 날짜의 글을 카테고리별 아카이브로
            if it["id"] not in seen and it["category"] in every:
                seen.add(it["id"])
                every[it["category"]].append(it)
    posts = load_posts()
    (SITE_DIR / "index.html").write_text(render_home(latest, cats, posts), encoding="utf-8")
    paths = []
    for c, name in cats.items():
        items = sorted(every[c], key=lambda x: x.get("published") or "", reverse=True)
        paths += render_category(c, name, items, cats, sc)
    paths += render_editor_pages(posts, cats, sc)
    credits = "".join(
        f'<li><a href="{esc(c["landing"])}" target="_blank" rel="noopener">{esc(c["title"] or c["file"])}</a> '
        f'<span class="meta" style="display:inline">· {esc(c["creator"] or "작자 미상")} · {esc(c["source"])} · {esc(c["license"].upper())}</span></li>'
        for c in PHOTO_CREDITS)
    (SITE_DIR / "credits.html").write_text(page(
        f"사진 출처 | {sc['name']}",
        '<div class="post"><h1 class="serif">사진 출처</h1><p>기사 표지에 쓰는 사진은 모두 저작권이 없는 퍼블릭 도메인(CC0) 사진입니다. '
        '기사 원본의 사진은 사용하지 않습니다.</p><ul class="credits">' + credits + "</ul></div>",
        "", cats, search=False, path="credits.html"), encoding="utf-8")
    st = latest.get("status", [])
    lis = "".join(f'<li class="{"" if x["ok"] else "bad"}">{esc(x["name"])}: {str(x["count"]) + "건" if x["ok"] else "실패"}</li>' for x in st)
    contact = (f'<a class="more" href="mailto:{esc(sc["email"])}">{esc(sc["email"])}</a>' if sc.get("email")
               else "문의 창구는 곧 열립니다.")
    policy = f"""<div class="post"><h1 class="serif">정책</h1>
<h2 class="serif" style="font-size:21px;margin-top:30px">저작권 안내</h2>
<p>이 사이트에 소개된 모든 기사·논문·영상의 저작권은 원작자와 원 매체에 있습니다. {esc(sc["name"])}는 각 글마다 출처(매체·기관명)와 원문 링크를 분명히 밝히며,
요약은 원문 앞부분을 짧게 발췌한 것입니다. 전문은 반드시 원문 링크에서 확인해 주세요.</p>
<p>원문의 사진·썸네일은 가져오지 않으며, 표지 사진은 저작권이 없는 퍼블릭 도메인(CC0) 사진입니다. <a class="more" href="credits.html">사진 출처 보기 →</a></p>
<p>저작권 관련 문의나 삭제 요청이 있으면 바로 반영하겠습니다.</p>
<h2 class="serif" style="font-size:21px;margin-top:30px">개인정보</h2>
<p>이 사이트는 회원가입·댓글이 없고 방문자의 개인정보를 수집하지 않습니다.</p>
<h2 class="serif" style="font-size:21px;margin-top:30px" id="contact">문의</h2><p>{contact}</p>
<h2 class="serif" style="font-size:21px;margin-top:30px">수집 현황</h2>
<p class="meta" style="display:block">30분마다 자동 수집 · 마지막 업데이트 {esc(latest.get("generated_at", "")[:16].replace("T", " "))} · 소스 {sum(x["ok"] for x in st)}/{len(st)}개 정상 ·
<a href="{sc["url"]}/feed.xml">RSS 구독</a></p><ul class="st meta" style="display:block">{lis}</ul></div>"""
    (SITE_DIR / "policy.html").write_text(page(f"정책 | {sc['name']}", policy, "", cats, search=False, path="policy.html"), encoding="utf-8")
    paths.append("policy.html")
    (SITE_DIR / "404.html").write_text(page(
        f"페이지를 찾을 수 없어요 | {sc['name']}",
        f'<h1 class="serif" style="font-size:26px;margin:40px 0 8px">페이지를 찾을 수 없어요</h1><p><a class="read" href="{sc["url"]}/">오늘의 브리핑으로 가기 →</a></p>',
        base=sc["url"] + "/", cats=cats, search=False, path="404.html", index=False), encoding="utf-8")
    # 검색엔진용 파일
    now = latest.get("generated_at", latest["date"])
    urls = [(f"{sc['url']}/", now, "hourly", "1.0")]
    urls += [(f"{sc['url']}/{p}", now, "hourly" if p.endswith("/") else "daily", "0.7" if p.endswith("/") else "0.5") for p in paths]
    sm = "".join(f"<url><loc>{esc(u)}</loc><lastmod>{m}</lastmod><changefreq>{c}</changefreq><priority>{p}</priority></url>" for u, m, c, p in urls)
    (SITE_DIR / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sm}</urlset>', encoding="utf-8")
    (SITE_DIR / "robots.txt").write_text(f"User-agent: *\nAllow: /\nDisallow: /editor/write.html\n\nSitemap: {sc['url']}/sitemap.xml\n", encoding="utf-8")
    write_feed(latest["items"], sc)
    for f in (ROOT / "static").rglob("*"):  # 공유 이미지·아이콘·표지 사진
        if f.is_file():
            dst = SITE_DIR / f.relative_to(ROOT / "static")
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(f.read_bytes())
    if sc["domain"]:
        (SITE_DIR / "CNAME").write_text(sc["domain"] + "\n")
    (SITE_DIR / ".nojekyll").write_text("")
    print(f"[build] 홈 + 카테고리·에디터 {len(paths)}쪽 생성 → {SITE_DIR.relative_to(ROOT)}/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="all", choices=["all", "collect", "build", "backfill"])
    ap.add_argument("--since", help="backfill 시작 날짜(YYYY-MM-DD)")
    ap.add_argument("--fixtures", help="네트워크 대신 사용할 로컬 피드 폴더(테스트용)")
    a = ap.parse_args()
    if a.cmd == "backfill":
        backfill(datetime.fromisoformat(a.since).date(), a.fixtures)
        build()
        return
    if a.cmd in ("all", "collect"):
        collect(a.fixtures)
    if a.cmd in ("all", "build"):
        build()


if __name__ == "__main__":
    main()
