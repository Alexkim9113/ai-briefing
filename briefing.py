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


def parse_date(s):
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
        d = d.replace(tzinfo=timezone.utc)
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


def is_ai_related(item, keywords):
    blob = (item["title"] + " " + clean_text(item["desc"])[:400]).lower()
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


def recent_ids(today, days=DEDUPE_DAYS):
    seen = set()
    for i in range(1, days + 1):
        p = DATA_DIR / f"{(today - timedelta(days=i)).isoformat()}.json"
        if p.exists():
            for it in json.loads(p.read_text(encoding="utf-8"))["items"]:
                seen.add(it["id"])
    return seen


def label(src):
    return f'{src["name"]} · {src["field"]}' if src.get("field") else src["name"]


_SLOW_HOST_LOCK = threading.Lock()


def collect_source(src, fixtures):
    host = urllib.parse.urlsplit(src["url"]).netloc
    if "nature.com" in host and not fixtures:
        with _SLOW_HOST_LOCK:  # 같은 사이트에 동시에 여러 번 요청하면 차단되므로 순서대로 천천히
            raw = fetch(src["url"], fixtures, src.get("ua"))
            time.sleep(2)
    else:
        raw = fetch(src["url"], fixtures, src.get("ua"))
    kind = src.get("type")
    if kind == "hf_papers":
        return parse_hf_papers(raw)
    if kind == "europepmc":
        return parse_europepmc(raw)
    return parse_feed(raw)


