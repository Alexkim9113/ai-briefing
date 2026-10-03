"""
OpenClaw -- Operator-only discovery pass.

Scope: KR/US/CN/EU, max 5 NEW items per region per run (20 total max), never padded.
Fully separate from the Public pipeline: NEVER imports, calls, or writes to briefing.py,
root sources.json, or any Public-facing output. Read-only against data/*.json for dedup.

Zero cost: stdlib only (urllib.request + xml.etree.ElementTree). No feedparser, no paid
API, no LLM call. Discover-and-preserve only -- no translation, no summarization (that is
an explicit separate not-yet-approved phase per the brief).

Every candidate feed in sources.json must have "verified": true, set only after an actual
HTTP fetch in a real run returned parseable RSS/Atom/XML. This collector will happily
*attempt* verification (--verify) and will register the real HTTP outcome (success or
failure) rather than trusting the static file blindly. If a fetch fails, the item is
reported as unreachable, not fabricated.
"""
import json
import re
import sys
import hashlib
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA_DIR = ROOT / "data"
SOURCES_PATH = HERE / "sources.json"
OUTPUT_PATH = HERE / "discoveries.json"

USER_AGENT = "METAXIS-OpenClaw/1.0 (operator-only discovery; contact: internal)"
FETCH_TIMEOUT = 15


