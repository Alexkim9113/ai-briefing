"""임시: 새 언론사 RSS 후보 주소를 GitHub 서버에서 확인한다(확인 후 삭제)."""
import re
import urllib.request

C = {
    "조선일보": ["https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml", "https://www.chosun.com/arc/outboundfeeds/rss/category/economy/tech_it/?outputType=xml"],
    "중앙일보": ["https://news.google.com/rss/search?q=AI+site:joongang.co.kr+when:2d&hl=ko&gl=KR&ceid=KR:ko", "https://rss.joins.com/joins_news_list.xml"],
    "동아일보": ["https://rss.donga.com/total.xml", "https://rss.donga.com/science.xml"],
    "문화일보": ["https://www.munhwa.com/rss/all.xml", "http://www.munhwa.com/news/rss/all.xml", "https://news.google.com/rss/search?q=AI+site:munhwa.com+when:2d&hl=ko&gl=KR&ceid=KR:ko"],
    "국민일보": ["https://www.kmib.co.kr/rss/data/kmibRssAll.xml", "https://news.google.com/rss/search?q=AI+site:kmib.co.kr+when:2d&hl=ko&gl=KR&ceid=KR:ko"],
    "한겨레": ["https://www.hani.co.kr/rss/", "https://www.hani.co.kr/rss/science/"],
    "경향신문": ["https://www.khan.co.kr/rss/rssdata/total_news.xml", "https://www.khan.co.kr/rss/rssdata/it_news.xml"],
    "서울신문": ["https://www.seoul.co.kr/xml/rss/rss_top_news.xml", "https://news.google.com/rss/search?q=AI+site:seoul.co.kr+when:2d&hl=ko&gl=KR&ceid=KR:ko"],
    "한국일보": ["https://www.hankookilbo.com/rss", "https://news.google.com/rss/search?q=AI+site:hankookilbo.com+when:2d&hl=ko&gl=KR&ceid=KR:ko"],
    "내일신문": ["https://www.naeil.com/rss/allArticle.xml", "https://news.google.com/rss/search?q=AI+site:naeil.com+when:2d&hl=ko&gl=KR&ceid=KR:ko"],
    "한국경제": ["https://www.hankyung.com/feed/it", "https://www.hankyung.com/feed/all-news"],
    "매일경제": ["https://www.mk.co.kr/rss/50300009/", "https://www.mk.co.kr/rss/30000001/"],
    "머니투데이": ["https://rss.mt.co.kr/mt_news.xml", "https://news.google.com/rss/search?q=AI+site:mt.co.kr+when:2d&hl=ko&gl=KR&ceid=KR:ko"],
    "이데일리": ["http://rss.edaily.co.kr/edaily_news.xml", "https://news.google.com/rss/search?q=AI+site:edaily.co.kr+when:2d&hl=ko&gl=KR&ceid=KR:ko"],
    "아주경제": ["https://www.ajunews.com/rss/all.xml", "https://news.google.com/rss/search?q=AI+site:ajunews.com+when:2d&hl=ko&gl=KR&ceid=KR:ko"],
    "오마이뉴스": ["http://rss.ohmynews.com/rss/ohmynews.xml", "http://rss.ohmynews.com/rss/science.xml"],
    "프레시안": ["https://www.pressian.com/api/v3/site/rss/news", "https://news.google.com/rss/search?q=AI+site:pressian.com+when:2d&hl=ko&gl=KR&ceid=KR:ko"],
    "마이뉴스코리아": ["https://www.mynewskorea.com/rss/allArticle.xml", "https://www.mynewskorea.co.kr/rss/allArticle.xml", "https://news.google.com/rss/search?q=%EB%A7%88%EC%9D%B4%EB%89%B4%EC%8A%A4%EC%BD%94%EB%A6%AC%EC%95%84+AI&hl=ko&gl=KR&ceid=KR:ko"],
    "내외신문": ["https://www.naewoenews.com/rss/allArticle.xml", "https://www.naewaynews.com/rss/allArticle.xml", "https://news.google.com/rss/search?q=%EB%82%B4%EC%99%B8%EC%8B%A0%EB%AC%B8+AI&hl=ko&gl=KR&ceid=KR:ko"],
    "굿데일리": ["https://www.gooddaily.co.kr/rss/allArticle.xml", "https://www.good-daily.co.kr/rss/allArticle.xml", "https://news.google.com/rss/search?q=%EA%B5%BF%EB%8D%B0%EC%9D%BC%EB%A6%AC+AI&hl=ko&gl=KR&ceid=KR:ko"],
    "기독연합뉴스": ["https://www.cupnews.kr/rss/allArticle.xml", "https://news.google.com/rss/search?q=%EA%B8%B0%EB%8F%85%EC%97%B0%ED%95%A9%EB%89%B4%EC%8A%A4+AI&hl=ko&gl=KR&ceid=KR:ko"],
    "불교신문": ["https://www.ibulgyo.com/rss/allArticle.xml", "https://news.google.com/rss/search?q=AI+site:ibulgyo.com&hl=ko&gl=KR&ceid=KR:ko"],
    "연합뉴스": ["https://www.yna.co.kr/rss/news.xml", "https://www.yna.co.kr/rss/industry.xml"],
    "뉴시스": ["https://newsis.com/RSS/sokbo.xml", "https://newsis.com/RSS/it.xml"],
    "더팩트": ['https://news.tf.co.kr/rss/all.xml', 'https://rss.tf.co.kr/rss/news.xml', 'https://news.google.com/rss/search?q=AI+site:tf.co.kr+when:2d&hl=ko&gl=KR&ceid=KR:ko'],
    "아시아투데이": ['https://www.asiatoday.co.kr/rss/all.xml', 'https://www.asiatoday.co.kr/rss/rss.php', 'https://news.google.com/rss/search?q=AI+site:asiatoday.co.kr+when:2d&hl=ko&gl=KR&ceid=KR:ko'],
    "로리더": ['https://www.lawleader.co.kr/rss/allArticle.xml', 'https://news.google.com/rss/search?q=AI+site:lawleader.co.kr+when:2d&hl=ko&gl=KR&ceid=KR:ko'],
    "법률저널": ['https://www.lec.co.kr/rss/allArticle.xml', 'https://news.google.com/rss/search?q=AI+site:lec.co.kr+when:2d&hl=ko&gl=KR&ceid=KR:ko'],
    "뉴스핌": ['https://www.newspim.com/rss/newspim_rss.xml', 'https://news.google.com/rss/search?q=AI+site:newspim.com+when:2d&hl=ko&gl=KR&ceid=KR:ko'],
    "IT비즈뉴스": ['https://www.itbiznews.com/rss/allArticle.xml', 'https://news.google.com/rss/search?q=AI+site:itbiznews.com+when:2d&hl=ko&gl=KR&ceid=KR:ko'],
    "헤럴드경제": ['https://biz.heraldcorp.com/rss/google/it', 'https://news.google.com/rss/search?q=AI+site:heraldcorp.com+when:2d&hl=ko&gl=KR&ceid=KR:ko'],
    "파이낸셜뉴스": ['https://www.fnnews.com/rss/r20/fn_realnews_all.xml', 'https://www.fnnews.com/rss/r20/fn_realnews_it.xml', 'https://news.google.com/rss/search?q=AI+site:fnnews.com+when:2d&hl=ko&gl=KR&ceid=KR:ko'],
    "국제뉴스": ['https://www.gukjenews.com/rss/allArticle.xml', 'https://news.google.com/rss/search?q=AI+site:gukjenews.com+when:2d&hl=ko&gl=KR&ceid=KR:ko'],
    "데일리안": ['https://www.dailian.co.kr/rss/all.xml', 'https://news.google.com/rss/search?q=AI+site:dailian.co.kr+when:2d&hl=ko&gl=KR&ceid=KR:ko'],
}
AI = re.compile(r"AI|인공지능|에이아이|GPT|LLM|생성형|챗봇|딥러닝|머신러닝|오픈AI|엔비디아|앤트로픽|제미나이|클로드", re.I)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
for name, urls in C.items():
    for u in urls:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": UA, "Accept": "application/rss+xml,application/xml,text/xml,*/*"})
            raw = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
            titles = re.findall(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", raw, re.S)[1:]
            desc = len(re.findall(r"<description>", raw))
            ai = [t for t in titles if AI.search(t)]
            print(f"OK  {name} | {u} | items={len(titles)} ai={len(ai)} desc={desc} | {(ai[:1] or titles[:1] or [''])[0][:60]}")
        except Exception as e:
            print(f"ERR {name} | {u} | {type(e).__name__}: {str(e)[:80]}")
