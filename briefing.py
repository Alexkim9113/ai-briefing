#!/usr/bin/env python3
"""매일 AI 브리핑: RSS/Atom/JSON 소스를 모아 정적 사이트(site/)를 만든다.

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
DEDUPE_DAYS = 7            # 최근 N일 브리핑에 이미 나온 글은 제외
USER_AGENT = "Mozilla/5.0 (compatible; AI-Briefing-Bot/1.0; +https://github.com)"


# ---------------------------------------------------------------- 수집

def fetch(url, fixtures=None):
    if fixtures:
        name = hashlib.sha1(url.encode()).hexdigest()[:12]
        for ext in (".xml", ".json"):
            p = Path(fixtures) / (name + ext)
            if p.exists():
                return p.read_bytes()
        raise FileNotFoundError(f"fixture {name} 없음")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
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


_IMG_SRC = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"']", re.I)


def rss_image(e, html_text):
    """RSS 항목에서 대표 이미지 주소를 찾는다(media:content, media:thumbnail, enclosure, 본문 img)."""
    for c in e.iter():
        name = local(c.tag)
        url = c.get("url", "")
        if not url:
            continue
        if name == "thumbnail" or (name == "content" and (c.get("medium") == "image" or c.get("type", "").startswith("image"))) \
                or (name == "enclosure" and c.get("type", "").startswith("image")):
            return url
    m = _IMG_SRC.search(html.unescape(html_text or ""))
    return m.group(1) if m and m.group(1).startswith("http") else ""


def parse_feed(raw):
    """RSS 2.0 / RSS 1.0(RDF) / Atom 을 공통 형식으로 변환."""
    root = parse_xml(raw)
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
            thumb = ""
            group = child(e, "group")  # YouTube media:group
            if group is not None:
                desc = desc or text_of(group, "description")
                t = child(group, "thumbnail")
                if t is not None:
                    thumb = t.get("url", "")
            items.append({"title": text_of(e, "title"), "link": link, "desc": desc,
                          "date": text_of(e, "published", "updated"), "thumb": thumb})
    else:  # RSS 2.0 / RDF
        nodes = root.iter()
        for e in nodes:
            if local(e.tag) != "item":
                continue
            link = text_of(e, "link") or (child(e, "guid").text if child(e, "guid") is not None else "")
            desc = text_of(e, "description", "encoded", "summary")
            items.append({"title": text_of(e, "title"), "link": (link or "").strip(), "desc": desc,
                          "date": text_of(e, "pubdate", "date", "published", "updated"),
                          "thumb": rss_image(e, desc + " " + text_of(e, "encoded"))})
    return items


def parse_hf_papers(raw):
    items = []
    for row in json.loads(raw):
        p = row.get("paper", row)
        pid = p.get("id", "")
        items.append({"title": p.get("title", ""), "link": f"https://huggingface.co/papers/{pid}",
                      "desc": p.get("summary", ""), "date": row.get("publishedAt") or p.get("publishedAt", ""),
                      "thumb": f"https://cdn-thumbnails.huggingface.co/social-thumbnails/papers/{pid}.png" if pid else "",
                      "score": p.get("upvotes", 0)})
    items.sort(key=lambda x: -x.get("score", 0))
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


def collect_source(src, fixtures):
    raw = fetch(src["url"], fixtures)
    return parse_hf_papers(raw) if src.get("type") == "hf_papers" else parse_feed(raw)


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
                status.append({"name": src["name"], "ok": False, "count": 0, "error": f"{type(e).__name__}: {e}"[:200]})
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
                if src.get("filter") and not is_ai_related(it, keywords):
                    continue
                iid = item_id(it["link"], title)
                if iid in seen:
                    continue
                kept.append({
                    "id": iid, "title": title, "link": it["link"], "source": src["name"],
                    "category": src["category"], "published": d.isoformat() if d else None,
                    "summary": summarize(it["desc"], title), "thumb": it.get("thumb", ""),
                })
                if len(kept) >= src.get("limit", DEFAULT_LIMIT):
                    break
            status.append({"name": src["name"], "ok": True, "count": len(kept), "fetched": len(raw_items)})
            results.extend(kept)

    if not fixtures:
        add_og_images(results)

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
    data = {"date": today.isoformat(), "generated_at": now.astimezone(KST).isoformat(timespec="minutes"),
            "items": uniq, "status": sorted(status, key=lambda s: s["name"])}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(s["ok"] for s in status)
    print(f"[collect] {today} 항목 {len(uniq)}개, 소스 {ok}/{len(status)} 성공 → {path.relative_to(ROOT)}")
    return data


_OG = re.compile(r"<meta[^>]+(?:property|name)=[\"'](?:og:image|twitter:image)[\"'][^>]*>", re.I)
_CONTENT = re.compile(r"content=[\"']([^\"']+)[\"']", re.I)


def og_image(link):
    req = urllib.request.Request(link, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=10) as r:
        head = r.read(300_000).decode("utf-8", errors="ignore")
    m = _OG.search(head)
    c = _CONTENT.search(m.group(0)) if m else None
    url = html.unescape(c.group(1)) if c else ""
    return urllib.parse.urljoin(link, url) if url else ""


def add_og_images(items, max_fetch=60):
    """썸네일이 없는 기사만 원문 페이지의 대표 이미지(og:image) 주소를 가져온다. 이미지는 복사하지 않고 링크만 쓴다."""
    todo = [it for it in items if not it["thumb"] and it["category"] in ("news_ko", "news_global", "policy")
            and "news.google.com" not in it["link"]][:max_fetch]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for it, fut in [(it, pool.submit(og_image, it["link"])) for it in todo]:
            try:
                it["thumb"] = fut.result()
            except Exception:
                pass
    print(f"[collect] 대표 이미지 {sum(1 for it in todo if it['thumb'])}/{len(todo)}개 확보")


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
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 Pretendard,-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}
.serif{font-family:"Noto Serif KR",Georgia,serif}
.wrap{max-width:1200px;margin:0 auto;padding:0 20px}
.bar{background:var(--bar);color:var(--bar-text)}
.bar .wrap{display:flex;align-items:center;gap:28px;height:64px}
.logo{display:flex;align-items:center;gap:10px;font-size:21px;letter-spacing:.5px;white-space:nowrap}
.logo svg{flex:none}
.bar nav{display:flex;gap:22px;flex:1;justify-content:center;font-size:14.5px;overflow-x:auto;scrollbar-width:none}
.bar nav a{opacity:.72;padding:4px 0;border-bottom:2px solid transparent;white-space:nowrap}
.bar nav a:hover,.bar nav a.on{opacity:1;border-color:var(--bar-text)}
.search{display:flex;align-items:center;gap:8px;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.14);border-radius:99px;padding:7px 14px;width:230px}
.search input{background:none;border:0;outline:0;color:var(--bar-text);font:inherit;font-size:14px;width:100%}
.search input::placeholder{color:rgba(243,230,235,.55)}
.hero{display:grid;grid-template-columns:1.12fr 1fr;gap:56px;padding:36px 0 28px}
.hero h1{font-size:32px;line-height:1.3;font-weight:500;color:var(--accent);margin:0 0 18px}
.badge{display:inline-block;vertical-align:middle;background:var(--accent);color:#fff;font:600 12px/1 Pretendard,sans-serif;padding:7px 12px;border-radius:99px;margin-left:10px;position:relative;top:-3px;box-shadow:var(--shadow)}
.thumb{position:relative;display:block;overflow:hidden;border-radius:16px;aspect-ratio:16/9;box-shadow:var(--shadow);background:linear-gradient(135deg,var(--g1,#3d0f22),var(--g2,#7a1f3d))}
.thumb img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.thumb .ph{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:flex-end;padding:14px 16px;color:#fff}
.thumb .ph b{font-family:"Noto Serif KR",Georgia,serif;font-weight:500;font-size:18px}.thumb .ph span{font-size:12px;opacity:.75}
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
.trend .thumb{border-radius:12px}.trend .thumb .ph b{font-size:13px}.trend .thumb .ph{padding:8px 10px}
.trend h3{font-size:16.5px;line-height:1.4;font-weight:500;color:var(--accent);margin:0 0 4px}
.trend p{margin:0 0 4px;font-size:13px;color:var(--muted);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.kw{display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:18px 0;border-top:1px solid var(--line)}
.kw strong{font-size:14px;margin-right:4px}.kw span{background:var(--soft);color:var(--accent);border-radius:99px;padding:3px 12px;font-size:13px}
.kw .info{background:none;color:var(--muted);margin-left:auto;padding:0}
.tabs{position:sticky;top:0;z-index:2;background:var(--bg);display:flex;gap:8px;overflow-x:auto;padding:12px 0;border-bottom:1px solid var(--line);scrollbar-width:none}
.tabs button{border:1px solid var(--line);background:var(--card);color:var(--text);border-radius:99px;padding:7px 16px;font:inherit;font-size:14px;cursor:pointer;white-space:nowrap}
.tabs button.on{background:var(--accent);border-color:var(--accent);color:#fff}
section.cat>h2{font-size:24px;font-weight:500;margin:34px 0 16px;color:var(--accent)}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:28px 24px}
.card h3{font-size:17px;line-height:1.45;font-weight:500;margin:14px 0 6px}
.card h3 a:hover,.trend h3 a:hover,.hero h1 a:hover{text-decoration:underline}
.card p{margin:0 0 8px;font-size:14px;color:var(--muted);display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.list{display:grid;grid-template-columns:1fr 1fr;gap:0 40px;margin-top:18px}
.row{padding:14px 0 12px;border-bottom:1px solid var(--line)}.row h3{margin:0 0 4px;font-size:16px}.row p{-webkit-line-clamp:2;margin-bottom:6px}
.empty{color:var(--muted);font-size:14px}
footer{margin-top:56px;padding-top:26px;padding-bottom:40px;border-top:1px solid var(--line);font-size:13px;color:var(--muted)}
details summary{cursor:pointer}ul.st{columns:3;padding-left:18px}ul.st .bad{color:#c2410c}
ul.days{list-style:none;padding:0;max-width:640px}ul.days li{padding:12px 0;border-bottom:1px solid var(--line)}ul.days a{color:var(--accent)}
[hidden]{display:none!important}
@media (max-width:960px){.hero{grid-template-columns:1fr;gap:32px}.grid{grid-template-columns:repeat(2,1fr)}.search{display:none}.bar nav{justify-content:flex-start}}
@media (max-width:600px){.wrap{padding:0 16px}.hero{padding-top:22px}.hero h1{font-size:25px}.grid,.list{grid-template-columns:1fr}
.trend{grid-template-columns:112px 1fr;gap:12px}.trend h3{font-size:15px}ul.st{columns:1}.bar .wrap{gap:16px}.logo span{display:none}.kw .info{margin-left:0;width:100%}}
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
CAT_COLORS = {"news_ko": ("#3d0f22", "#8a2748"), "news_global": ("#2a1030", "#6b2d6b"), "papers": ("#1c1636", "#4b3a8c"),
              "policy": ("#10262a", "#2f6b67"), "youtube": ("#2b0d0d", "#9b2c2c")}
ICON_CLOCK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>'
ICON_SRC = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 5h16v14H4z"/><path d="M8 9h8M8 13h5"/></svg>'
ICON_SHARE = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4"/></svg>'
ICON_SEARCH = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>'
LOGO = '<svg width="30" height="30" viewBox="0 0 32 32" fill="none" stroke="#c9738f" stroke-width="2"><path d="M4 6l12 21L28 6"/><path d="M10 6l6 11 6-11"/></svg>'
FAVICON = ("data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 32 32%22>"
           "<rect width=%2232%22 height=%2232%22 rx=%227%22 fill=%22%232a0b17%22/>"
           "<path d=%22M7 8l9 16 9-16%22 fill=%22none%22 stroke=%22%23e58fae%22 stroke-width=%223%22/></svg>")


def esc(s):
    return html.escape(s or "", quote=True)


def fmt_time(iso):
    if not iso:
        return ""
    d = datetime.fromisoformat(iso).astimezone(KST)
    return d.strftime("%m.%d %H:%M")


def page(title, body, base="", cats=None, search=True):
    nav = f'<a href="{base}index.html" class="on">오늘</a>'
    if cats:
        nav += "".join(f'<a href="#{c}" data-go="{c}">{esc(n)}</a>' for c, n in cats.items())
    nav += f'<a href="{base}archive.html">지난 브리핑</a>'
    box = (f'<label class="search">{ICON_SEARCH}<input type="search" placeholder="뉴스, 주제 검색" aria-label="검색"></label>'
           if search else "")
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title>
<meta name="description" content="국내외 AI 뉴스·논문·정책·유튜브를 매일 자동으로 모아 보여주는 AI 브리핑">
<link rel="icon" href="{FAVICON}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
<style>{CSS}</style></head><body>
<header class="bar"><div class="wrap"><a class="logo serif" href="{base}index.html">{LOGO}<span>AI 브리핑</span></a><nav>{nav}</nav>{box}</div></header>
<main class="wrap">{body}</main>
<footer class="wrap">매일 오전 6시와 오후 6시에 자동으로 수집됩니다. 요약은 원문 앞부분을 자동 발췌한 것이며, 기사와 이미지의 저작권은 원 저작자에게 있습니다. 전문은 각 원문 링크에서 확인하세요.</footer>
<script>{JS}</script></body></html>"""