def log(msg):
    print(f"[openclaw] {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Fetch + parse (stdlib only)
# ---------------------------------------------------------------------------

def fetch_url(url):
    """Returns (ok, body_bytes_or_None, note)."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"})
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            body = resp.read()
            return True, body, f"HTTP {resp.status}"
    except urllib.error.HTTPError as e:
        return False, None, f"HTTPError {e.code}"
    except urllib.error.URLError as e:
        return False, None, f"URLError {e.reason}"
    except Exception as e:  # noqa: BLE001 -- deliberately broad: a bad feed must never crash the run
        return False, None, f"{type(e).__name__}: {e}"


ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}


def parse_feed(body_bytes):
    """Minimal RSS 2.0 / Atom parser using stdlib ElementTree. Returns list of
    dicts: title, link, published, summary. Raises on genuinely unparseable XML
    (caller treats that as a failed verification, never fabricates items)."""
    root = ET.fromstring(body_bytes)
    items = []
    # RSS 2.0: rss/channel/item
    channel = root.find("channel")
    if channel is not None:
        for it in channel.findall("item"):
            title = (it.findtext("title") or "").strip()
            link = (it.findtext("link") or "").strip()
            pub = (it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date") or "").strip()
            summary = (it.findtext("description") or "").strip()
            if title and link:
                items.append({"title": title, "link": link, "published": pub, "summary": summary})
        return items
    # Atom: feed/entry
    if root.tag.endswith("feed"):
        for e in root.findall("a:entry", ATOM_NS):
            title = (e.findtext("a:title", namespaces=ATOM_NS) or "").strip()
            link_el = e.find("a:link", ATOM_NS)
            link = link_el.get("href") if link_el is not None else ""
            pub = (e.findtext("a:published", namespaces=ATOM_NS) or e.findtext("a:updated", namespaces=ATOM_NS) or "").strip()
            summary = (e.findtext("a:summary", namespaces=ATOM_NS) or "").strip()
            if title and link:
                items.append({"title": title, "link": link, "published": pub, "summary": summary})
        return items
    raise ValueError("neither RSS <channel> nor Atom <feed> root found")


def verify_feed(url):
    """Real HTTP fetch + parse attempt. Returns (verified: bool, note: str, items: list)."""
    ok, body, note = fetch_url(url)
    if not ok:
        return False, f"확인 불가 ({note})", []
    try:
        items = parse_feed(body)
        return True, f"검증됨 ({note}, {len(items)}개 항목)", items
    except Exception as e:  # noqa: BLE001
        return False, f"확인 불가 (파싱 실패: {e})", []


# ---------------------------------------------------------------------------
# Dedup against existing METAXIS Public data (data/*.json)
# ---------------------------------------------------------------------------

_WS_RE = re.compile(r"\s+")


def canonicalize_url(url):
    if not url:
        return ""
    u = url.strip()
    u = re.sub(r"^https?://(www\.)?", "", u)
    u = u.split("?")[0].split("#")[0]
    return u.rstrip("/").lower()


def title_key(title):
    t = (title or "").lower()
    t = re.sub(r"[^\w가-힣一-鿿]+", "", t)
    return t


def load_existing_index():
    """Read every data/*.json (the real, already-collected METAXIS Feed) and build
    a dedup index of canonical URLs and title-keys. Read-only -- never mutated."""
    urls = set()
    titles = set()
    if not DATA_DIR.exists():
        return urls, titles
    for fp in sorted(DATA_DIR.glob("20*.json")):
        try:
            d = json.loads(fp.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            log(f"skip unreadable {fp.name}: {e}")
            continue
        for it in d.get("items", []):
            link = it.get("link") or ""
            title = it.get("title") or ""
            if link:
                urls.add(canonicalize_url(link))
            if title:
                titles.add(title_key(title))
    return urls, titles


def is_duplicate(candidate_url, candidate_title, existing_urls, existing_titles):
    cu = canonicalize_url(candidate_url)
    ct = title_key(candidate_title)
    if cu and cu in existing_urls:
        return True
    if ct and ct in existing_titles:
        return True
    return False


# ---------------------------------------------------------------------------
# Main collection
# ---------------------------------------------------------------------------

def collected_at_now():
    return datetime.now(timezone.utc).isoformat()


def make_item_id(canonical_url, title):
    h = hashlib.sha256((canonical_url + "|" + title).encode("utf-8")).hexdigest()
    return h[:16]


def run(do_verify=True, write_sources_back=True):
    sources = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    existing_urls, existing_titles = load_existing_index()
    log(f"loaded dedup index: {len(existing_urls)} urls, {len(existing_titles)} title-keys from data/*.json")

    discoveries = {region: [] for region in sources["regions"]}
    verify_log = {"verified": [], "unverified": []}
    dup_count = 0
    ai_copyright_count = 0

    for region, cfg in sources["regions"].items():
        cap = cfg.get("max_new_per_run", 5)
        all_feeds = list(cfg.get("sources", []))
        axis = cfg.get("ai_copyright_axis")
        if axis:
            all_feeds.extend(axis.get("queries", []))

        for feed in all_feeds:
            feed_id = feed["id"]
            url = feed["url"]
            if do_verify:
                ok, note, raw_items = verify_feed(url)
                feed["verified"] = ok
                feed["verify_note"] = note
                feed["verify_checked_at"] = collected_at_now()
            else:
                ok = feed.get("verified", False)
                raw_items = []
                note = feed.get("verify_note", "not re-checked this run")

            if ok:
                verify_log["verified"].append({"id": feed_id, "region": region, "name": feed.get("name", feed.get("query", feed_id)), "url": url, "note": note})
            else:
                verify_log["unverified"].append({"id": feed_id, "region": region, "name": feed.get("name", feed.get("query", feed_id)), "url": url, "note": note})
                continue  # never register items from an unverified feed

            if len(discoveries[region]) >= cap:
                continue  # region already at cap; still verify remaining feeds for honesty, but stop adding items

            for raw in raw_items:
                if len(discoveries[region]) >= cap:
                    break
                title = raw["title"]
                link = raw["link"]
                if is_duplicate(link, title, existing_urls, existing_titles):
                    dup_count += 1
                    continue
                item = {
                    "id": make_item_id(canonicalize_url(link), title),
                    "original_title": title,
                    "source_name": feed.get("name", feed.get("query", feed_id)),
                    "source_type": feed.get("source_type", "NEWS"),
                    "source_region": region,
                    "original_language": feed.get("original_language", "und"),
                    "published_at": raw.get("published", ""),
                    "canonical_url": link,
                    "collected_at": collected_at_now(),
                    "feed_id": feed_id,
                    "evidence_status": "OPENCLAW_DISCOVERY_ONLY -- Claim 아님",
                    # O-4B: 피드가 제공하는 원문 설명/요약 그대로 보존(가공·번역 없음). relevance_gate.py가
                    # 제목만이 아니라 이 텍스트까지 함께 보고 AI 관련성을 판정하는 데 쓰인다.
                    "raw_description": raw.get("summary", ""),
                }
                discoveries[region].append(item)
                if region == "CN" and feed_id.startswith("cn_ai_copyright"):
                    ai_copyright_count += 1

    total_unique = sum(len(v) for v in discoveries.values())

    output = {
        "codename": "OpenClaw",
        "run_at": collected_at_now(),
        "scope": "KR/US/CN/EU Operator-only discovery, read-only vs Public data, never merged into briefing.py output",
        "regions": discoveries,
        "counts": {region: len(items) for region, items in discoveries.items()},
        "cn_ai_copyright_axis_count": ai_copyright_count,
        "total_duplicates_skipped": dup_count,
        "total_unique_discoveries": total_unique,
        "verification": verify_log,
    }
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"wrote {OUTPUT_PATH}")

    if write_sources_back:
        SOURCES_PATH.write_text(json.dumps(sources, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"updated verified/verify_note fields in {SOURCES_PATH}")

    return output


if __name__ == "__main__":
    result = run(do_verify=True, write_sources_back=True)
    print(json.dumps(result["counts"], ensure_ascii=False, indent=2))
    print(f"total_unique_discoveries: {result['total_unique_discoveries']}")
    print(f"total_duplicates_skipped: {result['total_duplicates_skipped']}")
    print(f"cn_ai_copyright_axis_count: {result['cn_ai_copyright_axis_count']}")
    print(f"verified feeds: {len(result['verification']['verified'])}")
    print(f"unverified feeds: {len(result['verification']['unverified'])}")
