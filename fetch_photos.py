import briefing as b, json
from datetime import datetime, timezone, timedelta
now=datetime.now(timezone.utc)
U={
"gn_ai":"https://news.google.com/rss/search?q=%22artificial+intelligence%22+when:1d&hl=en-US&gl=US&ceid=US:en",
"gn_co":"https://news.google.com/rss/search?q=(OpenAI+OR+Anthropic+OR+Nvidia+OR+Gemini+OR+%22Meta+AI%22)+when:1d&hl=en-US&gl=US&ceid=US:en",
"ars":"https://arstechnica.com/ai/feed/","wired":"https://www.wired.com/feed/tag/ai/latest/rss","decoder":"https://the-decoder.com/feed/",
"ainews":"https://www.artificialintelligence-news.com/feed/","mtp":"https://www.marktechpost.com/feed/",
"zdnet":"https://www.zdnet.com/topic/artificial-intelligence/rss.xml","guardian":"https://www.theguardian.com/technology/artificialintelligence/rss",
"engadget":"https://www.engadget.com/rss.xml","vb":"https://venturebeat.com/category/ai/feed/","openai":"https://openai.com/news/rss.xml",
"deepmind":"https://deepmind.google/blog/rss.xml","hf":"https://huggingface.co/blog/feed.xml","googleai":"https://blog.google/technology/ai/rss/","mittr":"https://www.technologyreview.com/topic/artificial-intelligence/feed",
"siliconangle":"https://siliconangle.com/category/ai/feed/","techxplore":"https://techxplore.com/rss-feed/machine-learning-ai-news/"}
for k,u in U.items():
    try:
        its=b.parse_feed(b.fetch(u)); ds=[b.parse_date(i["date"]) for i in its]
        fresh=sum(1 for d in ds if d and d>now-timedelta(hours=36)); newest=max([d for d in ds if d],default=None)
        print(k,len(its),"fresh36h",fresh,"newest",newest)
    except Exception as e: print(k,"ERR",e)
