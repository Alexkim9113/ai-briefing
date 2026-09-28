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
            items.append({"title": text_of(e, "title"), "link": (link or "").strip(),
                          "desc": text_of(e, "description", "encoded", "summary"),
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


# ---------------------------------------------------------------- 요약

_COMMENT = re.compile(r"<!--.*?(-->|$)", re.S)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_ARXIV_PREFIX = re.compile(r"^arXiv:\S+\s+Announce Type:\s*\S+\s*(Abstract:)?\s*", re.I)
_SENT = re.compile(r"(?<=[.!?。])\s+|(?<=다\.)\s*|(?<=요\.)\s*")


def clean_text(s):
    s = _COMMENT.sub(" ", s or "")
    s = _TAG.sub(" ", s)
    s = html.unescape(html.unescape(s))
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
:root{--bg:#f7f7f5;--card:#fff;--text:#1d1d1f;--muted:#6b6b70;--line:#e4e4e0;--accent:#3b5bdb;--chip:#eef1fb}
@media (prefers-color-scheme:dark){:root{--bg:#141416;--card:#1e1e22;--text:#ececef;--muted:#9a9aa3;--line:#2e2e34;--accent:#8ea2ff;--chip:#262a3a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR","Malgun Gothic",sans-serif}
.wrap{max-width:860px;margin:0 auto;padding:24px 16px 64px}
header h1{font-size:26px;margin:0}header p{color:var(--muted);margin:4px 0 0}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
nav.top{display:flex;gap:14px;margin:6px 0 18px;font-size:14px}
.kw{display:flex;flex-wrap:wrap;gap:6px;margin:16px 0}.kw span{background:var(--chip);border-radius:99px;padding:2px 10px;font-size:13px}
.tabs{position:sticky;top:0;background:var(--bg);display:flex;gap:6px;overflow-x:auto;padding:10px 0;border-bottom:1px solid var(--line);z-index:1}
.tabs button{border:1px solid var(--line);background:var(--card);color:var(--text);border-radius:99px;padding:6px 14px;font:inherit;font-size:14px;cursor:pointer;white-space:nowrap}
.tabs button.on{background:var(--accent);border-color:var(--accent);color:#fff}
section h2{font-size:19px;margin:28px 0 10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:10px 0;display:flex;gap:14px}
.card img{width:140px;height:79px;object-fit:cover;border-radius:8px;flex:none}
.card h3{font-size:16px;margin:0 0 4px;line-height:1.45}.meta{font-size:12.5px;color:var(--muted)}
.card p{margin:6px 0 0;font-size:14px;color:var(--muted)}
.empty{color:var(--muted);font-size:14px}
footer{margin-top:40px;font-size:12.5px;color:var(--muted);border-top:1px solid var(--line);padding-top:16px}
details summary{cursor:pointer}ul.st{columns:2;padding-left:18px}ul.st .bad{color:#d9480f}
ul.days{list-style:none;padding:0}ul.days li{padding:8px 0;border-bottom:1px solid var(--line)}
@media (max-width:560px){.card{flex-direction:column}.card img{width:100%;height:auto;aspect-ratio:16/9}ul.st{columns:1}}
"""

JS = """
document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>{
 document.querySelectorAll('.tabs button').forEach(x=>x.classList.toggle('on',x===b));
 const c=b.dataset.cat;document.querySelectorAll('section[data-cat]').forEach(s=>s.hidden=c!=='all'&&s.dataset.cat!==c);});
"""

WEEKDAYS = "월화수목금토일"


def esc(s):
    return html.escape(s or "", quote=True)


def fmt_time(iso):
    if not iso:
        return ""
    d = datetime.fromisoformat(iso).astimezone(KST)
    return d.strftime("%m.%d %H:%M")


def page(title, body, base=""):
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title>
<meta name="description" content="국내외 AI 뉴스·논문·정책·유튜브를 매일 자동으로 모아 보여주는 AI 브리핑">
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>📰</text></svg>">
<style>{CSS}</style></head><body><div class="wrap">
<header><h1><a href="{base}index.html" style="color:inherit">AI 브리핑</a></h1></header>
<nav class="top"><a href="{base}index.html">오늘</a><a href="{base}archive.html">지난 브리핑</a></nav>
{body}
<footer>매일 아침 자동으로 수집됩니다. 요약은 원문 앞부분을 자동 발췌한 것이며, 모든 저작권은 원 저작자에게 있습니다. 전문은 각 원문 링크에서 확인하세요.</footer>
</div><script>{JS}</script></body></html>"""


def render_day(data, cats, base=""):
    d = datetime.fromisoformat(data["date"])
    by_cat = {c: [] for c in cats}
    for it in data["items"]:
        by_cat.setdefault(it["category"], []).append(it)
    kws = top_keywords(data["items"])
    parts = [f'<p class="meta">{d.year}년 {d.month}월 {d.day}일 ({WEEKDAYS[d.weekday()]}) · 총 {len(data["items"])}건 · {esc(data["generated_at"][11:16])} 업데이트</p>']
    if kws:
        parts.append('<div class="kw">' + "".join(f"<span>#{esc(k)}</span>" for k in kws) + "</div>")
    tabs = ['<button class="on" data-cat="all">전체</button>']
    tabs += [f'<button data-cat="{c}">{esc(n)} {len(by_cat.get(c, []))}</button>' for c, n in cats.items()]
    parts.append('<div class="tabs">' + "".join(tabs) + "</div>")
    for c, name in cats.items():
        items = by_cat.get(c, [])
        cards = []
        for it in items:
            img = f'<img src="{esc(it["thumb"])}" alt="" loading="lazy">' if it.get("thumb") else ""
            summ = f"<p>{esc(it['summary'])}</p>" if it.get("summary") else ""
            t = fmt_time(it.get("published"))
            cards.append(f'<article class="card">{img}<div><h3><a href="{esc(it["link"])}" target="_blank" rel="noopener">{esc(it["title"])}</a></h3>'
                         f'<div class="meta">{esc(it["source"])}{" · " + t if t else ""}</div>{summ}</div></article>')
        body = "".join(cards) or '<p class="empty">오늘은 새 소식이 없습니다.</p>'
        parts.append(f'<section data-cat="{c}"><h2>{esc(name)}</h2>{body}</section>')
    st = data.get("status", [])
    ok = sum(s["ok"] for s in st)
    lis = "".join(f'<li class="{"" if s["ok"] else "bad"}">{esc(s["name"])}: '
                  f'{str(s["count"]) + "건" if s["ok"] else "실패"}</li>' for s in st)
    parts.append(f'<details style="margin-top:28px"><summary class="meta">수집 상태: 소스 {ok}/{len(st)}개 성공</summary><ul class="st meta">{lis}</ul></details>')
    return page(f"AI 브리핑 {data['date']}", "\n".join(parts), base)


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
    (SITE_DIR / "archive.html").write_text(page("지난 브리핑 - AI 브리핑", f"<h2>지난 브리핑</h2><ul class=\"days\">{lis}</ul>"), encoding="utf-8")
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
