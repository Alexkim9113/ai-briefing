"""임시: 출처가 불분명한 언론사의 실제 도메인을 확인한다(확인 후 삭제)."""
import re, urllib.request, urllib.parse
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=25).read().decode("utf-8", "replace")
for q in ["내일신문", "마이뉴스코리아", "내외신문", "굿데일리", "내일신문 AI", "굿데일리 인공지능"]:
    try:
        raw = get("https://news.google.com/rss/search?q=" + urllib.parse.quote(q) + "&hl=ko&gl=KR&ceid=KR:ko")
        src = re.findall(r'<source url="([^"]*)">([^<]*)</source>', raw)
        from collections import Counter
        print("Q", q, Counter(src).most_common(6))
    except Exception as e:
        print("ERR", q, e)
for u in ["https://www.naeil.com/rss", "https://www.naeil.com/rss/all", "https://www.naewaynews.com/rss/S1N1.xml", "https://www.naewaynews.com/rss/clickTop.xml",
          "https://news.google.com/rss/search?q=AI+site:naewaynews.com+when:2d&hl=ko&gl=KR&ceid=KR:ko",
          "https://news.google.com/rss/search?q=%EC%9D%B8%EA%B3%B5%EC%A7%80%EB%8A%A5+site:naeil.com&hl=ko&gl=KR&ceid=KR:ko",
          "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"]:
    try:
        raw = get(u); t = re.findall(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", raw, re.S)[1:]
        ko = sum(1 for x in t if re.search("[가-힣]", x))
        print("OK", u, "items", len(t), "korean", ko, t[:2])
    except Exception as e:
        print("ERR", u, e)
