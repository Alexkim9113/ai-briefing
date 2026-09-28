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
CAT_CAP = {"talks": 3}    # 영상·강연은 하루 최신 3개만
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


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_SHORTS = {}


def is_youtube_short(link, fixtures=None):
    """세로형 쇼츠인지. 피드 주소에 /shorts/ 가 있거나, 쇼츠 주소로 열었을 때 일반 영상으로 넘어가지 않으면 쇼츠."""
    if "/shorts/" in link:
        return True
    m = re.search(r"(?:[?&]v=|youtu\.be/)([\w-]{11})", link)
    if not m or fixtures:
        return False
    vid = m.group(1)
    if vid not in _SHORTS:
        req = urllib.request.Request(f"https://www.youtube.com/shorts/{vid}", method="HEAD", headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.build_opener(_NoRedirect).open(req, timeout=15) as r:
                _SHORTS[vid] = r.status == 200
        except Exception:  # 일반 영상은 /watch 로 넘겨 보낸다(3xx)
            _SHORTS[vid] = False
    return _SHORTS[vid]


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
                if "youtube.com" in item["link"] and is_youtube_short(item["link"], fixtures):
                    continue  # 가로형 긴 영상만
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
    old = [i for i in old if not ("youtube.com" in i["link"] and is_youtube_short(i["link"], fixtures))]
    new = sorted(results, key=lambda x: x["published"] or "", reverse=True)
    today_seen, uniq = Deduper(), []
    for it in old + new:
        if today_seen.is_dup(it):
            continue
        today_seen.add(it)
        uniq.append(it)
    uniq.sort(key=lambda x: x["published"] or "", reverse=True)
    per_cat = Counter()  # 30분마다 쌓이므로 분야별 하루 최대 개수를 넘으면 오래된 것부터 뺀다
    uniq = [i for i in uniq if (per_cat.update([i["category"]]) or per_cat[i["category"]] <= CAT_CAP.get(i["category"], MAX_PER_CAT))]
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


# 연관어 묶음: #키워드를 누르거나 검색하면 같은 묶음의 말이 들어간 글까지 함께 찾는다(첫 말이 대표 이름)
KW_GROUPS = [
    ["인공지능", "artificial intelligence", "에이아이"],
    ["OpenAI", "오픈AI", "오픈에이아이", "ChatGPT", "챗GPT", "GPT", "Sam Altman", "올트먼", "알트만"],
    ["Anthropic", "앤트로픽", "Claude", "클로드"],
    ["Google", "구글", "Gemini", "제미나이", "DeepMind", "딥마인드", "Alphabet"],
    ["Nvidia", "엔비디아", "젠슨 황", "Jensen Huang"],
    ["Microsoft", "마이크로소프트", "MS", "Copilot", "코파일럿"],
    ["Meta", "메타", "Llama", "라마", "저커버그", "Zuckerberg"],
    ["Apple", "애플", "Siri", "시리"],
    ["Amazon", "아마존", "AWS"],
    ["xAI", "Grok", "그록", "머스크", "Musk", "Tesla", "테슬라"],
    ["삼성", "삼성전자", "Samsung"],
    ["SK", "SK하이닉스", "하이닉스", "SKT", "SK텔레콤", "Hynix"],
    ["네이버", "Naver", "하이퍼클로바"],
    ["카카오", "Kakao"],
    ["LG", "엘지", "엑사원", "EXAONE"],
    ["Trump", "트럼프", "White House", "백악관"],
    ["규제", "regulation", "regulate", "법안", "기본법", "AI Act", "입법"],
    ["정책", "policy", "정부", "government", "과기정통부", "과학기술정보통신부"],
    ["반도체", "chip", "chips", "semiconductor", "HBM", "GPU", "칩"],
    ["로봇", "robot", "robots", "robotics", "휴머노이드", "humanoid", "로보틱스"],
    ["에이전트", "agent", "agents", "agentic", "에이전틱"],
    ["생성형", "generative", "GenAI", "생성AI"],
    ["LLM", "언어모델", "language model", "파운데이션", "foundation model"],
    ["데이터센터", "data center", "data centers", "datacenter", "데이터 센터"],
    ["보안", "security", "cyber", "cybersecurity", "사이버", "해킹", "hack"],
    ["교육", "education", "학생", "students", "school", "학교", "대학"],
    ["의료", "health", "healthcare", "medical", "병원", "헬스케어", "신약"],
    ["투자", "investment", "funding", "raises", "투자유치", "valuation", "IPO", "상장"],
    ["스타트업", "startup", "startups", "창업"],
    ["CEO", "대표", "최고경영자"],
    ["KAIST", "카이스트"],
    ["서울대", "서울대학교", "SNU"],
    ["중국", "China", "Chinese", "DeepSeek", "딥시크", "알리바바", "Alibaba"],
    ["저작권", "copyright", "lawsuit", "소송"],
    ["일자리", "jobs", "고용", "layoffs", "해고", "노동"],
]
_KW_CANON = {w.lower(): g[0] for g in KW_GROUPS for w in g}


def kw_terms(k):
    """키워드 하나로 찾을 말들(연관어 묶음이 있으면 묶음 전체)."""
    g = next((g for g in KW_GROUPS if g[0] == _KW_CANON.get(k.lower())), None)
    return g or [k]


def top_keywords(items, n=12):
    c = Counter()
    for it in items:
        words = set(re.findall(r"[A-Za-z][A-Za-z0-9.+-]{1,}|[가-힣]{2,}", it["title"]))
        for w in words:
            wl = w.lower().strip(".-")
            if wl in STOP or len(wl) < 2:
                continue
            c[_KW_CANON.get(wl) or (w if not w.isascii() or w.isupper() or w[0].isupper() else wl)] += 1
    return [w for w, k in c.most_common(n) if k >= 2]


# ---------------------------------------------------------------- 사이트 생성

ICON_SHARE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="2.6"/><circle cx="6" cy="12" r="2.6"/><circle cx="18" cy="19" r="2.6"/><path d="M8.3 10.8l7.4-4.3M8.3 13.2l7.4 4.3"/></svg>'
ICON_THEME = ('<svg class="sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="4"/>'
              '<path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>'
              '<svg class="moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/></svg>')
CSS = """
:root{--bar:rgba(6,5,13,.86);--bar-text:#eceef6;--bg:#07061a;--card:#0f0d26;--text:#d9dcea;--heading:#f3f4fa;--muted:#9097b3;--line:#1f1c40;
--accent:#9ab8ff;--soft:#16143a;--shadow:0 8px 24px rgba(0,0,0,.45);--grad:linear-gradient(90deg,#12e3ff,#3b7bff 55%,#8b2cff);
--dot:rgba(255,255,255,.045);--glow:#1a1340;--field:rgba(255,255,255,.07);--field-line:rgba(255,255,255,.14);color-scheme:dark}
:root[data-theme=light]{--bar:rgba(255,255,255,.86);--bar-text:#15172b;--bg:#f6f7fb;--card:#fff;--text:#33374d;--heading:#111325;--muted:#646b84;--line:#e3e6f0;
--accent:#3552c9;--soft:#eef1fb;--shadow:0 6px 18px rgba(20,24,60,.08);--dot:rgba(20,24,60,.055);--glow:#e4e8ff;--field:#f1f3f9;--field-line:#e0e4ef;color-scheme:light}
@media (prefers-color-scheme:light){:root:not([data-theme=dark]){--bar:rgba(255,255,255,.86);--bar-text:#15172b;--bg:#f6f7fb;--card:#fff;--text:#33374d;--heading:#111325;--muted:#646b84;--line:#e3e6f0;
--accent:#3552c9;--soft:#eef1fb;--shadow:0 6px 18px rgba(20,24,60,.08);--dot:rgba(20,24,60,.055);--glow:#e4e8ff;--field:#f1f3f9;--field-line:#e0e4ef;color-scheme:light}}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(ellipse at 50% -10%,var(--glow) 0%,var(--bg) 55%) fixed,var(--bg);color:var(--text);font:16px/1.6 "Pretendard Variable",Pretendard,-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;-webkit-font-smoothing:antialiased;word-break:keep-all;overflow-wrap:break-word;-webkit-text-size-adjust:100%}
a{color:inherit;text-decoration:none}
.serif{font-family:"Pretendard Variable",Pretendard,sans-serif;letter-spacing:-.01em}
.wrap{max-width:1200px;margin:0 auto;padding:0 20px}
.bar{background:var(--bar);color:var(--bar-text);position:sticky;top:0;z-index:10;backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border-bottom:1px solid var(--line)}
.bar .wrap{display:flex;align-items:center;gap:28px;height:64px}
.logo{display:flex;align-items:center;gap:10px;font-size:20px;font-weight:800;letter-spacing:.14em;white-space:nowrap}.logo span{font-family:Unbounded,"Pretendard Variable",sans-serif;font-weight:700;letter-spacing:.08em;font-size:19px;background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
.logo svg{flex:none}
.bar nav{display:flex;gap:22px;flex:1;justify-content:center;font-size:14.5px;overflow-x:auto;scrollbar-width:none}
.bar nav a{opacity:.72;padding:4px 0;border-bottom:2px solid transparent;white-space:nowrap}
.bar nav a:hover,.bar nav a.on{opacity:1;border-image:var(--grad) 1}
.search{display:flex;align-items:center;gap:8px;background:var(--field);border:1px solid var(--field-line);border-radius:99px;padding:7px 14px;width:230px}
.search input{background:none;border:0;outline:0;color:var(--bar-text);font:inherit;font-size:14px;width:100%}
.search input::placeholder{color:var(--muted)}
.theme{flex:none;width:38px;height:38px;border-radius:50%;border:1px solid var(--field-line);background:var(--field);color:var(--bar-text);display:grid;place-items:center;cursor:pointer}
.theme svg{width:18px;height:18px}.toast{position:fixed;left:50%;bottom:28px;transform:translateX(-50%);background:var(--heading);color:var(--bg);padding:10px 18px;border-radius:99px;font-size:14px;font-weight:600;z-index:50;box-shadow:var(--shadow);white-space:nowrap}.theme .moon{display:none}:root[data-theme=light] .theme .sun{display:none}:root[data-theme=light] .theme .moon{display:block}
@media (prefers-color-scheme:light){:root:not([data-theme=dark]) .theme .sun{display:none}:root:not([data-theme=dark]) .theme .moon{display:block}}
.eyebrow{font-size:14px;font-weight:600;color:var(--muted);margin:26px 0 0;letter-spacing:.01em}
.hero{display:grid;grid-template-columns:1.12fr 1fr;gap:56px;padding:14px 0 28px}
.hero h2{font-size:32px;line-height:1.35;font-weight:700;letter-spacing:-.02em;color:var(--heading);margin:0 0 18px}
.badge{display:inline-block;vertical-align:middle;background:var(--grad);color:#fff;font:600 12px/1 "Pretendard Variable",Pretendard,sans-serif;padding:7px 12px;border-radius:99px;margin-left:10px;position:relative;top:-3px;box-shadow:var(--shadow)}
.thumb{position:relative;display:block;overflow:hidden;border-radius:16px;aspect-ratio:16/9;box-shadow:var(--shadow);background:var(--card)}
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
.trend h3{font-size:16.5px;line-height:1.45;font-weight:600;color:var(--heading);margin:0 0 4px}
.trend p{margin:0 0 4px;font-size:13px;color:var(--muted);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.cd{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--c);box-shadow:0 0 8px var(--c);margin-right:7px;vertical-align:.12em}
.kw{display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:18px 0;border-top:1px solid var(--line)}
.kw strong{font-size:14px;margin-right:4px}.kw span,.kwb{background:var(--soft);color:var(--accent);border-radius:99px;padding:3px 12px;font-size:13px}
.kwb{font:inherit;font-size:13px;border:2px solid transparent;cursor:pointer;padding:2px 11px}.kwb:hover{border-color:var(--line)}
.kwb.on{background:linear-gradient(var(--card),var(--card)) padding-box,var(--grad) border-box;color:var(--heading);font-weight:700}
.kwres{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:14px 0 0;padding:12px 16px;border-radius:14px;background:var(--soft);font-size:14px}
.kwres b{color:var(--heading)}.kwres em{font-style:normal;color:var(--muted);display:block;font-size:12.5px;margin-top:2px}
.kwres button{font:inherit;font-size:13px;border:1px solid var(--line);background:var(--card);color:var(--text);border-radius:99px;padding:6px 12px;cursor:pointer;white-space:nowrap}
.kw .info{background:none;color:var(--muted);margin-left:auto;padding:0}
.tabs{position:sticky;top:0;z-index:2;background:var(--bg);display:flex;gap:8px;overflow-x:auto;padding:12px 0;border-bottom:1px solid var(--line);scrollbar-width:none}
.tabs button{border:1px solid var(--line);background:var(--card);color:var(--text);border-radius:99px;padding:7px 16px;font:inherit;font-size:14px;cursor:pointer;white-space:nowrap}
.tabs button.on{background:linear-gradient(var(--card),var(--card)) padding-box,var(--grad) border-box;border:2px solid transparent;color:var(--heading);font-weight:700}
section.cat>h2{font-size:24px;font-weight:700;margin:34px 0 16px;color:var(--heading)}section.cat>h2::before,.ph h1::before,.editor-h h2::before{content:"";display:inline-block;width:5px;height:.85em;border-radius:3px;background:var(--c,var(--grad));margin-right:10px;vertical-align:-.06em}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:28px 24px}
.card h3{font-size:17px;line-height:1.5;font-weight:600;margin:14px 0 6px}
.card h3 a:hover,.trend h3 a:hover,.hero h2 a:hover{text-decoration:underline}
.card p{margin:0 0 8px;font-size:14px;color:var(--muted);display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.list{display:grid;grid-template-columns:1fr 1fr;gap:0 40px;margin-top:18px}
.row{padding:14px 0 12px;border-bottom:1px solid var(--line)}.row h3{margin:0 0 4px;font-size:16px}.row p{-webkit-line-clamp:2;margin-bottom:6px}
.empty{color:var(--muted);font-size:14px}
footer{margin-top:56px;line-height:1.7;padding-top:30px;padding-bottom:44px;border-top:1px solid var(--line);font-size:13px;color:var(--muted)}
footer.wrap{margin-top:64px}
.foot{display:flex;justify-content:space-between;gap:40px;flex-wrap:wrap}.fbrand p{margin:0}.fbrand .copy{font-size:12px;opacity:.85}
.flogo{display:inline-flex;align-items:center;gap:8px;font-weight:800;letter-spacing:.14em;color:var(--text);font-size:16px}.flogo svg{width:24px;height:24px}.flogo rect{stroke:var(--accent)}.flogo path{fill:var(--accent)}
.foot{align-items:center}.connect{display:flex;flex-wrap:wrap;align-items:center;gap:8px 22px}.connect h4{margin:0;font-size:12px;font-weight:600;letter-spacing:.1em;color:var(--muted);font-family:inherit}
.connect a{display:inline-flex;align-items:center;gap:9px;color:var(--text);font-size:15px;font-weight:500;letter-spacing:.01em}.connect a svg{width:17px;height:17px;flex:none}
.connect a[href]:hover{color:var(--accent)}.connect a[aria-disabled]{cursor:default}
details summary{cursor:pointer}ul.st{columns:3;padding-left:18px}ul.st .bad{color:#c2410c}
ul.days{list-style:none;padding:0;max-width:640px}ul.days li{padding:12px 0;border-bottom:1px solid var(--line)}ul.days a{color:var(--accent)}
[hidden]{display:none!important}
@media (max-width:960px){.hero{grid-template-columns:1fr;gap:32px}.grid{grid-template-columns:repeat(2,1fr)}
.bar .wrap{flex-wrap:wrap;height:auto;padding-top:12px;padding-bottom:12px;gap:10px 16px}
.bar nav{order:2;flex:1 0 100%;justify-content:flex-start;flex-wrap:wrap;overflow:visible;gap:4px 18px;margin:0;padding:2px 0}
.search{order:3;width:100%}.search input{font-size:16px}.theme{position:absolute;right:16px;top:10px}.site-share{right:62px}.bar .wrap{position:relative}.bar{position:relative}}
@media (max-width:600px){.connect{gap:6px 16px}.connect h4{display:none}.connect a{font-size:14px;gap:6px}.connect a svg{width:15px;height:15px}}
@media (max-width:600px){body{font-size:16px;line-height:1.65;background:radial-gradient(ellipse at 50% -10%,var(--glow) 0%,var(--bg) 55%) fixed,var(--bg)}.wrap{padding:0 16px}
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
.row{padding:14px 0}.meta{font-size:13px}
.trend:last-child{border-bottom:0;margin-bottom:0}.card h3,.rows h3,.trend h3{font-size:17px;line-height:1.5;letter-spacing:-.01em}
.card p,.rows p{font-size:15px;line-height:1.6}.rows article{padding:16px 0 14px}.hero p.sum{font-size:16.5px;line-height:1.75}
.kw span,.kwb{font-size:14px}
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
.pager .on{background:linear-gradient(var(--card),var(--card)) padding-box,var(--grad) border-box;border:2px solid transparent;color:var(--heading);font-weight:700}.pager span{border:0;cursor:default;min-width:20px;padding:0}
.more{display:inline-block;margin-top:12px;color:var(--accent);font-weight:600;font-size:14px}.more:hover{text-decoration:underline}
.ph{display:flex;align-items:baseline;justify-content:space-between;gap:12px;flex-wrap:wrap;margin:36px 0 8px}
.btn-w{display:inline-block;margin-left:14px;background:var(--grad);color:#fff;font-weight:600;font-size:14px;padding:8px 16px;border-radius:99px}.btn-w:hover{opacity:.9}
.ph h1{font-size:28px;font-weight:700;margin:0;color:var(--heading)}.ph span{color:var(--muted);font-size:14px}
.editor-h{display:flex;justify-content:space-between;align-items:baseline;margin:30px 0 14px}
.editor-h h2{font-size:22px;margin:0;color:var(--heading);font-weight:700}.editor-h a{font-size:13.5px;color:var(--muted)}
.egrid{display:grid;grid-template-columns:repeat(3,1fr);gap:24px;margin-bottom:26px}
.egrid h3{font-size:17px;line-height:1.5;margin:12px 0 4px;font-weight:600}.egrid p{margin:0 0 6px;font-size:14px;color:var(--muted);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.elist article{display:grid;grid-template-columns:220px 1fr;gap:20px;padding:18px 0;border-bottom:1px solid var(--line)}
.elist .thumb{border-radius:12px;box-shadow:none}.elist h3{font-size:19px;margin:0 0 6px;line-height:1.45}.elist p{margin:0 0 8px;color:var(--muted);font-size:14.5px}
.post{max-width:760px;margin:0 auto;padding-bottom:10px}
.post h1{font-size:34px;line-height:1.35;letter-spacing:-.02em;color:var(--heading);margin:40px 0 10px}
.post .meta{margin-bottom:26px}
.post .body{font-size:17.5px;line-height:1.85}
.post .body h2{font-size:24px;margin:36px 0 10px}.post .body h3{font-size:20px;margin:28px 0 8px}
.post .body img{display:block;max-width:100%;height:auto;border-radius:12px;margin:22px auto}
.post .body blockquote{margin:20px 0;padding:4px 18px;border-left:3px solid var(--accent);color:var(--muted)}
.post .body a{color:var(--accent);text-decoration:underline}
.post .body figure{margin:22px 0}.post .body figure img{margin:0 auto}.post .body hr{border:0;border-top:1px solid var(--line);margin:32px 0}
.post .body mark{background:#fff27a;color:#111;padding:0 2px;border-radius:2px}.post .body ul,.post .body ol{padding-left:1.4em}
.post .body [style*="background-color"]{color:#111;border-radius:2px;padding:0 1px}
.credits li{margin-bottom:6px;font-size:14px}
@media (max-width:960px){.egrid{grid-template-columns:1fr 1fr}}
@media (max-width:600px){.rows{grid-template-columns:1fr}
.egrid{grid-template-columns:1fr;gap:18px}.elist article{grid-template-columns:110px 1fr;gap:14px}.elist .thumb{aspect-ratio:1}.elist h3{font-size:16.5px}
.elist .thumb .tag{display:none}.ph h1{font-size:23px}.post h1{font-size:25px;margin-top:26px}.post .body{font-size:17px}
.pager a,.pager button{min-width:40px;height:40px}}
"""

JS = """
function toast(t){const d=document.createElement('div');d.className='toast';d.textContent=t;document.body.append(d);setTimeout(()=>d.remove(),2200);}
document.querySelectorAll('.site-share').forEach(b=>b.onclick=async e=>{e.stopImmediatePropagation();const u=b.dataset.url,t=b.dataset.title;
 try{if(navigator.share){await navigator.share({title:t,text:t+' | 국내외 AI 뉴스·논문·정책·영상',url:u});}else{await navigator.clipboard.writeText(u);toast('사이트 링크를 복사했어요');}}catch(err){}});
document.querySelectorAll('.theme:not(.site-share)').forEach(b=>b.onclick=()=>{const r=document.documentElement,
 dark=r.dataset.theme?r.dataset.theme==='dark':!matchMedia('(prefers-color-scheme: light)').matches,n=dark?'light':'dark';
 r.dataset.theme=n;try{localStorage.setItem('metaxis_theme',n);}catch(e){}});
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
const q=document.querySelector('.search input'),KWD=document.querySelector('.kw');
const KG=KWD&&KWD.dataset.kg?JSON.parse(KWD.dataset.kg):[];
function has(t,w){w=w.toLowerCase();if(!/^[ -~]+$/.test(w))return t.includes(w);let i=t.indexOf(w);
 while(i>=0){const a=t[i-1]||' ',b=t[i+w.length]||' ';if(!/[a-z0-9]/.test(a)&&!/[a-z0-9]/.test(b))return true;i=t.indexOf(w,i+1);}return false;}
function related(v){const l=v.toLowerCase();const g=KG.find(g=>g.some(w=>w.toLowerCase()===l));return g||null;}
function clearKw(){KWD&&KWD.querySelectorAll('.kwb').forEach(b=>b.classList.remove('on'));const r=document.querySelector('.kwres');if(r)r.remove();}
function filter(terms,label,plain){ // terms: 찾을 말들, 하나라도 들어간 글만 보인다
 if(!terms){boxes.forEach(b=>b._go(0));secs.forEach(s=>s.hidden=false);show('all');return 0;}
 let n=0;show('all');
 boxes.forEach(b=>{[...b.children].forEach(a=>{const t=plain?a.dataset.q:(a.dataset.k||a.dataset.q);a.hidden=!(plain?t.includes(plain):terms.some(w=>has(t,w)));if(!a.hidden)n++;});b.nextElementSibling.hidden=true;});
 secs.forEach(s=>s.hidden=!s.querySelector('article:not([hidden])'));return n;}
function kwBanner(label,terms,n){let r=document.querySelector('.kwres');if(!r){r=document.createElement('div');r.className='kwres';document.querySelector('.tabs').before(r);}
 const rel=terms.filter(t=>t.toLowerCase()!==label.toLowerCase()).slice(0,6);
 r.innerHTML=`<div><b>#${label.replace(/</g,'&lt;')}</b> 관련 글 ${n}건${rel.length?`<em>함께 찾은 말: ${rel.join(', ').replace(/</g,'&lt;')}</em>`:''}</div><button type="button">전체 보기</button>`;
 r.querySelector('button').onclick=()=>{clearKw();if(q)q.value='';filter(null);};}
if(KWD)KWD.querySelectorAll('.kwb').forEach(b=>b.onclick=()=>{
 if(b.classList.contains('on')){clearKw();filter(null);return;}
 clearKw();b.classList.add('on');if(q)q.value='';const terms=b.dataset.t.split('|'),label=b.textContent.slice(1);
 const n=filter(terms,label);kwBanner(label,terms,n);document.querySelector('.kwres').scrollIntoView({behavior:'smooth',block:'start'});});
if(q)q.oninput=()=>{clearKw();const v=q.value.trim();if(!v){filter(null);return;}
 const g=related(v);if(g){const n=filter(g,v);kwBanner(v,g,n);}else filter([v],v,v.toLowerCase());};
document.querySelectorAll('.share').forEach(b=>b.onclick=async()=>{const u=b.dataset.url;
 try{if(navigator.share)await navigator.share({url:u,title:b.dataset.title});else{await navigator.clipboard.writeText(u);b.title='링크 복사됨';}}catch(e){}});
"""

WRITE_JS = r"""
// 운영자 글쓰기: GitHub 토큰 없이 비밀번호 4자리만으로 쓴다.
// 글은 사이트의 공개키로 암호화해 무료 중계 서버(ntfy.sh)에 맡기고, 30분마다 도는 자동 작업이 풀어서 사이트에 올린다.
const W=document.getElementById('w'),TOPIC=W.dataset.topic,KEY=JSON.parse(W.dataset.key||'null'),enc=new TextEncoder();
const $=s=>document.querySelector(s),views=['#v-first','#v-lock','#v-list','#v-edit'];
let PIN=null,POSTS=[],STATUS={},cur=null,imgs={},seq=0;
function view(id){views.forEach(v=>$(v).hidden=v!==id);}
function msg(el,t,bad){const m=$(el);m.textContent=t;m.style.color=bad?'#e5484d':'';}
const b64=u8=>{let s='';for(let i=0;i<u8.length;i+=8192)s+=String.fromCharCode.apply(null,u8.subarray(i,i+8192));return btoa(s);};
function esc(s){return String(s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
const pinOk=p=>/^\d{4}$/.test(p);
function pending(){try{return JSON.parse(localStorage.getItem('metaxis_pending')||'[]');}catch(e){return [];}}
function savePending(a){try{localStorage.setItem('metaxis_pending',JSON.stringify(a.slice(-20)));}catch(e){}}
async function send(op,data){
 if(!KEY||!TOPIC)throw new Error('글쓰기 준비가 아직 안 됐어요. 30분 뒤 다시 시도해 주세요.');
 const ref=Math.random().toString(36).slice(2,10)+Date.now().toString(36);
 const pub=await crypto.subtle.importKey('jwk',KEY,{name:'RSA-OAEP',hash:'SHA-256'},false,['encrypt']);
 const k=crypto.getRandomValues(new Uint8Array(32)),iv=crypto.getRandomValues(new Uint8Array(12));
 const ak=await crypto.subtle.importKey('raw',k,'AES-GCM',false,['encrypt']);
 const ct=new Uint8Array(await crypto.subtle.encrypt({name:'AES-GCM',iv},ak,enc.encode(JSON.stringify({op,pin:PIN,ref,at:new Date().toISOString(),...data}))));
 const ek=new Uint8Array(await crypto.subtle.encrypt({name:'RSA-OAEP'},pub,k));
 const body=JSON.stringify({v:1,kid:KEY.kid,k:b64(ek),iv:b64(iv),ct:b64(ct)});
 const r=await fetch('https://ntfy.sh/'+TOPIC+'?filename=post.bin',{method:'PUT',body:new Blob([body])});
 if(!r.ok)throw new Error('보내지 못했어요 ('+r.status+')');
 const pd=pending();pd.push({ref,op,title:data.post?data.post.title:(data.title||''),at:Date.now()});savePending(pd);return ref;}
async function loadStatus(){try{STATUS=await (await fetch('status.json?'+Date.now())).json();}catch(e){STATUS={};}}
function showPending(){const done=Object.fromEntries((STATUS.results||[]).map(r=>[r.ref,r]));let pd=pending(),out=[];
 pd=pd.filter(x=>{const r=done[x.ref];if(r){out.push(`<li class="${r.ok?'':'bad'}">${r.ok?'✓':'✕'} ${esc(x.title||x.op)} · ${esc(r.msg)}</li>`);return false;}
  if(Date.now()-x.at>86400000*2)return false;out.push(`<li>⏳ ${esc(x.title||x.op)} · 사이트에 올리는 중이에요 (최대 30분)</li>`);return true;});
 savePending(pd);$('#pend').innerHTML=out.join('');}
async function start(){await loadStatus();PIN=null;try{PIN=sessionStorage.getItem('metaxis_pin');}catch(e){}
 if(!KEY){view('#v-lock');msg('#lock-msg','글쓰기 준비 중이에요. 30분 뒤 다시 열어 주세요.',1);return;}
 if(PIN)return openList();view(STATUS.pin_set?'#v-lock':'#v-first');}
$('#first-go').onclick=async()=>{const p1=$('#pin1').value,p2=$('#pin2').value;
 if(!pinOk(p1))return msg('#first-msg','비밀번호는 숫자 4자리예요.',1);if(p1!==p2)return msg('#first-msg','두 번 입력한 값이 달라요.',1);
 PIN=p1;msg('#first-msg','저장 중…');try{await send('setpin',{});try{sessionStorage.setItem('metaxis_pin',PIN);}catch(e){}openList();}
 catch(e){msg('#first-msg',e.message,1);}};
$('#pin').oninput=()=>{const p=$('#pin').value;if(!pinOk(p))return;PIN=p;$('#pin').value='';try{sessionStorage.setItem('metaxis_pin',PIN);}catch(e){}openList();};
$('#logout').onclick=()=>{try{sessionStorage.removeItem('metaxis_pin');}catch(e){}PIN=null;view(STATUS.pin_set?'#v-lock':'#v-first');};
async function openList(){view('#v-list');msg('#list-msg','');
 try{POSTS=await (await fetch('posts.json?'+Date.now())).json();}catch(e){POSTS=[];}
 showPending();renderList();
 const bad=(STATUS.results||[]).slice(-1)[0];if(bad&&!bad.ok&&/비밀번호/.test(bad.msg))msg('#list-msg','최근 요청이 비밀번호가 달라서 처리되지 않았어요. 다시 로그인해 주세요.',1);}
function renderList(){$('#plist').innerHTML=POSTS.map((p,i)=>`<li><b>${esc(p.title)}</b> <span class="meta">${(p.date||'').slice(0,10)}</span>
  <button data-e="${i}">수정</button> <button data-d="${i}">삭제</button></li>`).join('')||'<li class="meta">아직 쓴 글이 없어요.</li>';
 $('#plist').querySelectorAll('[data-e]').forEach(b=>b.onclick=()=>edit(POSTS[+b.dataset.e]));
 $('#plist').querySelectorAll('[data-d]').forEach(b=>b.onclick=()=>del(POSTS[+b.dataset.d]));}
function newId(){const d=new Date(),z=n=>String(n).padStart(2,'0');return `${d.getFullYear()}${z(d.getMonth()+1)}${z(d.getDate())}-${z(d.getHours())}${z(d.getMinutes())}${z(d.getSeconds())}`;}
$('#new').onclick=()=>edit(null);
function edit(p){cur=p?{...p}:{id:newId(),title:'',body:'',cover:'',images:[],date:''};imgs={};seq=(cur.images||[]).length;
 $('#title').value=cur.title;setBody(cur.body||'',cur.format);msg('#edit-msg','');drawThumbs();view('#v-edit');}
function drawThumbs(){const all=[...(cur.images||[]).map(n=>({n,src:'img/'+n})),...Object.entries(imgs).map(([n,src])=>({n,src}))];
 $('#thumbs').innerHTML=all.map(x=>`<figure><img src="${x.src}" alt=""><label><input type="radio" name="cover" value="${x.n}" ${cur.cover==='img/'+x.n?'checked':''}> 대표 사진</label></figure>`).join('');
 $('#thumbs').querySelectorAll('input').forEach(r=>r.onchange=()=>cur.cover='img/'+r.value);}
async function shrink(file){const bmp=await createImageBitmap(file),s=Math.min(1,1600/bmp.width),c=document.createElement('canvas');
 c.width=Math.round(bmp.width*s);c.height=Math.round(bmp.height*s);c.getContext('2d').drawImage(bmp,0,0,c.width,c.height);return c.toDataURL('image/jpeg',.82);}
// 본문 편집기: 사진이 실제 모습으로 보이고, 게시할 때 간단한 글 형식(마크다운)으로 바꿔 보낸다
const ED=$('#body');let RANGE=null;
document.execCommand('defaultParagraphSeparator',false,'p');
const saveSel=()=>{const s=getSelection();if(s.rangeCount&&ED.contains(s.anchorNode))RANGE=s.getRangeAt(0).cloneRange();};
document.addEventListener('selectionchange',saveSel);['mouseup','keyup','touchend'].forEach(ev=>ED.addEventListener(ev,saveSel));
const inl=t=>esc(t).replace(/\*\*(.+?)\*\*/g,'<b>$1</b>');
function fig(name,src){return `<figure contenteditable="false" data-n="${esc(name)}"><img src="${esc(src)}" alt=""><button type="button" aria-label="사진 빼기">✕</button></figure>`;}
function decorate(){ED.querySelectorAll('figure').forEach(f=>{const im=f.querySelector('img');if(!im)return f.remove();
 const src=im.getAttribute('src')||'';f.contentEditable='false';f.dataset.n=f.dataset.n||src.replace(/^img\//,'');
 if(!f.querySelector('button'))f.insertAdjacentHTML('beforeend','<button type="button" aria-label="사진 빼기">✕</button>');});}
function setBody(md,fmt){if(fmt==='html'){ED.innerHTML=md;decorate();return;}ED.innerHTML=md.replace(/\r/g,'').split(/\n\s*\n/).map(b=>b.trim()).filter(Boolean).map(b=>{
  const m=b.match(/^!\[[^\]]*\]\((img\/[\w.-]+|https:\/\/[^)\s]+)\)$/);if(m)return fig(m[1].replace(/^img\//,''),m[1]);
  if(/^#{1,3} /.test(b))return `<h2>${inl(b.replace(/^#{1,3} /,''))}</h2>`;return `<p>${b.split('\n').map(inl).join('<br>')}</p>`;}).join('')||'';}
function txt(el){let o='';el.childNodes.forEach(n=>{if(n.nodeType===3)o+=n.textContent;else if(n.nodeName==='BR')o+='\n';
  else if(/^(B|STRONG)$/.test(n.nodeName)){const t=txt(n).trim();o+=t?`**${t}**`:'';}else o+=txt(n);});return o;}
function getBody(){const c=ED.cloneNode(true); // 편집용 표시(✕ 버튼, 미리보기 사진)를 걷어내고 게시용 HTML로
 c.querySelectorAll('figure').forEach(f=>{const n=f.dataset.n;f.replaceWith(Object.assign(document.createElement('figure'),{innerHTML:`<img src="${/^https:/.test(n)?n:'img/'+n}" alt="">`}));});
 c.querySelectorAll('[contenteditable]').forEach(e=>e.removeAttribute('contenteditable'));
 const base=getComputedStyle(ED).color; // 편집기가 저절로 붙인 기본 글자색·inherit 값은 지워서 밝은/어두운 화면 모두에서 읽히게
 c.querySelectorAll('[style]').forEach(e=>{const st=e.style;for(const k of [...st])if(st.getPropertyValue(k)==='inherit')st.removeProperty(k);
  if(st.color===base)st.removeProperty('color');if(!e.getAttribute('style').trim())e.removeAttribute('style');
  if(e.nodeName==='SPAN'&&!e.attributes.length)e.replaceWith(...e.childNodes);});
 [...c.childNodes].forEach(n=>{if(n.nodeType===3&&n.textContent.trim()){const p=document.createElement('p');n.replaceWith(p);p.append(n);}});
 return c.innerHTML.replace(/<p><br><\/p>/g,'').trim();}
ED.addEventListener('click',e=>{if(e.target.matches('figure button')){const f=e.target.closest('figure');const n=f.dataset.n;f.remove();
  if(cur.cover==='img/'+n&&!ED.querySelector('figure'))cur.cover='';drawThumbs();}});
ED.addEventListener('paste',e=>{e.preventDefault();document.execCommand('insertText',false,(e.clipboardData||window.clipboardData).getData('text/plain'));});
function placeAt(){ED.focus();const s=getSelection();s.removeAllRanges();
 if(RANGE&&ED.contains(RANGE.startContainer))s.addRange(RANGE);else{const r=document.createRange();r.selectNodeContents(ED);r.collapse(false);s.addRange(r);}}
function insertFigure(name,src){placeAt();const s=getSelection(),r=s.getRangeAt(0);
 let blk=r.startContainer;while(blk&&blk.parentNode!==ED)blk=blk.parentNode;
 const tmp=document.createElement('div');tmp.innerHTML=fig(name,src);const f=tmp.firstChild,after=document.createElement('p');after.innerHTML='<br>';
 if(blk&&blk!==ED){ // 커서가 문단 가운데면 문단을 둘로 나눠 그 사이에 사진을 넣는다
  const tail=document.createRange();tail.setStart(r.startContainer,r.startOffset);tail.setEndAfter(blk.lastChild||blk);
  const rest=tail.extractContents();const restText=rest.textContent.trim();
  blk.after(f);if(restText){const p=document.createElement('p');p.append(...(rest.firstChild&&rest.firstChild.nodeName===blk.nodeName?rest.firstChild.childNodes:rest.childNodes));f.after(p);RANGE=null;placeCaret(p,true);return;}
  f.after(after);if(!blk.textContent.trim()&&!blk.querySelector('figure'))blk.remove();}
 else{ED.append(f,after);}
 placeCaret(after,true);}
function placeCaret(el,start){const r=document.createRange();r.selectNodeContents(el);r.collapse(start);const s=getSelection();s.removeAllRanges();s.addRange(r);RANGE=r.cloneRange();}
$('#file').onchange=async e=>{for(const f of e.target.files){if(!f.type.startsWith('image/'))continue;
 const name=`${cur.id}-${++seq}.jpg`;imgs[name]=await shrink(f);if(!cur.cover)cur.cover='img/'+name;insertFigure(name,imgs[name]);}
 e.target.value='';drawThumbs();};
// 서식 도구: 버튼을 눌러도 글자 선택이 풀리지 않게 한다
const T=$('#tools');['pointerdown','mousedown','touchstart'].forEach(ev=>T.addEventListener(ev,saveSel,true));T.addEventListener('mousedown',e=>{if(e.target.closest('button'))e.preventDefault();});
T.addEventListener('pointerdown',e=>{if(e.target.closest('button')&&e.pointerType!=='mouse')e.preventDefault();});
const exec=(c,v)=>{placeAt();document.execCommand('styleWithCSS',false,true);document.execCommand(c,false,v);ED.focus();syncTools();};
T.querySelectorAll('[data-c]').forEach(b=>b.onclick=()=>exec(b.dataset.c));
T.querySelectorAll('[data-b]').forEach(b=>b.onclick=()=>{placeAt();const t=b.dataset.b,now=(document.queryCommandValue('formatBlock')||'').toLowerCase();
 document.execCommand('formatBlock',false,now===t?'p':t);syncTools();});
const pop=id=>{['#p-hl','#p-fc'].forEach(p=>{if(p!==id)$(p).hidden=true;});$(id).hidden=!$(id).hidden;};
$('#t-hl').onclick=()=>pop('#p-hl');$('#t-fc').onclick=()=>pop('#p-fc');
T.querySelectorAll('[data-hl]').forEach(b=>b.onclick=()=>{exec('hiliteColor',b.dataset.hl);$('#p-hl').hidden=true;});
T.querySelectorAll('[data-fc]').forEach(b=>b.onclick=()=>{exec('foreColor',b.dataset.fc||getComputedStyle(ED).color);$('#p-fc').hidden=true;});
$('#t-font').onchange=e=>{exec('fontName',e.target.value||'Pretendard Variable');};
$('#t-size').onchange=e=>{if(e.target.value)exec('fontSize',e.target.value);e.target.value='';};
$('#t-link').onclick=()=>{const u=prompt('연결할 주소(https://…)를 넣어 주세요');if(u&&/^https?:\/\//i.test(u.trim()))exec('createLink',u.trim());};
function syncTools(){['bold','italic','underline','strikeThrough','justifyLeft','justifyCenter','justifyRight','justifyFull','insertUnorderedList','insertOrderedList'].forEach(c=>{
  const b=T.querySelector(`[data-c="${c}"]`);if(b){let on=false;try{on=document.queryCommandState(c);}catch(e){}b.classList.toggle('on',on);}});}
document.addEventListener('selectionchange',()=>{if(ED.contains(getSelection().anchorNode))syncTools();});
$('#cancel').onclick=()=>{view('#v-list');renderList();};
$('#publish').onclick=async()=>{const title=$('#title').value.trim(),body=getBody();
 if(!title||!body)return msg('#edit-msg','제목과 내용을 모두 써 주세요.',1);
 const used=n=>body.includes('img/'+n)||cur.cover==='img/'+n,up={};
 const keep=(cur.images||[]).filter(used);
 for(const [n,d] of Object.entries(imgs))if(used(n)){up[n]=d.split(',')[1];keep.push(n);}
 if(cur.cover&&!keep.includes(cur.cover.slice(4)))cur.cover=keep.length?'img/'+keep[0]:'';
 const post={id:cur.id,title,body,format:'html',cover:cur.cover,images:keep,date:cur.date||new Date().toISOString(),updated:new Date().toISOString()};
 $('#publish').disabled=true;msg('#edit-msg','보내는 중…');
 try{await send('publish',{post,upload:up});msg('#edit-msg','보냈어요! 30분 안에 사이트에 올라가요.');
  const i=POSTS.findIndex(p=>p.id===post.id);if(i<0)POSTS.unshift(post);cur=post;imgs={};
  setTimeout(()=>{openList();},1400);}
 catch(e){msg('#edit-msg',e.message,1);}finally{$('#publish').disabled=false;}};
async function del(p){if(!confirm(`'${p.title}' 글을 삭제할까요?`))return;msg('#list-msg','보내는 중…');
 try{await send('delete',{id:p.id,title:p.title});msg('#list-msg','삭제 요청을 보냈어요. 30분 안에 사이트에서 사라져요.');showPending();}
 catch(e){msg('#list-msg',e.message,1);}}
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
           "<rect width=%2232%22 height=%2232%22 rx=%227%22 fill=%22%2306050d%22/>"
           "<circle cx=%2216%22 cy=%2216%22 r=%229%22 fill=%22none%22 stroke=%22%233b7bff%22 stroke-width=%221.6%22/>"
           "<path d=%22M16 3v26%22 stroke=%22%2312e3ff%22 stroke-width=%222%22/><path d=%22M3 16h26%22 stroke=%22%238b2cff%22 stroke-width=%222%22/></svg>")


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
            "email": s.get("contact_email", ""), "instagram": s.get("instagram", ""), "x": s.get("x", ""),
            "editor_topic": s.get("editor_topic", "")}


SOCIAL_ICONS = {
    "Contact": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/></svg>',
    "Instagram": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1" fill="currentColor" stroke="none"/></svg>',
    "X": '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.8 3h3.1l-6.8 7.8L22 21h-6.3l-4.9-6.4L5.2 21H2.1l7.3-8.3L1.8 3h6.4l4.4 5.9L17.8 3zm-1.1 16.2h1.7L7.4 4.7H5.6l11.1 14.5z"/></svg>',
    "Policy": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5M9 13h7M9 17h5"/></svg>',
}


def connect_links(sc, base):
    """하단 CONNECT: Contact · Instagram · X · Policy. 주소가 아직 없는 SNS는 아이콘만 보이고 링크는 걸리지 않는다."""
    contact = f'mailto:{sc["email"]}' if sc.get("email") else f"{base}policy.html#contact"
    links = [("Contact", contact, False), ("Instagram", sc.get("instagram"), True), ("X", sc.get("x"), True),
             ("Policy", f"{base}policy.html", False)]
    out = []
    for n, u, ext in links:
        inner = f'{SOCIAL_ICONS[n]}<span>{n}</span>'
        if u:
            out.append(f'<a href="{esc(u)}"{" target=_blank rel=noopener" if ext else ""}>{inner}</a>')
        else:
            out.append(f'<a aria-disabled="true" title="준비 중">{inner}</a>')
    return "".join(out)


def page(title, body, base="", cats=None, search=True, desc=None, path="", jsonld=None, og_type="website", index=True,
         active="", script="", image=None, head=""):
    sc = site_cfg()
    canonical = f'{sc["url"]}/{path}'
    desc = desc or sc["description"]
    on = lambda k: ' class="on" aria-current="page"' if k == active else ""
    nav = f'<a href="{base}home.html"{on("home")}>홈</a>'
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
<meta name="theme-color" content="#06050d" media="(prefers-color-scheme: dark)"><meta name="theme-color" content="#ffffff" media="(prefers-color-scheme: light)"><script>try{{var m=localStorage.getItem("metaxis_theme");if(m)document.documentElement.dataset.theme=m}}catch(e){{}}</script>{verify}
<link rel="icon" href="{FAVICON}"><link rel="apple-touch-icon" href="{base}apple-touch-icon.png">
<link rel="alternate" type="application/rss+xml" title="{esc(sc["name"])} RSS" href="{sc["url"]}/feed.xml">
<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Unbounded:wght@500;700;800&amp;text=METAXIS&amp;display=swap">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">
{head}<style>{CSS}</style>{ld}</head><body>
<header class="bar"><div class="wrap"><a class="logo serif" href="{base}index.html" title="처음 화면" aria-label="{esc(sc["name"])} 홈"><span>{esc(sc["name"])}</span></a><nav aria-label="주요 메뉴">{nav}</nav>{box}<button class="theme site-share" type="button" aria-label="사이트 공유하기" title="사이트 공유하기" data-url="{sc["url"]}/" data-title="{esc(sc["name"])}">{ICON_SHARE}</button><button class="theme" type="button" aria-label="밝은 화면·어두운 화면 전환">{ICON_THEME}</button></div></header>
<main class="wrap">{body}</main>
<footer class="wrap foot"><div class="fbrand"><p class="copy">© {datetime.now(KST).year} {esc(sc["name"])}. 기사·논문·영상 등 이 사이트에 소개된 모든 정보의 저작권은 원작자에게 있습니다.</p></div>
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
    "투자·기업": ("#0f2419", ["#22c55e", "#86efac", "#15803d"]), "언어모델": ("#0d1030", ["#3b7bff", "#12e3ff", "#8b2cff"]),
    "신제품·서비스": ("#2b1208", ["#fb923c", "#fca5a5", "#c2410c"]), "연구": ("#141a33", ["#6366f1", "#a5b4fc", "#312e81"]),
    "영상": ("#2b0d0d", ["#ef4444", "#fca5a5", "#7f1d1d"]), "AI": ("#0b0a24", ["#8b2cff", "#12e3ff", "#3b7bff"]),
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
        parts.append(f"<span style=\"--c:{INTRO_COLORS.get(it['category'], DEFAULT_TINT)}\"><i class=\"cd\"></i>{esc(cats.get(it['category'], ''))}</span>")
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


PHOTO_TEXT = set()  # 사진 안에 영어 글자가 보이는 사진(한국어 기사에는 쓰지 않는다)


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
    PHOTO_TEXT.update(c["file"] for c in credits if c.get("text"))
    for c in credits:  # 파일 이름 앞부분(chip-3.jpg → chip)으로도 묶는다
        by.setdefault("#" + c["file"].rsplit("-", 1)[0], []).append(c["file"])
    return credits, by, tagged


PHOTO_CREDITS, PHOTOS, PHOTO_TAGS = load_photos()
# 카테고리마다 어울리는 사진 묶음(기사 내용과 맞는 사진이 없을 때 쓴다)
CAT_PHOTOS = {"papers": ["research", "brain", "code", "xray"], "policy": ["law", "capitol", "meeting"],
              "talks": ["event", "voice", "meeting"], "news_global": ["ai", "code", "chip"], "news_ko": ["ai", "seoul", "code"]}
# 자동으로 새 사진을 모을 때 쓰는 영어 검색어(묶음 이름 → 검색어). 태그·주제는 같은 묶음의 기존 사진에서 가져온다.
PHOTO_QUERIES = {
    "ai": "abstract technology", "art": "art painting", "brain": "brain neuroscience", "camera": "camera lens",
    "capitol": "government building", "car": "car road", "chess": "chess", "chip": "circuit board",
    "code": "programming code screen", "deal": "handshake business", "drone": "drone", "edu": "classroom students",
    "energy": "solar panels", "event": "conference stage", "farm": "farm field", "hospital": "hospital",
    "invest": "stock market", "kids": "children learning", "launch": "smartphone", "law": "law justice",
    "llm": "laptop typing", "media": "newspaper", "medical": "doctor", "meeting": "business meeting",
    "military": "military", "money": "money", "music": "music studio", "pills": "medicine pills",
    "plane": "airplane", "power": "power lines", "research": "laboratory science", "robot": "robot",
    "security": "cyber security lock", "seoul": "seoul city", "ship": "cargo ship", "shop": "shopping store",
    "space": "space satellite", "video": "video camera film", "voice": "microphone", "vr": "virtual reality headset",
    "wind": "wind turbine", "write": "writing notebook", "xray": "x-ray"}
PHOTO_CAP = 15      # 묶음마다 최대 사진 수
PHOTO_DAILY = 6     # 하루에 새로 모으는 사진 수


def _hit(tag, text):
    if tag.isascii() and len(tag) <= 3:
        return re.search(r"(?<![a-z0-9])" + re.escape(tag) + r"(?![a-z0-9])", text) is not None
    return tag in text


def has_text(path):
    """사진 속에 영어 단어가 읽히는지 글자 인식(tesseract)으로 확인. 도구가 없으면 확인하지 않는다."""
    import csv
    import io
    import subprocess
    try:
        out = subprocess.run(["tesseract", str(path), "stdout", "--psm", "11", "tsv"],
                             capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    for r in csv.DictReader(io.StringIO(out), delimiter="\t", quoting=csv.QUOTE_NONE):
        try:
            conf = float(r.get("conf") or -1)
        except ValueError:
            conf = -1
        if conf >= 70 and re.fullmatch(r"[A-Za-z]{3,}", (r.get("text") or "").strip()):
            return True
    return False


def collect_photos():
    """퍼블릭 도메인(CC0) 사진을 Openverse에서 하루 몇 장씩 자동으로 모은다.
    워터마크가 없는 큐레이션 사이트(StockSnap, WordPress 사진 디렉터리)만 쓰고, 기사 원본 사진은 가져오지 않는다."""
    try:
        from PIL import Image
    except ImportError:
        print("Pillow가 없어 사진 수집을 건너뜀")
        return 0
    import io
    import zlib
    folder = ROOT / "static" / "photos"
    credits = json.loads((folder / "credits.json").read_text(encoding="utf-8"))
    seen = {c.get("landing") for c in credits}
    groups = {}
    for c in credits:
        groups.setdefault(c["file"].rsplit("-", 1)[0], []).append(c)
    day = datetime.now(KST).timetuple().tm_yday
    order = sorted(PHOTO_QUERIES, key=lambda g: (len(groups.get(g, [])), (zlib.crc32(g.encode()) + day) % 97))
    added = 0
    for g in order:
        if added >= PHOTO_DAILY:
            break
        if len(groups.get(g, [])) >= PHOTO_CAP:
            continue
        q = urllib.parse.quote(PHOTO_QUERIES[g])
        url = (f"https://api.openverse.org/v1/images/?q={q}&license=cc0,pdm&source=stocksnap,wordpress"
               f"&aspect_ratio=wide&size=large&page_size=20")  # 로그인 없이 쓰면 한 번에 20장까지
        try:
            res = json.loads(fetch(url)).get("results", [])
        except Exception as e:
            print("사진 검색 실패", g, e)
            if "429" in str(e):  # 너무 자주 물어봤다는 뜻이라 오늘은 멈춘다
                break
            continue
        finally:
            time.sleep(4)
        for r in res:
            w, h = r.get("width") or 0, r.get("height") or 0
            if (r.get("license") not in ("cc0", "pdm") or r.get("source") not in ("stocksnap", "wordpress")
                    or r.get("foreign_landing_url") in seen or w < 1200 or not h or not 1.3 <= w / h <= 2.2):
                continue
            try:
                im = Image.open(io.BytesIO(fetch(r["url"]))).convert("RGB")
            except Exception as e:
                print("사진 받기 실패", r.get("url"), e)
                continue
            W, H = im.size
            ch = min(H, W * 9 // 16)
            cw = ch * 16 // 9
            im = im.crop(((W - cw) // 2, (H - ch) // 2, (W - cw) // 2 + cw, (H - ch) // 2 + ch)).resize((960, 540), Image.LANCZOS)
            n = 0
            while (folder / f"{g}-{n}.jpg").exists():
                n += 1
            name = f"{g}-{n}.jpg"
            im.save(folder / name, "JPEG", quality=82, optimize=True, progressive=True)
            base = (groups.get(g) or [{}])[0]
            c = {"file": name, "topic": base.get("topic", ""), "tags": base.get("tags", []),
                 "title": (r.get("title") or "")[:120], "creator": r.get("creator") or "", "license": r["license"],
                 "source": r["source"], "landing": r["foreign_landing_url"]}
            if has_text(folder / name):  # 글자가 보이면 표시만 해 두고 해외 기사에만 쓴다
                c["text"] = True
            credits.append(c)
            groups.setdefault(g, []).append(c)
            seen.add(c["landing"])
            added += 1
            print("새 사진", name, c["landing"])
            break
    if added:
        (folder / "credits.json").write_text(json.dumps(credits, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"사진 {added}장 추가 (전체 {len(credits)}장)")
    return added


def photo_for(it, used=None):
    """기사 제목(번역 제목 포함)·요약과 사진 태그가 가장 많이 겹치는 사진. 없으면 주제별 사진."""
    title = (it["title"] + " " + it.get("title_ko", "")).lower()
    summ = (it.get("summary") or "")[:200].lower()
    best, files = 0, []
    ko = re.search("[가-힣]", it["title"]) is not None
    ok = lambda f: not (ko and f in PHOTO_TEXT)
    for f, tags in PHOTO_TAGS:
        if not ok(f):
            continue
        score = sum(3 if _hit(t, title) else 1 if _hit(t, summ) else 0 for t in tags)
        if score > best:
            best, files = score, [f]
        elif score == best and score:
            files.append(f)
    if not files:
        topic, _ = topic_of(it)
        files = PHOTOS.get(TOPIC_SLUG.get(topic, "")) or []
        if not files:  # 뚜렷한 주제가 없으면 카테고리에 어울리는 사진
            files = [f for g in CAT_PHOTOS.get(it.get("category"), ["ai"]) for f in PHOTOS.get("#" + g, [])]
        files = [f for f in (files or PHOTOS.get("ai") or []) if ok(f)] or [f for f in PHOTOS.get("ai", []) if ok(f)]
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
    k = (it["title"] + " " + it.get("title_ko", "") + " " + (it.get("summary") or "")).lower()
    q = esc(k + " " + it["source"].lower())
    return f'<article data-q="{q}" data-k="{esc(k)}"><h3 class="serif">{title_link(it)}</h3>{summ}{meta_html(it, cats, with_cat)}</article>'


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


# 에디터에서 고를 수 있는 무료 글꼴(모두 Google Fonts, SIL 오픈 폰트 라이선스): 이름 → 불러올 주소 조각
POST_FONTS = {"Nanum Myeongjo": "Nanum+Myeongjo:wght@400;700", "Noto Serif KR": "Noto+Serif+KR:wght@400;700",
              "Gowun Batang": "Gowun+Batang:wght@400;700", "Nanum Gothic": "Nanum+Gothic:wght@400;700",
              "Gowun Dodum": "Gowun+Dodum", "IBM Plex Sans KR": "IBM+Plex+Sans+KR:wght@400;700",
              "Do Hyeon": "Do+Hyeon", "Black Han Sans": "Black+Han+Sans", "Nanum Pen Script": "Nanum+Pen+Script",
              "Gaegu": "Gaegu:wght@400;700"}


def font_links(fams):
    return "".join(f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family={POST_FONTS[f]}&amp;display=swap">'
                   for f in fams if f in POST_FONTS)


_SAFE_TAGS = {"p", "div", "br", "h2", "h3", "b", "strong", "i", "em", "u", "s", "strike", "span", "mark", "a", "ul", "ol",
              "li", "blockquote", "hr", "figure", "img", "figcaption", "sub", "sup"}
_VOID = {"br", "hr", "img"}
_COLOR = re.compile(r"#[0-9a-f]{3,8}|rgba?\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*(,\s*[\d.]+\s*)?\)|transparent", re.I)
_SIZES = {"small", "medium", "large", "x-large", "xx-large", "xxx-large"}


def _safe_style(style):
    out = []
    for decl in style.split(";"):
        if ":" not in decl:
            continue
        k, v = (x.strip().lower() for x in decl.split(":", 1))
        v = v.replace("!important", "").strip()
        if k == "font-family":
            fam = v.split(",")[0].strip().strip("'\"")
            match = next((f for f in POST_FONTS if f.lower() == fam), None)
            if match:
                out.append(f"font-family:'{match}'")
        elif k == "font-size" and (v in _SIZES or re.fullmatch(r"(1[2-9]|[2-4]\d)px", v)):
            out.append(f"font-size:{v}")
        elif k in ("color", "background-color") and _COLOR.fullmatch(v):
            out.append(f"{k}:{v}")
        elif k == "text-align" and v in ("left", "center", "right", "justify", "start", "end"):
            out.append(f"text-align:{v}")
        elif k in ("text-decoration", "text-decoration-line") and re.fullmatch(r"(underline|line-through|none)( (underline|line-through))?", v):
            out.append(f"text-decoration:{v}")
        elif k == "font-weight" and v in ("bold", "700", "normal", "400"):
            out.append(f"font-weight:{v}")
        elif k == "font-style" and v in ("italic", "normal"):
            out.append(f"font-style:{v}")
    return ";".join(out)


def sanitize_html(src):
    """에디터 글(HTML)에서 허용한 태그·서식만 남긴다(스크립트·외부 요소 차단)."""
    from html.parser import HTMLParser
    out, stack, skip = [], [], [0]

    class P(HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style", "iframe", "object", "embed", "template", "svg", "math", "noscript", "textarea", "select"):
                skip[0] += 1
                return
            if tag == "font" or skip[0]:
                return
            if tag not in _SAFE_TAGS:
                return
            a = dict(attrs)
            keep = ""
            st = _safe_style(a.get("style") or "")
            if st:
                keep += f' style="{esc(st)}"'
            if tag == "a":
                href = (a.get("href") or "").strip()
                if not re.match(r"https?://", href, re.I):
                    return
                keep += f' href="{esc(href)}" target="_blank" rel="noopener"'
            if tag == "img":
                srcv = (a.get("src") or "").strip()
                if not (re.fullmatch(r"img/[\w.-]+", srcv) or srcv.startswith("https://")):
                    return
                keep += f' src="{esc(srcv)}" alt="{esc(a.get("alt") or "")}" loading="lazy"'
            out.append(f"<{tag}{keep}>")
            if tag not in _VOID:
                stack.append(tag)

        def handle_endtag(self, tag):
            if tag in ("script", "style", "iframe", "object", "embed", "template", "svg", "math", "noscript", "textarea", "select"):
                skip[0] = max(0, skip[0] - 1)
                return
            if tag in stack:
                while stack:
                    t = stack.pop()
                    out.append(f"</{t}>")
                    if t == tag:
                        break

        def handle_data(self, data):
            if not skip[0]:
                out.append(esc(data))

    parser = P(convert_charrefs=True)
    parser.feed(src)
    parser.close()
    out.extend(f"</{t}>" for t in reversed(stack))
    return "".join(out)


def post_html(p):
    return sanitize_html(p.get("body", "")) if p.get("format") == "html" else render_md(p.get("body", ""))


def load_posts():
    posts = []
    for f in sorted(POSTS_DIR.glob("*.json")):
        try:
            p = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if not re.fullmatch(r"[\w-]{1,40}", p.get("id", "")) or not p.get("title"):
            continue
        p["summary"] = post_summary(html.unescape(re.sub(r"<[^>]+>", " ", p.get("body", ""))) if p.get("format") == "html"
                                    else p.get("body", ""))
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
        rows = rows or '<p class="empty">아직 올라온 에디터 글이 없어요. 위의 <b>운영자 글쓰기</b>를 눌러 첫 글을 올려 보세요.</p>'
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
        body_html = post_html(p)
        fams = [f for f in POST_FONTS if f in body_html]
        body = (f'<article class="post"><h1 class="serif">{esc(p["title"])}</h1>'
                f'<div class="meta"><span>{esc(sc["name"])} 에디터</span><span>{ICON_CLOCK}{fmt_time(p.get("date"))}</span>'
                f'<button class="circle share" data-url="{sc["url"]}/{path}" data-title="{esc(p["title"])}" title="공유" aria-label="공유">{ICON_SHARE}</button></div>'
                f'<div class="body">{body_html}</div>'
                f'<p style="margin-top:40px"><a class="more" href="index.html">← 에디터 글 목록</a></p></article>')
        (out / f"{p['id']}.html").write_text(page(f"{p['title']} | {sc['name']}", body, "../", cats, search=False,
                                                  path=path, desc=p["summary"], jsonld=ld, og_type="article",
                                                  active="editor", image=cover, head=font_links(fams)), encoding="utf-8")
        pages.append(path)
    (out / "posts.json").write_text(json.dumps(
        [{k: p.get(k) for k in ("id", "title", "body", "format", "cover", "images", "date", "updated")} for p in posts],
        ensure_ascii=False), encoding="utf-8")
    key = ROOT / "static" / "editor-key.json"
    write = (WRITE_HTML.replace("{TOPIC}", esc(sc.get("editor_topic", "")))
             .replace("{KEY}", esc(key.read_text(encoding="utf-8").strip()) if key.exists() else "null"))
    st = POSTS_DIR / "status.json"
    (out / "status.json").write_text(st.read_text(encoding="utf-8") if st.exists() else '{"pin_set": false, "results": []}',
                                     encoding="utf-8")
    (out / "write.html").write_text(page(f"글쓰기 | {sc['name']}", write, "../", cats, search=False, path="editor/write.html",
                                         index=False, active="editor", script=WRITE_JS, head=font_links(POST_FONTS)), encoding="utf-8")
    return pages


WRITE_HTML = """<div class="post" id="w" data-topic="{TOPIC}" data-key='{KEY}'><h1 class="serif">에디터 글쓰기</h1>
<section id="v-first" hidden><p>처음이라 운영자 비밀번호를 정해요. 숫자 4자리를 두 번 입력해 주세요.</p>
<p><input id="pin1" class="inp pin" inputmode="numeric" maxlength="4" type="password" placeholder="비밀번호 4자리">
<input id="pin2" class="inp pin" inputmode="numeric" maxlength="4" type="password" placeholder="한 번 더"></p>
<p><button id="first-go" class="btn">비밀번호 정하고 시작</button> <span id="first-msg" class="meta"></span></p>
<p class="meta">비밀번호는 사이트 서버 쪽에만 보관돼요. 어느 기기에서든 이 비밀번호로 글을 쓸 수 있어요.</p></section>
<section id="v-lock" hidden><p>운영자 비밀번호 4자리를 입력하세요.</p>
<p><input id="pin" class="inp pin" inputmode="numeric" maxlength="4" type="password" autocomplete="off" placeholder="••••"></p>
<p id="lock-msg" class="meta"></p></section>
<section id="v-list" hidden><p><button id="new" class="btn">새 글 쓰기</button> <button id="logout" class="linkbtn">로그아웃</button> <span id="list-msg" class="meta"></span></p>
<ul id="pend" class="plist pend"></ul><ul id="plist" class="plist"></ul></section>
<section id="v-edit" hidden><p><input id="title" class="inp" placeholder="제목"></p>
<div class="tools" id="tools"><select id="t-font" class="tsel" title="글꼴"><option value="" style="font-family:''">기본 글꼴</option><option value="Nanum Myeongjo" style="font-family:'Nanum Myeongjo'">나눔명조</option><option value="Noto Serif KR" style="font-family:'Noto Serif KR'">노토 세리프</option><option value="Gowun Batang" style="font-family:'Gowun Batang'">고운바탕</option><option value="Nanum Gothic" style="font-family:'Nanum Gothic'">나눔고딕</option><option value="Gowun Dodum" style="font-family:'Gowun Dodum'">고운돋움</option><option value="IBM Plex Sans KR" style="font-family:'IBM Plex Sans KR'">IBM 플렉스</option><option value="Do Hyeon" style="font-family:'Do Hyeon'">도현</option><option value="Black Han Sans" style="font-family:'Black Han Sans'">검은고딕</option><option value="Nanum Pen Script" style="font-family:'Nanum Pen Script'">나눔손글씨 펜</option><option value="Gaegu" style="font-family:'Gaegu'">개구 손글씨</option></select><select id="t-size" class="tsel" title="글자 크기"><option value="">크기</option><option value="2">작게</option><option value="3">보통</option><option value="5">크게</option><option value="6">아주 크게</option><option value="7">제일 크게</option></select><span class="tsep"></span><button type="button" class="tb ic" data-c="bold" title="굵게"><b>B</b></button><button type="button" class="tb ic" data-c="italic" title="기울임"><i style="font-family:serif">I</i></button><button type="button" class="tb ic" data-c="underline" title="밑줄"><u>U</u></button><button type="button" class="tb ic" data-c="strikeThrough" title="취소선"><s>S</s></button><span class="tpop"><button type="button" class="tb ic" id="t-hl" title="형광펜"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 11l-5 5v4h4l5-5M14 6l4 4M9 11l5-5 4 4-5 5z"/><path d="M3 21h18" stroke="#ffd400" stroke-width="3"/></svg></button><span class="pal" id="p-hl" hidden><button type="button" data-hl="#fff27a" style="background:#fff27a" title="형광펜"></button><button type="button" data-hl="#b8f5c8" style="background:#b8f5c8" title="형광펜"></button><button type="button" data-hl="#bde0ff" style="background:#bde0ff" title="형광펜"></button><button type="button" data-hl="#ffc8e6" style="background:#ffc8e6" title="형광펜"></button><button type="button" data-hl="#ffd6a5" style="background:#ffd6a5" title="형광펜"></button><button type="button" data-hl="transparent" class="none" title="형광펜 지우기">✕</button></span></span><span class="tpop"><button type="button" class="tb ic" id="t-fc" title="글자색"><span style="font-weight:700;border-bottom:3px solid #3b7bff;line-height:1">A</span></button><span class="pal" id="p-fc" hidden><button type="button" data-fc="#e5484d" style="background:#e5484d" title="글자색"></button><button type="button" data-fc="#f76b15" style="background:#f76b15" title="글자색"></button><button type="button" data-fc="#2a9d5c" style="background:#2a9d5c" title="글자색"></button><button type="button" data-fc="#3b7bff" style="background:#3b7bff" title="글자색"></button><button type="button" data-fc="#8b2cff" style="background:#8b2cff" title="글자색"></button><button type="button" data-fc="#6b7280" style="background:#6b7280" title="글자색"></button><button type="button" data-fc="" class="none" title="기본 색">✕</button></span></span><span class="tsep"></span><button type="button" class="tb ic" data-c="justifyLeft" title="왼쪽 정렬"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6h16M4 10h10M4 14h16M4 18h10"/></svg></button><button type="button" class="tb ic" data-c="justifyCenter" title="가운데 정렬"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6h16M7 10h10M4 14h16M7 18h10"/></svg></button><button type="button" class="tb ic" data-c="justifyRight" title="오른쪽 정렬"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6h16M10 10h10M4 14h16M10 18h10"/></svg></button><button type="button" class="tb ic" data-c="justifyFull" title="양쪽 정렬"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6h16M4 10h16M4 14h16M4 18h16"/></svg></button><span class="tsep"></span><button type="button" class="tb" data-b="h2" title="소제목">소제목</button><button type="button" class="tb ic" data-b="blockquote" title="인용"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 7h4v4c0 3-2 5-4 6M15 7h4v4c0 3-2 5-4 6"/></svg></button><button type="button" class="tb ic" data-c="insertUnorderedList" title="점 목록"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6h11M9 12h11M9 18h11"/><circle cx="4.5" cy="6" r="1"/><circle cx="4.5" cy="12" r="1"/><circle cx="4.5" cy="18" r="1"/></svg></button><button type="button" class="tb ic" data-c="insertOrderedList" title="번호 목록"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 6h10M10 12h10M10 18h10M4 5h1v4M4 9h2M4 14h2l-2 3h2"/></svg></button><button type="button" class="tb ic" id="t-link" title="링크"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/></svg></button><button type="button" class="tb ic" data-c="insertHorizontalRule" title="구분선"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12h18"/></svg></button><label class="tb" title="커서가 있는 곳에 사진 넣기"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="3"/><circle cx="9" cy="10" r="2"/><path d="M21 16l-5-5-9 9"/></svg>사진<input id="file" type="file" accept="image/*" multiple hidden></label><span class="tsep"></span><button type="button" class="tb ic" data-c="undo" title="되돌리기"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 14L4 9l5-5"/><path d="M4 9h11a5 5 0 0 1 0 10h-3"/></svg></button><button type="button" class="tb ic" data-c="redo" title="다시 하기"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 14l5-5-5-5"/><path d="M20 9H9a5 5 0 0 0 0 10h3"/></svg></button><button type="button" class="tb ic" data-c="removeFormat" title="서식 지우기"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7V5h14v2M11 5l-3 14M14 19H6M16 14l5 5M21 14l-5 5"/></svg></button></div>
<div id="body" class="inp rich" contenteditable="true" data-ph="내용을 쓰세요. 글 사이에 사진을 넣고 싶은 곳을 누른 뒤 '사진 넣기'를 누르면 그 자리에 들어가요."></div>
<p class="meta">사진은 직접 찍었거나 사용 권리가 있는 것만 올려 주세요. 사진 오른쪽 위 ✕ 로 뺄 수 있어요.</p>
<div id="thumbs" class="thumbs"></div>
<p><button id="publish" class="btn">게시하기</button> <button id="cancel" class="btn ghost">목록으로</button> <span id="edit-msg" class="meta"></span></p></section>
</div>
<style>.inp{width:100%;font:inherit;font-size:16px;padding:12px 14px;border:1px solid var(--line);border-radius:12px;background:var(--card);color:var(--text)}
.pin{width:160px;letter-spacing:.4em;text-align:center}.pin::placeholder{letter-spacing:normal}textarea.inp{line-height:1.7;resize:vertical}
.tools{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin:0 0 8px;position:sticky;top:64px;z-index:6;background:var(--bg);padding:8px 0;border-bottom:1px solid var(--line)}
.tb.ic{width:38px;height:38px;padding:0;justify-content:center;font-size:16px}.tb.on{border-color:var(--accent);color:var(--accent)}.tsep{width:1px;height:24px;background:var(--line);margin:0 2px}
.tsel{font:inherit;font-size:14px;height:38px;padding:0 10px;border-radius:99px;border:1px solid var(--line);background:var(--card);color:var(--text);max-width:150px}
.tpop{position:relative;display:inline-flex}.pal{position:absolute;top:44px;left:0;display:flex;gap:6px;padding:8px;background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow);z-index:8}
.pal button{width:28px;height:28px;border-radius:50%;border:1px solid var(--line);cursor:pointer}.pal .none{background:var(--card);color:var(--muted);font-size:12px}
.rich blockquote{margin:12px 0;padding:4px 16px;border-left:3px solid var(--accent);color:var(--muted)}.rich hr{border:0;border-top:1px solid var(--line);margin:22px 0}
.rich ul,.rich ol{padding-left:1.4em}.rich a{color:var(--accent);text-decoration:underline}.rich [style*="background-color"]{color:#111}
.tb{display:inline-flex;align-items:center;gap:6px;font:inherit;font-size:14px;font-weight:600;padding:9px 14px;border-radius:99px;border:1px solid var(--line);background:var(--card);color:var(--text);cursor:pointer}.tb svg{width:18px;height:18px}
.rich{min-height:320px;line-height:1.8;font-size:17px;outline:none}.rich:empty::before{content:attr(data-ph);color:var(--muted)}
.rich p,.rich div{margin:0 0 12px}.rich h2{font-size:21px;margin:18px 0 8px;color:var(--heading)}
.rich figure{margin:14px 0;position:relative;user-select:none}.rich figure img{display:block;max-width:100%;border-radius:10px}
.rich figure button{position:absolute;top:8px;right:8px;width:32px;height:32px;border-radius:50%;border:0;background:rgba(0,0,0,.6);color:#fff;font-size:16px;cursor:pointer}
.btn{font:inherit;font-weight:600;border:0;border-radius:99px;padding:10px 20px;background:var(--grad);color:#fff;cursor:pointer;display:inline-block}
.btn.ghost{background:var(--soft);color:var(--accent)}.btn:disabled{opacity:.5}.linkbtn{background:none;border:0;color:var(--muted);text-decoration:underline;cursor:pointer;font:inherit;font-size:13px}
.thumbs{display:flex;flex-wrap:wrap;gap:12px;margin:8px 0 16px}.thumbs figure{margin:0;width:140px}.thumbs img{width:140px;height:90px;object-fit:cover;border-radius:8px}
.thumbs label{font-size:12.5px;color:var(--muted)}
@media (max-width:600px){.post#w h1{font-size:25px}.pin{width:calc(50% - 6px)}#v-lock .pin{width:100%;font-size:22px}
#setup-go,#new{width:100%;padding:14px}#v-list .meta,#setup-msg{display:block;margin-top:8px}
.plist li{display:flex;flex-wrap:wrap;align-items:center;gap:6px}.plist li b{flex:1 0 100%}.pend li{font-size:14px;color:var(--muted)}.pend li.bad{color:#e5484d}.plist button{margin:0;padding:8px 14px}
.tools{flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none;top:0;margin:0 -16px 8px;padding:8px 16px}.tools::-webkit-scrollbar{display:none}.tools>*{flex:none}
.pal{position:fixed;top:auto;left:16px;right:16px;bottom:90px;justify-content:center}.rich{min-height:45vh;font-size:17px;padding:14px}
.thumbs figure,.thumbs img{width:calc((100vw - 56px)/3)}.thumbs img{height:auto;aspect-ratio:3/2}
#v-edit>p:last-child{position:sticky;bottom:0;background:var(--bg);padding:10px 0 calc(10px + env(safe-area-inset-bottom));margin:0 0 -10px;display:flex;flex-wrap:wrap;gap:8px;border-top:1px solid var(--line);z-index:5}
#v-edit>p:last-child .btn{flex:1;padding:14px}#edit-msg{flex:1 0 100%}}.plist{list-style:none;padding:0}.plist li{padding:12px 0;border-bottom:1px solid var(--line)}
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
    parts.append(f'<div class="kw" data-kg="{esc(json.dumps(KW_GROUPS, ensure_ascii=False))}"><strong>오늘의 키워드</strong>'
                 + "".join(f'<button type="button" class="kwb" data-t="{esc("|".join(kw_terms(k)))}">#{esc(k)}</button>' for k in top_keywords(items))
                 + f'<span class="info">{info}</span></div>')
    tabs = ['<button class="on" data-cat="all" id="all">전체</button>']
    tabs += [f'<button data-cat="{c}" style="--c:{INTRO_COLORS.get(c, DEFAULT_TINT)}"><i class="cd"></i>{esc(n)} {len(by_cat.get(c, []))}</button>' for c, n in cats.items()]
    parts.append('<div class="tabs">' + "".join(tabs) + "</div>")
    for c, name in cats.items():  # 나머지는 그림 없이 최신순 8개씩, 페이지를 넘겨 본다
        rows = sorted(by_cat.get(c, []), key=lambda x: x.get("published") or "", reverse=True)
        body = (f'<div class="rows" data-pg>{"".join(row_html(it, cats) for it in rows)}</div><div class="pager"></div>'
                if rows else '<p class="empty">오늘은 새 소식이 없습니다.</p>')
        parts.append(f'<section class="cat" data-cat="{c}" id="{c}" style="--c:{INTRO_COLORS.get(c, DEFAULT_TINT)}"><h2 class="serif">{esc(name)}</h2>{body}'
                     f'<a class="more" href="{c}/">{esc(name)} 지난 기록 모두 보기 →</a></section>')
    sc = site_cfg()
    heading = f'<h1 class="eyebrow">{day_title(data["date"])} 오늘의 AI 브리핑</h1>'
    title = f"{sc['name']} | 오늘의 AI 뉴스·논문·정책 브리핑 · {day_title(data['date'])}"
    ld = day_jsonld(data, f"{sc['url']}/")
    ld.insert(0, {"@context": "https://schema.org", "@type": "WebSite", "name": sc["name"], "url": sc["url"] + "/",
                  "description": sc["description"], "inLanguage": "ko"})
    return page(title, heading + "\n".join(parts), "", cats, desc=day_desc(data, cats), path="home.html", jsonld=ld, active="home")


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
        body = (f'<div class="ph" style="--c:{INTRO_COLORS.get(c, DEFAULT_TINT)}"><h1 class="serif">{esc(name)}</h1><span>지금까지 {len(items)}건 · {pg + 1}/{n}쪽</span></div>'
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


DEFAULT_TINT = "#3b7bff"
INTRO_COLORS = {"news_ko": "#12e3ff", "news_global": "#3b7bff", "papers": "#a24bff", "policy": "#ffb020", "talks": "#2ff5a0"}  # 분야별로 확실히 다른 색(첫 화면 점·제목 막대·탭 공통)


def ticker_items(items, n=14):
    """첫 화면 아래 흐르는 줄: 홈의 헤드라인·주요 소식을 먼저, 나머지는 최신순."""
    hero, trend = pick_featured(items)
    top = [x for x in [hero, *trend] if x]
    ids = {x["id"] for x in top}
    rest = sorted((x for x in items if x["id"] not in ids), key=lambda x: x.get("published") or "", reverse=True)
    return [{"t": x.get("title_ko") or x["title"], "u": x["link"], "c": INTRO_COLORS.get(x["category"], DEFAULT_TINT)}
            for x in (top + rest)[:n]]


def tick_html(tk):
    return "".join(f'<a href="{esc(x["u"])}" target="_blank" rel="noopener" style="--c:{x["c"]}">{esc(x["t"])}</a>' for x in tk)


def render_intro(latest, cats, sc, enter="home.html", preview=False):
    """사이트 앞에 두는 3D 입장 페이지(intro.html 템플릿). 오늘 모인 글 수와 제목 몇 개를 띄운다."""
    items = latest["items"]
    count = {c: sum(1 for it in items if it["category"] == c) for c in cats}
    links = "".join(f'<a href="{c}/" data-go style="--c:{INTRO_COLORS.get(c, DEFAULT_TINT)}"><i></i><b>{esc(n)}</b></a>'
                    for c, n in cats.items())
    tick = tick_html(ticker_items(items))
    d = datetime.fromisoformat(latest["date"])
    verify = ""
    if sc["google"]:
        verify += f'<meta name="google-site-verification" content="{esc(sc["google"])}">'
    if sc["naver"]:
        verify += f'<meta name="naver-site-verification" content="{esc(sc["naver"])}">'
    page_ = (ROOT / "intro.html").read_text(encoding="utf-8")
    for k, v in {"{NAME}": esc(sc["name"]), "{DESC}": esc(sc["description"]), "{URL}": sc["url"], "{VERIFY}": verify,
                 "{ROBOTS}": '<meta name="robots" content="noindex">' if preview else "", "{FAVICON}": FAVICON,
                 "{DATE}": f"{d.month}월 {d.day}일", "{TOTAL}": str(len(items)), "{CATS}": links, "{TICK}": tick}.items():
        page_ = page_.replace(k, v)
    return page_.replace('href="home.html"', f'href="{enter}"')


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
    # 첫 화면은 3D 입장 페이지, ENTER 를 누르면 오늘의 브리핑(home.html)
    (SITE_DIR / "index.html").write_text(render_intro(latest, cats, sc), encoding="utf-8")
    (SITE_DIR / "ticker.json").write_text(json.dumps(ticker_items(latest["items"]), ensure_ascii=False), encoding="utf-8")
    (SITE_DIR / "home.html").write_text(render_home(latest, cats, posts), encoding="utf-8")
    (SITE_DIR / "intro.html").unlink(missing_ok=True)
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
        f'<h1 class="serif" style="font-size:26px;margin:40px 0 8px">페이지를 찾을 수 없어요</h1><p><a class="read" href="{sc["url"]}/home.html">오늘의 브리핑으로 가기 →</a></p>',
        base=sc["url"] + "/", cats=cats, search=False, path="404.html", index=False), encoding="utf-8")
    # 검색엔진용 파일
    now = latest.get("generated_at", latest["date"])
    urls = [(f"{sc['url']}/", now, "hourly", "1.0"), (f"{sc['url']}/home.html", now, "hourly", "0.9")]
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

# ---------------------------------------------------------------- 운영자 글 받기(비밀번호만으로 글쓰기)
# 글쓰기 화면은 글을 사이트 공개키로 암호화해 ntfy.sh(무료 중계)에 맡긴다. 여기서 30분마다 꺼내 풀고,
# 비밀번호가 맞으면 posts/ 에 저장한다. 비밀키와 비밀번호 확인값은 저장소가 아닌 .editor/(GitHub 캐시)에만 둔다.
EDITOR_DIR = ROOT / ".editor"
MAX_PIN_FAILS = 10  # 하루에 비밀번호를 이만큼 틀리면 그날은 더 받지 않는다


def _b64d(s):
    import base64
    return base64.b64decode(s)


def editor_inbox():
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:
        print("[inbox] cryptography 가 없어 건너뜀")
        return
    import base64
    import hmac
    import secrets
    topic = site_cfg().get("editor_topic")
    if not topic:
        return
    EDITOR_DIR.mkdir(exist_ok=True)
    kf, sf = EDITOR_DIR / "key.pem", EDITOR_DIR / "state.json"
    pub_file = ROOT / "static" / "editor-key.json"
    if not kf.exists():  # 처음 한 번 열쇠 한 쌍을 만든다(비밀번호도 새로 정해야 함)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        kf.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption()))
        sf.unlink(missing_ok=True)
    key = serialization.load_pem_private_key(kf.read_bytes(), password=None)
    nums = key.public_key().public_numbers()
    to64 = lambda n: base64.urlsafe_b64encode(n.to_bytes((n.bit_length() + 7) // 8, "big")).rstrip(b"=").decode()
    kid = hashlib.sha256(str(nums.n).encode()).hexdigest()[:12]
    jwk = {"kty": "RSA", "n": to64(nums.n), "e": to64(nums.e), "alg": "RSA-OAEP-256", "ext": True, "kid": kid}
    if not pub_file.exists() or json.loads(pub_file.read_text(encoding="utf-8")).get("kid") != kid:
        pub_file.write_text(json.dumps(jwk), encoding="utf-8")
    st = json.loads(sf.read_text(encoding="utf-8")) if sf.exists() else {}
    status_f = POSTS_DIR / "status.json"
    status = json.loads(status_f.read_text(encoding="utf-8")) if status_f.exists() else {"results": []}
    today = datetime.now(KST).strftime("%Y-%m-%d")
    fails = st.get("fails", {}).get(today, 0)

    def pin_hash(pin, salt):
        return hashlib.pbkdf2_hmac("sha256", pin.encode(), salt.encode(), 200000).hex()

    def result(ref, ok, text):
        status["results"] = (status.get("results", []) + [{"ref": str(ref)[:40], "ok": ok, "msg": text,
                                                           "at": datetime.now(KST).isoformat(timespec="minutes")}])[-30:]
        print("[inbox]", "OK" if ok else "거절", text)

    since = st.get("since") or "12h"
    try:
        raw = fetch(f"https://ntfy.sh/{topic}/json?poll=1&since={since}").decode("utf-8", "replace")
    except Exception as e:
        print("[inbox] 중계 서버에 연결 실패:", e)
        return
    changed = False
    for line in raw.splitlines():
        try:
            m = json.loads(line)
        except ValueError:
            continue
        if m.get("event") != "message":
            continue
        st["since"] = m.get("id") or st.get("since")
        try:
            blob = fetch(m["attachment"]["url"]) if m.get("attachment") else (m.get("message") or "").encode()
            env = json.loads(blob)
            if env.get("kid") != kid:
                continue  # 예전 열쇠로 잠근 글(열쇠가 바뀌기 전 것)
            aes = key.decrypt(_b64d(env["k"]), padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
            req = json.loads(AESGCM(aes).decrypt(_b64d(env["iv"]), _b64d(env["ct"]), None))
        except Exception as e:
            print("[inbox] 읽을 수 없는 메시지 건너뜀:", type(e).__name__)
            continue
        ref, op, pin = req.get("ref", ""), req.get("op"), str(req.get("pin") or "")
        if fails >= MAX_PIN_FAILS:
            result(ref, False, "비밀번호를 너무 많이 틀려서 오늘은 잠겨 있어요")
            continue
        if not re.fullmatch(r"\d{4}", pin):
            result(ref, False, "비밀번호 형식이 달라요")
            continue
        if op == "setpin":
            if st.get("pin"):
                result(ref, False, "비밀번호가 이미 정해져 있어요")
            else:
                salt = secrets.token_hex(16)
                st["pin"] = {"salt": salt, "hash": pin_hash(pin, salt)}
                result(ref, True, "비밀번호를 정했어요")
            changed = True
            continue
        if not st.get("pin") or not hmac.compare_digest(pin_hash(pin, st["pin"]["salt"]), st["pin"]["hash"]):
            fails += 1
            st.setdefault("fails", {})[today] = fails
            result(ref, False, "비밀번호가 달라요")
            changed = True
            continue
        if op == "publish":
            post, up = req.get("post") or {}, req.get("upload") or {}
            pid = str(post.get("id", ""))
            if not re.fullmatch(r"[\w-]{1,40}", pid) or not post.get("title"):
                result(ref, False, "글 형식이 잘못됐어요")
                continue
            (POSTS_DIR / "img").mkdir(parents=True, exist_ok=True)
            imgs = [n for n in post.get("images", []) if re.fullmatch(re.escape(pid) + r"-\d{1,3}\.jpg", str(n))]
            old_f = POSTS_DIR / f"{pid}.json"
            old = json.loads(old_f.read_text(encoding="utf-8")) if old_f.exists() else {}
            for n in old.get("images", []):
                if n not in imgs:
                    (POSTS_DIR / "img" / n).unlink(missing_ok=True)
            for n, data in up.items():
                if n in imgs:
                    b = _b64d(data)
                    if b[:3] == b"\xff\xd8\xff" and len(b) < 8_000_000:  # JPEG 만
                        (POSTS_DIR / "img" / n).write_bytes(b)
            imgs = [n for n in imgs if (POSTS_DIR / "img" / n).exists()]
            cover = post.get("cover") if str(post.get("cover", "")).removeprefix("img/") in imgs else (f"img/{imgs[0]}" if imgs else "")
            fmt = "html" if post.get("format") == "html" else "md"
            body = str(post.get("body", ""))[:300000]
            clean = {"id": pid, "title": str(post["title"])[:200], "format": fmt,
                     "body": sanitize_html(body) if fmt == "html" else body[:60000], "cover": cover,
                     "images": imgs, "date": old.get("date") or str(post.get("date", ""))[:40] or datetime.now(KST).isoformat(),
                     "updated": datetime.now(KST).isoformat(timespec="seconds")}
            old_f.write_text(json.dumps(clean, ensure_ascii=False, indent=1), encoding="utf-8")
            result(ref, True, "게시했어요")
            changed = True
        elif op == "delete":
            pid = str(req.get("id", ""))
            f = POSTS_DIR / f"{pid}.json"
            if re.fullmatch(r"[\w-]{1,40}", pid) and f.exists():
                for n in json.loads(f.read_text(encoding="utf-8")).get("images", []):
                    (POSTS_DIR / "img" / n).unlink(missing_ok=True)
                f.unlink()
                result(ref, True, "삭제했어요")
            else:
                result(ref, False, "지울 글을 찾지 못했어요")
            changed = True
    status["pin_set"] = bool(st.get("pin"))
    POSTS_DIR.mkdir(exist_ok=True)
    status_f.write_text(json.dumps(status, ensure_ascii=False, indent=1), encoding="utf-8")
    sf.write_text(json.dumps(st), encoding="utf-8")
    print("[inbox] 처리 완료" if changed else "[inbox] 새 글 없음")



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="all", choices=["all", "collect", "build", "backfill", "photos", "inbox"])
    ap.add_argument("--since", help="backfill 시작 날짜(YYYY-MM-DD)")
    ap.add_argument("--fixtures", help="네트워크 대신 사용할 로컬 피드 폴더(테스트용)")
    a = ap.parse_args()
    if a.cmd == "inbox":
        editor_inbox()
        return
    if a.cmd == "photos":
        collect_photos()
        return
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
