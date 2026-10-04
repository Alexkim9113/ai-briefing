#!/usr/bin/env python3
"""METAXIS Operator final presentation/synthesis layer.
Private Operator only. Does not mutate canonical claims/hypotheses/intelligence_objects/reports.
Builds readable Intelligence + periodic Brief reports from collected corpus, repairs legacy report links,
and cleans HTML-entity titles. LLM use is optional via GEMINI_KEY; deterministic fallback is honest.
"""
from __future__ import annotations
import calendar, datetime as dt, html, json, os, re, urllib.request
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'data'; OP=ROOT/'intel_private'/'operator'; OUT=ROOT/'intel_private'/'periodic_reports'
KST=dt.timezone(dt.timedelta(hours=9))
MODEL=os.getenv('GEMINI_MODEL','gemini-2.5-flash')

CSS="""<style>:root{--bg:#07061a;--card:#0f0d26;--ink:#eceef6;--text:#d9dcea;--sub:#9097b3;--line:#1f1c40;--accent:#9ab8ff}*{box-sizing:border-box}body{margin:0;background:#07061a;color:var(--text);font:15.5px/1.75 Pretendard,Arial,sans-serif}header,nav,main{max-width:1040px;margin:auto}header{padding:22px 24px 10px}nav{padding:8px 24px 18px;border-bottom:1px solid var(--line)}nav a{color:var(--sub);margin-right:20px;text-decoration:none}main{padding:28px 24px 70px}h1,h2,h3{color:var(--ink)}h1{font-size:1.35rem}h2{margin-top:38px}.card{border:1px solid var(--line);background:var(--card);border-radius:12px;padding:18px;margin:14px 0}.meta,.src{color:var(--sub);font-size:.88rem}.src a,a{color:var(--accent)}.prose{white-space:pre-wrap}.tag{display:inline-block;border:1px solid var(--line);border-radius:20px;padding:2px 9px;margin:2px 5px 2px 0}@media(max-width:480px){main,header,nav{padding-left:16px;padding-right:16px}}</style>"""
NAV='<nav><a href="../overview/">오늘</a><a href="../daily_discovery/">수집정보</a><a href="../emerging_issues/">이슈</a><a href="../intelligence_index/">인텔리전스</a><a href="../reports/">보고서</a></nav>'

def shell(title, body, depth=1):
    nav=NAV if depth==1 else NAV.replace('href="../','href="../../')
    return f"<!doctype html><html lang='ko'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{html.escape(title)}</title>{CSS}</head><body><header><h1>METAXIS · {html.escape(title)}</h1></header>{nav}<main>{body}</main></body></html>"

def clean_title(s):
    s=html.unescape(html.unescape(str(s or '')))
    s=re.sub(r'^\s*\[[^\]]{1,28}\]\s*','',s)
    s=re.sub(r'\s*\[[^\]]{1,28}\]\s*$','',s)
    return re.sub(r'\s+',' ',s).strip()

def load_items():
    out=[]
    for p in sorted(DATA.glob('20??-??-??.json')):
        try:
            d=json.loads(p.read_text('utf-8')); date=d.get('date') or p.stem
            for x in d.get('items',[]):
                y=dict(x); y['_date']=date; y['title_clean']=clean_title(x.get('title'))
                y['_text']=' '.join(str(v or '') for v in [y['title_clean'],x.get('summary'),x.get('detail'),json.dumps(x.get('mx',{}),ensure_ascii=False)]).lower()
                out.append(y)
        except Exception: pass
    # URL/id dedupe, newest wins
    seen=set(); ded=[]
    for x in reversed(out):
        k=x.get('link') or x.get('id') or (x['_date'],x['title_clean'])
        if k in seen: continue
        seen.add(k); ded.append(x)
    return list(reversed(ded))

TOPICS={
 'AI × 에너지':['전력','에너지','데이터센터','원전','원자력','전력망','electricity','energy','data center','nuclear','grid'],
 'AI × 법률·저작권':['저작권','판례','법률','법원','소송','copyright','legal','court','lawsuit','知识产权','版权'],
 'AI × 노동·일자리':['일자리','고용','노동','채용','해고','workforce','employment','jobs','labor'],
 'AI × 정책·규제':['규제','정책','법안','정부','ai act','regulation','policy','governance'],
 'AI × 산업·인프라':['엔비디아','반도체','gpu','hpe','인프라','투자','데이터센터','nvidia','semiconductor','infrastructure'],
 'AI × 문화·사회':['문화','예술','교육','미디어','콘텐츠','사회','art','culture','education','media']}

def topic_items(items,name,days=60,limit=60):
    keys=TOPICS[name]; latest=max((x['_date'] for x in items),default='1970-01-01'); cutoff=(dt.date.fromisoformat(latest)-dt.timedelta(days=days)).isoformat()
    scored=[]
    for x in items:
        if x['_date']<cutoff: continue
        score=sum(1 for k in keys if k.lower() in x['_text'])
        if score: scored.append((score,x))
    scored.sort(key=lambda z:(z[0],z[1]['_date']),reverse=True)
    return [x for _,x in scored[:limit]]