def collect(fixtures=None, now=None):
    cfg = load_config()
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(KST).date()
    cutoff = now - timedelta(hours=FRESH_HOURS)
    seen = recent_ids(today)
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
                title = clean_text(it["title"])
                if not title or not it["link"]:
                    continue
                if src.get("url", "").startswith("https://news.google.com"):
                    title = _TITLE_SUFFIX.sub("", title)  # "제목 - 언론사" 에서 언론사 꼬리 제거
                d = parse_date(it["date"])
                if d and d < cutoff and src["category"] != "papers":  # 논문은 주말·발표 지연이 있어 기간 제한 없이 최근 7일 중복만 제외
                    continue
                if src.get("keywords") and not is_ai_related(it, src["keywords"]):
                    continue  # 분야 키워드(예: 법·교육·에너지)가 있는 글만
                if (src.get("filter") or src.get("require_ai")) and not is_ai_related(it, keywords):
                    continue
                iid = item_id(it["link"], title)
                if iid in seen:
                    continue
                kept.append({
                    "id": iid, "title": title, "link": it["link"],
                    "source": label(src), "field": src.get("field", ""),
                    "category": src["category"], "published": d.isoformat() if d else None,
                    "summary": summarize(it["desc"], title),
                    "thumb": "",  # 저작권 보호: 원본의 썸네일·사진은 수집하지 않는다(표지는 자체 제작 디자인)
                })
                if len(kept) >= src.get("limit", DEFAULT_LIMIT):
                    break
            status.append({"name": label(src), "ok": True, "count": len(kept), "fetched": len(raw_items)})
            results.extend(kept)

    # 소스 간 중복 제거(같은 링크 또는 같은 제목)
    uniq, keys = [], set()
    for it in sorted(results, key=lambda x: x["published"] or "", reverse=True):
        tkey = re.sub(r"\W+", "", it["title"].lower())[:60]
        if it["id"] in keys or tkey in keys:
            continue
        keys.update((it["id"], tkey))
        uniq.append(it)

    DATA_DIR.mkdir(exist_ok=True)
    path = DATA_DIR / f"{today.isoformat()}.json"
    if path.exists():  # 같은 날 여러 번 실행되면 기존 항목과 합친다
        old = json.loads(path.read_text(encoding="utf-8"))["items"]
        ids = {i["id"] for i in uniq}
        uniq += [i for i in old if i["id"] not in ids]
        uniq.sort(key=lambda x: x["published"] or "", reverse=True)
    per_cat = Counter()  # 30분마다 쌓이므로 분야별 하루 최대 개수를 넘으면 오래된 것부터 뺀다
    uniq = [i for i in uniq if (per_cat.update([i["category"]]) or per_cat[i["category"]] <= MAX_PER_CAT)]
    data = {"date": today.isoformat(), "generated_at": now.astimezone(KST).isoformat(timespec="minutes"),
            "items": uniq, "status": sorted(status, key=lambda s: s["name"])}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(s["ok"] for s in status)
    print(f"[collect] {today} 항목 {len(uniq)}개, 소스 {ok}/{len(status)} 성공 → {path.relative_to(ROOT)}")
    return data


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
.thumb{position:relative;display:block;overflow:hidden;border-radius:16px;aspect-ratio:16/9;box-shadow:var(--shadow);background:linear-gradient(135deg,var(--g1,#3d0f22),var(--g2,#7a1f3d))}
.thumb img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.thumb::before{content:"";position:absolute;inset:0;background:radial-gradient(circle at 85% 20%,rgba(255,255,255,.22),transparent 45%),
repeating-linear-gradient(135deg,rgba(255,255,255,.05) 0 2px,transparent 2px 14px)}
.thumb .ico{position:absolute;right:8%;top:50%;transform:translateY(-50%);width:34%;height:auto;max-height:62%;color:rgba(255,255,255,.88)}
.thumb .ph{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:flex-end;padding:16px 18px;color:#fff}
.thumb .ph i{position:absolute;top:14px;left:16px;font-style:normal;font-size:11.5px;background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.25);padding:3px 10px;border-radius:99px}
.thumb .ph b{font-weight:700;font-size:22px;line-height:1.3}.thumb .ph span{font-size:12px;opacity:.7}
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
.trend .thumb{border-radius:12px}.trend .thumb .ph b{font-size:13.5px}.trend .thumb .ph{padding:8px 10px}.trend .thumb .ph i,.trend .thumb .ph span,.trend .thumb .ph b{display:none}.trend .thumb .ico{right:50%;transform:translate(50%,-50%);width:38%}
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
footer{margin-top:56px;line-height:1.7;padding-top:26px;padding-bottom:40px;border-top:1px solid var(--line);font-size:13px;color:var(--muted)}
details summary{cursor:pointer}ul.st{columns:3;padding-left:18px}ul.st .bad{color:#c2410c}
ul.days{list-style:none;padding:0;max-width:640px}ul.days li{padding:12px 0;border-bottom:1px solid var(--line)}ul.days a{color:var(--accent)}
[hidden]{display:none!important}
@media (max-width:960px){.hero{grid-template-columns:1fr;gap:32px}.grid{grid-template-columns:repeat(2,1fr)}
.bar .wrap{flex-wrap:wrap;height:auto;padding-top:12px;padding-bottom:12px;gap:10px 16px}
.bar nav{justify-content:flex-end;flex:1}.bar nav a[data-go]{display:none}
.search{order:3;width:100%}.search input{font-size:16px}}
@media (max-width:600px){body{font-size:16px;line-height:1.65}.wrap{padding:0 16px}
.logo{font-size:18px}.eyebrow{margin-top:18px;font-size:13px}.hero{padding:8px 0 16px;gap:28px}.hero h2{font-size:23px;line-height:1.4;margin-bottom:14px}
.badge{margin:8px 0 0;top:0;display:table}.hero .thumb{aspect-ratio:16/8}.hero p.sum{font-size:16px;line-height:1.7}
.trend{grid-template-columns:88px 1fr;gap:14px;padding-bottom:14px;border-bottom:1px solid var(--line)}.trend .thumb{aspect-ratio:1}
.trend .thumb .ph b{font-size:11.5px}.trend h3{font-size:16px}.trend .meta span:last-child{display:none}
.kw{gap:6px}.kw .info{margin-left:0;width:100%;padding-top:4px}
.tabs{padding:10px 0;margin:0 -16px;padding-left:16px;padding-right:16px}.tabs button{padding:9px 16px;font-size:15px}
section.cat>h2{font-size:21px;margin:26px 0 8px}
.grid,.list{grid-template-columns:1fr;gap:0}
.card:not(.row){display:grid;grid-template-columns:96px 1fr;column-gap:14px;padding:14px 0;border-bottom:1px solid var(--line)}
.card:not(.row) .thumb{grid-row:1/span 3;aspect-ratio:1;border-radius:12px;box-shadow:none}
.card .thumb .ph{padding:8px 10px}.card .thumb .ph{display:none}.card .thumb .ico{right:50%;transform:translate(50%,-50%);width:46%}
.card h3{font-size:16px;line-height:1.5;margin:0 0 4px}.card p{font-size:14px;-webkit-line-clamp:2;margin-bottom:6px}
.row{padding:14px 0}.meta{font-size:12.5px}
ul.st{columns:1}footer{margin-top:36px}}
"""

JS = """
const tabs=document.querySelectorAll('.tabs button'),secs=document.querySelectorAll('section.cat');
function show(c){tabs.forEach(x=>x.classList.toggle('on',x.dataset.cat===c));secs.forEach(s=>s.hidden=c!=='all'&&s.dataset.cat!==c);}
tabs.forEach(b=>b.onclick=()=>show(b.dataset.cat));
document.querySelectorAll('[data-go]').forEach(a=>a.onclick=e=>{e.preventDefault();show(a.dataset.go);document.querySelector('.tabs').scrollIntoView({behavior:'smooth'});});
const q=document.querySelector('.search input');
if(q)q.oninput=()=>{const v=q.value.trim().toLowerCase();show('all');
 document.querySelectorAll('article.card').forEach(a=>a.hidden=v&&!a.dataset.q.includes(v));
 if(v)secs.forEach(s=>s.hidden=!s.querySelector('article.card:not([hidden])'));};
document.querySelectorAll('.share').forEach(b=>b.onclick=async()=>{const u=b.dataset.url;
 try{if(navigator.share)await navigator.share({url:u,title:b.dataset.title});else{await navigator.clipboard.writeText(u);b.title='링크 복사됨';}}catch(e){}});
"""

WEEKDAYS = "월화수목금토일"
CARDS_PER_CAT = 6  # 분야별로 표지 카드로 보여줄 개수(나머지는 목록)
CAT_COLORS = {"news_ko": ("#3d0f22", "#8a2748"), "news_global": ("#2a1030", "#6b2d6b"), "papers": ("#1c1636", "#4b3a8c"),
              "policy": ("#10262a", "#2f6b67"), "youtube": ("#2b0d0d", "#9b2c2c")}
# 표지 이미지 대신 쓰는 자체 제작 그라데이션(기사마다 다르게)
COVER_COLORS = [("#3d0f22", "#8a2748"), ("#2a1030", "#6b2d6b"), ("#1c1636", "#4b3a8c"), ("#10262a", "#2f6b67"),
                ("#2b0d0d", "#9b2c2c"), ("#2d1a0c", "#9a5b24"), ("#0f1f33", "#2f5d8c"), ("#261022", "#a3456f")]
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
            "naver": s.get("naver_verification", "")}


def page(title, body, base="", cats=None, search=True, desc=None, path="", jsonld=None, og_type="website", index=True):
    sc = site_cfg()
    canonical = f'{sc["url"]}/{path}'
    desc = desc or sc["description"]
    nav = f'<a href="{base}index.html" class="on">오늘</a>'
    if cats:
        nav += "".join(f'<a href="#{c}" data-go="{c}">{esc(n)}</a>' for c, n in cats.items())
    nav += f'<a href="{base}archive.html">지난 브리핑</a>'
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
<meta property="og:url" content="{esc(canonical)}"><meta property="og:image" content="{sc["url"]}/og.png">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta property="og:locale" content="ko_KR">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(desc)}"><meta name="twitter:image" content="{sc["url"]}/og.png">
<meta name="theme-color" content="#2a0b17">{verify}
<link rel="icon" href="{FAVICON}"><link rel="apple-touch-icon" href="{base}apple-touch-icon.png">
<link rel="alternate" type="application/rss+xml" title="{esc(sc["name"])} RSS" href="{sc["url"]}/feed.xml">
<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">
<style>{CSS}</style>{ld}</head><body>
<header class="bar"><div class="wrap"><a class="logo serif" href="{base}index.html" aria-label="{esc(sc["name"])} 홈">{LOGO}<span>{esc(sc["name"])}</span></a><nav aria-label="주요 메뉴">{nav}</nav>{box}</div></header>
<main class="wrap">{body}</main>
<footer class="wrap"><p>30분마다 자동으로 새 소식을 모읍니다. 요약은 원문 앞부분을 자동 발췌한 것이며, 기사 저작권은 원 저작자에게 있습니다. 원본의 사진·썸네일은 수집하지 않으며, 표지 이미지는 사이트가 자체 생성한 디자인입니다. 전문은 각 원문 링크에서 확인하세요.</p>
<p><a href="{base}archive.html">지난 브리핑</a> · <a href="{sc["url"]}/feed.xml">RSS 구독</a></p></footer>
<script>{JS}</script></body></html>"""


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
                 "youtube": ("영상", '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="M10 9l5 3-5 3z"/>'),
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


def thumb_html(it, cats):
    g1, g2 = COVER_COLORS[int(it["id"][:6], 16) % len(COVER_COLORS)] if it.get("id") else CAT_COLORS["news_ko"]
    topic, icon = topic_of(it)
    img = (f'<img src="{esc(it["thumb"])}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">'
           if it.get("thumb") else "")
    return (f'<a class="thumb" href="{esc(it["link"])}" target="_blank" rel="noopener" style="--g1:{g1};--g2:{g2}" tabindex="-1" aria-hidden="true">'
            f'<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">{icon}</svg>'
            f'<div class="ph"><i>{esc(topic)}</i><b>{esc(it.get("field") or re.sub(r"^(구글뉴스|Google News): ", "", it["source"]))}</b>'
            f'<span>{fmt_time(it.get("published"))}</span></div>{img}</a>')


def meta_html(it, cats, with_cat=False):
    t = fmt_time(it.get("published"))
    parts = [f"<span>{ICON_SRC}{esc(it['source'])}</span>"]
    if t:
        parts.append(f"<span>{ICON_CLOCK}{t}</span>")
    if with_cat:
        parts.append(f"<span>{esc(cats.get(it['category'], ''))}</span>")
    return '<div class="meta">' + "".join(parts) + "</div>"


def title_link(it):
    return f'<a href="{esc(it["link"])}" target="_blank" rel="noopener">{esc(it["title"])}</a>'


def pick_featured(items):
    """헤드라인 1개 + 주요 소식 4개. 요약이 있는 뉴스를 우선하고 분야가 겹치지 않게 고른다."""
    pri = {"news_ko": 0, "news_global": 1, "policy": 2, "youtube": 3, "papers": 4}
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


def render_day(data, cats, base="", path=""):
    d = datetime.fromisoformat(data["date"])
    items = data["items"]
    by_cat = {c: [] for c in cats}
    for it in items:
        by_cat.setdefault(it["category"], []).append(it)
    parts = []
    hero, trend = pick_featured(items)
    if hero:
        summ = f'<p class="sum">{esc(hero["summary"])}</p>' if hero.get("summary") else ""
        side = "".join(
            f'<div class="trend">{thumb_html(i, cats)}<div><h3 class="serif">{title_link(i)}</h3>'
            + (f"<p>{esc(i['summary'])}</p>" if i.get("summary") else "")
            + f"{meta_html(i, cats, True)}</div></div>" for i in trend)
        parts.append(
            f'<div class="hero"><div><h2 class="serif">{title_link(hero)}<span class="badge">오늘의 헤드라인</span></h2>'
            f'{thumb_html(hero, cats)}{meta_html(hero, cats, True)}{summ}'
            f'<div class="actions"><a class="read" href="{esc(hero["link"])}" target="_blank" rel="noopener">원문 보기 →</a>'
            f'<button class="circle share" data-url="{esc(hero["link"])}" data-title="{esc(hero["title"])}" title="공유" aria-label="공유">{ICON_SHARE}</button></div></div>'
            f'<aside><div class="side-h"><h2>주요 소식</h2><a href="#all" data-go="all">전체 보기</a></div>{side}</aside></div>')
    info = f'{d.month}월 {d.day}일 ({WEEKDAYS[d.weekday()]}) · 총 {len(items)}건 · {esc(data["generated_at"][11:16])} 업데이트'
    parts.append('<div class="kw"><strong>오늘의 키워드</strong>'
                 + "".join(f"<span>#{esc(k)}</span>" for k in top_keywords(items))
                 + f'<span class="info">{info}</span></div>')
    tabs = ['<button class="on" data-cat="all" id="all">전체</button>']
    tabs += [f'<button data-cat="{c}">{esc(n)} {len(by_cat.get(c, []))}</button>' for c, n in cats.items()]
    parts.append('<div class="tabs">' + "".join(tabs) + "</div>")
    for c, name in cats.items():
        cards, rows = [], []
        for it in by_cat.get(c, []):  # 이미지가 있으면 카드, 없으면 간단한 목록으로
            summ = f"<p>{esc(it['summary'])}</p>" if it.get("summary") else ""
            q = esc((it["title"] + " " + it["source"] + " " + (it.get("summary") or "")).lower())
            if it.get("thumb") or len(cards) < CARDS_PER_CAT:
                cards.append(f'<article class="card" data-q="{q}">{thumb_html(it, cats)}'
                             f'<h3 class="serif">{title_link(it)}</h3>{summ}{meta_html(it, cats)}</article>')
            else:
                rows.append(f'<article class="card row" data-q="{q}"><h3 class="serif">{title_link(it)}</h3>{summ}{meta_html(it, cats)}</article>')
        body = (f'<div class="grid">{"".join(cards)}</div>' if cards else "") + (f'<div class="list">{"".join(rows)}</div>' if rows else "")
        body = body or '<p class="empty">오늘은 새 소식이 없습니다.</p>'
        parts.append(f'<section class="cat" data-cat="{c}" id="{c}"><h2 class="serif">{esc(name)}</h2>{body}</section>')
    st = data.get("status", [])
    ok = sum(s["ok"] for s in st)
    lis = "".join(f'<li class="{"" if s["ok"] else "bad"}">{esc(s["name"])}: '
                  f'{str(s["count"]) + "건" if s["ok"] else "실패"}</li>' for s in st)
    parts.append(f'<details style="margin-top:40px"><summary class="meta">수집 상태: 소스 {ok}/{len(st)}개 성공</summary>'
                 f'<ul class="st meta" style="display:block">{lis}</ul></details>')
    sc = site_cfg()
    heading = f'<h1 class="eyebrow">{day_title(data["date"])} 오늘의 AI 브리핑</h1>'
    if path:
        title = f"{day_title(data['date'])} AI 브리핑 · 뉴스·논문·정책 {len(items)}건 | {sc['name']}"
    else:
        title = f"{sc['name']} | 오늘의 AI 뉴스·논문·정책 브리핑 · {day_title(data['date'])}"
    ld = day_jsonld(data, f"{sc['url']}/{path}")
    if not path:
        ld.insert(0, {"@context": "https://schema.org", "@type": "WebSite", "name": sc["name"], "url": sc["url"] + "/",
                      "description": sc["description"], "inLanguage": "ko"})
    return page(title, heading + "\n".join(parts), base, cats, desc=day_desc(data, cats), path=path, jsonld=ld)


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
    (SITE_DIR / "archive").mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "data").mkdir(exist_ok=True)
    days, latest = [], None
    for i, f in enumerate(files):
        data = json.loads(f.read_text(encoding="utf-8"))
        days.append((data["date"], len(data["items"]), data.get("generated_at", data["date"])))
        (SITE_DIR / "data" / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")  # 원본 데이터도 함께 공개(백업·이전용)
        path = f"archive/{data['date']}.html"
        (SITE_DIR / path).write_text(render_day(data, cats, "../", path), encoding="utf-8")
        if i == 0:
            latest = data
            (SITE_DIR / "index.html").write_text(render_day(data, cats, "", ""), encoding="utf-8")
    lis = "".join(f'<li><a href="archive/{d}.html">{day_title(d)} AI 브리핑</a> <span class="meta">· {n}건</span></li>' for d, n, _ in days)
    (SITE_DIR / "archive.html").write_text(page(
        f"지난 AI 브리핑 모음 | {sc['name']}",
        f'<h1 class="serif" style="font-weight:700;font-size:26px;margin:36px 0 12px">지난 AI 브리핑</h1><ul class="days">{lis}</ul>',
        search=False, desc=f"{sc['name']}가 날짜별로 모아 둔 AI 뉴스·논문·정책 브리핑 {len(days)}일치 목록", path="archive.html"), encoding="utf-8")
    (SITE_DIR / "404.html").write_text(page(
        f"페이지를 찾을 수 없어요 | {sc['name']}",
        f'<h1 class="serif" style="font-size:26px;margin:40px 0 8px">페이지를 찾을 수 없어요</h1><p><a class="read" href="{sc["url"]}/">오늘의 브리핑으로 가기 →</a></p>',
        base=sc["url"] + "/", search=False, path="404.html", index=False), encoding="utf-8")
    # 검색엔진용 파일
    urls = [(f"{sc['url']}/", latest.get("generated_at", latest["date"]), "hourly", "1.0"),
            (f"{sc['url']}/archive.html", latest["date"], "daily", "0.6")]
    urls += [(f"{sc['url']}/archive/{d}.html", g, "weekly" if n2 else "daily", "0.5") for n2, (d, _, g) in enumerate(days)]
    sm = "".join(f"<url><loc>{esc(u)}</loc><lastmod>{m}</lastmod><changefreq>{c}</changefreq><priority>{p}</priority></url>" for u, m, c, p in urls)
    (SITE_DIR / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sm}</urlset>', encoding="utf-8")
    (SITE_DIR / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {sc['url']}/sitemap.xml\n", encoding="utf-8")
    write_feed(latest["items"], sc)
    for f in (ROOT / "static").glob("*"):  # 공유 이미지·아이콘
        (SITE_DIR / f.name).write_bytes(f.read_bytes())
    if sc["domain"]:
        (SITE_DIR / "CNAME").write_text(sc["domain"] + "\n")
    (SITE_DIR / ".nojekyll").write_text("")
    print(f"[build] {len(days)}일치 페이지 생성 → {SITE_DIR.relative_to(ROOT)}/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="all", choices=["all", "collect", "build"])
    ap.add_argument("--fixtures", help="네트워크 대신 사용할 로컬 피드 폴더(테스트용)")
    a = ap.parse_args()
    if a.cmd in ("all", "collect"):
        collect(a.fixtures)
    if a.cmd in ("all", "build"):
        build()


if __name__ == "__main__":
    main()