def thumb_html(it, cats):
    g1, g2 = CAT_COLORS.get(it["category"], CAT_COLORS["news_ko"])
    img = (f'<img src="{esc(it["thumb"])}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">'
           if it.get("thumb") else "")
    return (f'<a class="thumb" href="{esc(it["link"])}" target="_blank" rel="noopener" style="--g1:{g1};--g2:{g2}" tabindex="-1" aria-hidden="true">'
            f'<div class="ph"><b>{esc(cats.get(it["category"], ""))}</b><span>{esc(it["source"])}</span></div>{img}</a>')


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
    """헤드라인 1개 + 주요 소식 4개. 이미지가 있는 뉴스를 우선하고 분야가 겹치지 않게 고른다."""
    pri = {"news_ko": 0, "news_global": 1, "policy": 2, "youtube": 3, "papers": 4}
    ranked = sorted(items, key=lambda i: (not i.get("thumb"), not i.get("summary"), pri.get(i["category"], 9)))
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


def render_day(data, cats, base=""):
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
            f'<div class="hero"><div><h1 class="serif">{title_link(hero)}<span class="badge">오늘의 헤드라인</span></h1>'
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
            if it.get("thumb"):
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
    return page(f"AI 브리핑 {data['date']}", "\n".join(parts), base, cats)


