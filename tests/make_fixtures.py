"""테스트용 가짜 피드를 만든다(실제 네트워크 없이 파이프라인 검증)."""
import hashlib, json, sys
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
out = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "tests" / "fixtures")
out.mkdir(parents=True, exist_ok=True)
now = datetime.now(timezone.utc)
cfg = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))

def name(url): return hashlib.sha1(url.encode()).hexdigest()[:12]

def rss(src, n=4):
    items = ""
    for i in range(n):
        d = format_datetime(now - timedelta(hours=3 * i + (50 if i == n - 1 else 0)))  # 마지막 항목은 오래된 글
        topic = "AI" if i % 2 == 0 else "스마트폰"
        items += f"""<item><title>{src['name']} {topic} 소식 {i} - 테스트언론</title>
<link>https://example.com/{name(src['url'])}/{i}?utm_source=rss</link>
<description><![CDATA[<p>{topic} 관련 첫 번째 문장입니다. 두 번째 문장은 조금 더 길게 작성되어 요약 길이 제한을 시험합니다.
세 번째 문장은&nbsp;잘려야 합니다. 네 번째 문장도 있습니다. 다섯 번째 문장은 확실히 잘립니다.</p>]]></description>
<pubDate>{d}</pubDate></item>"""
    return f'<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>{items}</channel></rss>'

def atom(src):
    es = ""
    for i in range(3):
        d = (now - timedelta(hours=5 * i)).isoformat().replace("+00:00", "Z")
        es += f"""<entry><title>{src['name']} 영상 {i}: New AI model explained</title>
<link rel="alternate" href="https://www.youtube.com/watch?v=vid{i}{name(src['url'])[:4]}"/>
<published>{d}</published><media:group><media:title>t</media:title>
<media:thumbnail url="https://i.ytimg.com/vi/vid{i}/hqdefault.jpg" width="480" height="360"/>
<media:description>In this video we look at a new AI model &amp; what it means. Second sentence.</media:description></media:group></entry>"""
    return f'<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/">{es}</feed>'

for src in cfg["sources"]:
    url = src["url"]
    if src.get("type") == "hf_papers":
        rows = [{"publishedAt": now.isoformat(), "paper": {"id": f"2609.0{i}123", "title": f"Scaling Agents Paper {i}",
                 "summary": "We propose a method for training language agents. It outperforms baselines by a wide margin. More details follow.", "upvotes": i * 7}} for i in range(5)]
        (out / (name(url) + ".json")).write_text(json.dumps(rows))
    elif "youtube.com" in url:
        (out / (name(url) + ".xml")).write_text(atom(src))
    elif "msit" in url:
        continue  # 실패하는 소스 흉내
    elif "arxiv" in url:
        x = rss(src).replace("<description><![CDATA[", "<description><![CDATA[arXiv:2609.01234v1 Announce Type: new Abstract: ")
        (out / (name(url) + ".xml")).write_text(x)
    elif "theverge" in url:
        (out / (name(url) + ".xml")).write_text(rss(src).replace("테스트언론", "R&D") + "")  # 이스케이프 안 된 & (깨진 XML)
    else:
        (out / (name(url) + ".xml")).write_text(rss(src))
print("fixtures ->", out)