def source_packet(rows,limit=35):
    arr=[]
    for i,x in enumerate(rows[:limit],1):
        mx=x.get('mx') or {}
        arr.append({'n':i,'date':x['_date'],'title':x['title_clean'],'source':x.get('source',''),'summary':mx.get('b') or x.get('summary',''),'meaning':mx.get('p',''),'url':x.get('link','')})
    return arr

def gemini(prompt):
    key=os.getenv('GEMINI_KEY')
    if not key:return None
    url=f'https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={key}'
    body=json.dumps({'contents':[{'parts':[{'text':prompt}]}],'generationConfig':{'temperature':0.25,'maxOutputTokens':5000}}).encode()
    try:
        req=urllib.request.Request(url,data=body,headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=90) as r: obj=json.loads(r.read())
        return obj['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception as e:
        print('LLM_FAIL',type(e).__name__,e); return None

def intelligence_text(name,rows):
    pkt=source_packet(rows)
    if not pkt:return None
    prompt=f'''당신은 METAXIS 인텔리전스 분석가다. 아래 실제 수집자료만 근거로 {name}의 현재 인텔리전스를 한국어로 작성하라. 기사 요약이 아니라 여러 자료를 연결한 판단이어야 한다. 사실과 해석을 구분하고 근거가 부족한 예측은 단정하지 않는다. 반드시 다음 소제목을 그대로 사용한다: 현재 판단 / 무엇이 변하고 있는가 / 구조적 의미 / 핵심 동인 / 반대 신호와 불확실성 / 향후 시나리오 / 한국에 대한 시사점 / 정책적 함의 / 계속 관측할 신호. 각 판단 뒤에 근거 자료 번호를 [1][3]처럼 붙인다. 자료에 없는 사실·수치·출처를 만들지 마라.\n자료:\n{json.dumps(pkt,ensure_ascii=False)}'''
    text=gemini(prompt)
    if text:return text
    # honest fallback: no fake synthesis
    latest=pkt[:8]
    return '현재 판단\nLLM 분석을 사용할 수 없어 현재는 근거자료 목록만 제공합니다. 분석을 임의 생성하지 않습니다.\n\n계속 관측할 신호\n'+ '\n'.join(f"- {x['date']} {x['title']}" for x in latest)

def period_bounds(latest,kind):
    d=dt.date.fromisoformat(latest)
    if kind=='daily': return d,d
    if kind=='weekly': return d-dt.timedelta(days=d.weekday()), d
    return d.replace(day=1),d

def report_title(kind,end):
    d=dt.date.fromisoformat(end); m=d.month
    if kind=='daily': return f'AI 이슈브리프_{m}월 {d.day}일'
    if kind=='weekly': return f'AI 이슈브리프_{m}월 {(d.day-1)//7+1}주차'
    return f'AI 이슈브리프_{m}월'

def report_text(kind,rows,title):
    pkt=source_packet(rows,50)
    if not pkt:return '해당 기간에 수집된 자료가 없습니다.'
    depth={'daily':'오늘의 핵심 사건을 선별하고 각 사건의 의미와 다음 관측점을 간결하게','weekly':'한 주의 사건을 주제별로 묶어 흐름, 변화, 상호연결, 다음 주 관측점을','monthly':'한 달의 자료를 과거 축적 맥락과 연결해 구조적 변화, 산업·사회 영향, 미래 시나리오, 한국 정책 시사점을 심층적으로'}[kind]
    prompt=f'''METAXIS의 {title}을 작성하라. {depth} 분석한다. 다양한 분야를 포괄하되 중요하지 않은 자료를 억지로 넣지 않는다. 단순 기사 나열 금지. 실제 자료만 사용하고 주장마다 [번호]로 근거를 표시한다. 불확실성과 반대 가능성을 명시한다. 월간은 지적 이슈브리프/정책보고서 수준의 긴 서사형 분석으로 작성하고, 일간은 비즈니스 인사이트 브리프처럼 빠르게 읽히게, 주간은 이슈브리프형으로 작성한다. 자료에 없는 사실을 만들지 마라.\n자료:\n{json.dumps(pkt,ensure_ascii=False)}'''
    return gemini(prompt) or ('LLM 분석을 사용할 수 없어 임의의 보고서를 생성하지 않았습니다.\n\n근거자료\n'+'\n'.join(f"[{x['n']}] {x['title']} — {x['source']}" for x in pkt))

def refs_html(rows,limit=50):
    lis=[]
    for i,x in enumerate(rows[:limit],1):
        u=html.escape(x.get('link',''),quote=True); t=html.escape(x['title_clean']); s=html.escape(x.get('source',''))
        lis.append(f"<li>[{i}] <a href='{u}' target='_blank' rel='noopener noreferrer'>{t}</a> — {s} · {x['_date']}</li>")
    return '<ol>'+''.join(lis)+'</ol>'

def render_text(text):
    # safe text, lightweight headings
    esc=html.escape(text or '')
    esc=re.sub(r'(?m)^#{0,3}\s*(현재 판단|무엇이 변하고 있는가|구조적 의미|핵심 동인|반대 신호와 불확실성|향후 시나리오|한국에 대한 시사점|정책적 함의|계속 관측할 신호)\s*$',r'</div><h2>\1</h2><div class="prose">',esc)
    return '<div class="prose">'+esc+'</div>'

def build_intelligence(items):
    cards=[]
    for name in TOPICS:
        rows=topic_items(items,name)
        if not rows: continue
        slug=re.sub(r'[^a-z0-9]+','-',name.lower().replace('ai × ','ai-')).strip('-') or str(abs(hash(name)))
        text=intelligence_text(name,rows)
        d=OP/'intelligence'/slug; d.mkdir(parents=True,exist_ok=True)
        body=f'<p class="meta">최근 관측 {rows[0]["_date"]} · 근거자료 {len(rows)}건</p>{render_text(text)}<h2>근거자료</h2>{refs_html(rows)}'
        (d/'index.html').write_text(shell(name,body,2),'utf-8')
        cards.append(f'<div class="card"><h2><a href="../intelligence/{slug}/">{html.escape(name)}</a></h2><p>최근 축적자료 {len(rows)}건을 바탕으로 현재 판단·변화·전망·정책 시사점을 지속 갱신합니다.</p><p class="meta">최근 관측 {rows[0]["_date"]}</p></div>')
    idx='<p>인텔리전스는 건수표가 아니라 축적된 정보를 연결해 현재 상황과 변화 방향을 판단하는 살아 있는 분석입니다.</p>'+''.join(cards)
    d=OP/'intelligence_index'; d.mkdir(parents=True,exist_ok=True); (d/'index.html').write_text(shell('인텔리전스',idx),'utf-8')

def build_reports(items):
    latest=max((x['_date'] for x in items),default=dt.date.today().isoformat()); cards=[]
    OUT.mkdir(parents=True,exist_ok=True)
    for kind in ('daily','weekly','monthly'):
        start,end=period_bounds(latest,kind); rows=[x for x in items if start.isoformat()<=x['_date']<=end.isoformat()]
        title=report_title(kind,end.isoformat()); rid=f'{kind}_{end.isoformat()}' if kind!='monthly' else f'monthly_{end:%Y-%m}'
        text=report_text(kind,rows,title)
        d=OP/'brief'/rid; d.mkdir(parents=True,exist_ok=True)
        body=f'<p class="meta">기간 {start.isoformat()} ~ {end.isoformat()} · 사용 가능 수집자료 {len(rows)}건</p>{render_text(text)}<h2>출처 및 근거자료</h2>{refs_html(rows)}'
        (d/'index.html').write_text(shell(title,body,2),'utf-8')
        (OUT/f'{rid}.json').write_text(json.dumps({'id':rid,'title':title,'kind':kind,'period':[start.isoformat(),end.isoformat()],'generated_at':dt.datetime.now(KST).isoformat(),'source_count':len(rows),'text':text},ensure_ascii=False,indent=2),'utf-8')
        label={'daily':'일간','weekly':'주간','monthly':'월간'}[kind]
        cards.append(f'<div class="card"><span class="tag">{label}</span><h2><a href="../brief/{rid}/">{html.escape(title)}</a></h2><p class="meta">{start.isoformat()} ~ {end.isoformat()} · 근거자료 {len(rows)}건</p></div>')
    d=OP/'reports'; d.mkdir(parents=True,exist_ok=True); (d/'index.html').write_text(shell('보고서','<p>일간·주간·월간 AI 이슈브리프입니다. 각 보고서는 실제 수집자료의 원문 출처를 함께 제공합니다.</p>'+''.join(cards)),'utf-8')

def repair_html():
    for p in OP.rglob('*.html'):
        try:s=p.read_text('utf-8')
        except Exception:continue
        # legacy 404 route -> actually built Operator report route
        s=re.sub(r'href=["\'](?:\.\./)*intelligence/(report_intel_[^/"\']+)/?["\']',lambda m:f'href="../../report/{m.group(1)}/"',s)
        # decode double-escaped numeric/named entities only in visible generated HTML
        for _ in range(2): s=re.sub(r'&amp;(#(?:x[0-9A-Fa-f]+|\d+)|[A-Za-z]+);',r'&\1;',s)
        p.write_text(s,'utf-8')

def main():
    items=load_items(); print('corpus',len(items))
    if not items: raise SystemExit('NO_CORPUS')
    build_intelligence(items); build_reports(items); repair_html()
    print('FINALIZED',max(x['_date'] for x in items))
if __name__=='__main__': main()