def build(keep_days=None):
    cfg = load_config()
    cats = cfg["categories"]
    files = sorted(DATA_DIR.glob("*.json"), reverse=True)
    if not files:
        print("[build] 데이터가 없습니다. 먼저 collect 를 실행하세요.", file=sys.stderr)
        return
    (SITE_DIR / "archive").mkdir(parents=True, exist_ok=True)
    days = []
    for i, f in enumerate(files):
        data = json.loads(f.read_text(encoding="utf-8"))
        days.append((data["date"], len(data["items"])))
        (SITE_DIR / "archive" / f"{data['date']}.html").write_text(render_day(data, cats, "../"), encoding="utf-8")
        if i == 0:
            (SITE_DIR / "index.html").write_text(render_day(data, cats), encoding="utf-8")
    lis = "".join(f'<li><a href="archive/{d}.html">{d} ({WEEKDAYS[datetime.fromisoformat(d).weekday()]})</a> <span class="meta">· {n}건</span></li>' for d, n in days)
    (SITE_DIR / "archive.html").write_text(page("지난 브리핑 - AI 브리핑", f'<h2 class="serif" style="font-weight:500;font-size:26px;margin:36px 0 12px">지난 브리핑</h2><ul class="days">{lis}</ul>', search=False), encoding="utf-8")
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
