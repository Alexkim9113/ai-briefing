#!/usr/bin/env python3
import html,json,re
from collections import defaultdict
from pathlib import Path
R=Path(__file__).resolve().parents[2];D=R/'data';O=R/'intel_private'/'operator'
TOPICS=[('energy','AI × 에너지',['전력','에너지','데이터센터','원전','전력망','energy','data center','nuclear']),('law-copyright','AI × 법률·저작권',['저작권','판례','법률','법원','소송','copyright','legal','知识产权','版权']),('labor','AI × 노동·일자리',['일자리','고용','노동','채용','해고','jobs','labor','employment']),('policy','AI × 정책·규제',['규제','정책','법안','정부','regulation','policy','ai act']),('industry','AI × 산업·인프라',['엔비디아','반도체','gpu','hpe','인프라','투자','데이터센터','nvidia']),('culture','AI × 문화·사회',['문화','예술','교육','미디어','콘텐츠','사회','culture','education','media'])]
def items():
 a=[]
 for p in sorted(D.glob('20??-??-??.json')):
  try:
   d=json.loads(p.read_text('utf-8'))
   for x in d.get('items',[]):
    x=dict(x);x['_date']=d.get('date',p.stem);x['_text']=' '.join(str(v or '') for v in [x.get('title'),x.get('summary'),x.get('detail'),json.dumps(x.get('mx',{}),ensure_ascii=False)]).lower();a.append(x)
  except:pass
 return a
def synth(rows,maxg=7):
 g=defaultdict(list)
 for x in rows:
  m=x.get('mx') or {};ts=m.get('t') or [];k=ts[0] if ts else x.get('field') or x.get('category') or 'AI 일반';g[str(k)].append(x)
 out=['현재 판단','수집자료에서 반복되는 변화 신호를 중심으로 현재 상황을 재구성했습니다. 단일 기사보다 복수 사건의 반복 여부를 우선 봅니다.','\n무엇이 변하고 있는가']
 for k,xs in sorted(g.items(),key=lambda z:len(z[1]),reverse=True)[:maxg]:
  x=xs[0];m=x.get('mx') or {};fact=m.get('b') or x.get('summary') or x.get('title','');meaning=m.get('p') or ''
  out += [f'- {k} ({len(xs)}건): {fact}'+(f' 의미: {meaning}' if meaning else '')]
 out += ['\n구조적 의미','반복 신호가 실제 정책 변경·기업 투자·제품 채택·가격·고용 등 현실 행동으로 연결되는지가 구조적 변화 여부를 가르는 핵심입니다.','\n반대 신호와 불확실성','현재 METAXIS 수집 범위 밖의 자료와 반대 방향 사례가 충분히 포착되지 않았을 수 있습니다.','\n향후 시나리오','1. 반복 신호가 복수 기관·지역으로 확산되어 구조적 흐름으로 강화\n2. 특정 사건에 머물러 일시적 관심으로 약화\n3. 규제·비용·기술효율 변화로 방향 전환','\n한국에 대한 시사점','해외 신호가 국내 제도·산업 행동으로 전이되는 시차와 경로를 별도로 추적해야 합니다.','\n정책적 함의','기사 건수보다 법제화, 예산, 투자, 채택 등 실제 행동지표를 중심으로 판단해야 합니다.','\n계속 관측할 신호','정책 발표·법제화·기업 투자·제품 채택·가격/고용 변화·반대 사례를 지속 추적합니다.']
 return '\n'.join(out)
def replace_prose(s,text):
 start=s.find('<div class="prose">');end=s.find('</div>',start)
 return s[:start]+'<div class="prose">'+html.escape(text)+'</div>'+s[end+6:] if start>=0 and end>=0 else s
def main():
 allx=items();latest=max((x['_date'] for x in allx),default='')
 # Brief fallback
 for p in (O/'brief').glob('*/index.html'):
  s=p.read_text('utf-8')
  if 'LLM 분석을 사용할 수 없어' in s:
   m=re.search(r'기간 (\d{4}-\d{2}-\d{2}) ~ (\d{4}-\d{2}-\d{2})',s);rows=allx if not m else [x for x in allx if m.group(1)<=x['_date']<=m.group(2)];p.write_text(replace_prose(s,synth(rows)),'utf-8')
 # Rebuild Intelligence routes with unique stable slugs; fixes previous Korean-slug collision.
 cards=[]
 template=(O/'intelligence'/'ai'/'index.html')
 for slug,name,keys in TOPICS:
  rows=[x for x in allx if any(k.lower() in x['_text'] for k in keys)][-80:]
  d=O/'intelligence'/slug;d.mkdir(parents=True,exist_ok=True)
  if template.exists():s=template.read_text('utf-8');s=re.sub(r'<title>.*?</title>',f'<title>{name}</title>',s,1);s=re.sub(r'<h1>METAXIS · .*?</h1>',f'<h1>METAXIS · {name}</h1>',s,1);s=replace_prose(s,synth(rows));
  else:s=f"<!doctype html><meta charset='utf-8'><h1>{name}</h1><pre>{html.escape(synth(rows))}</pre>"
  (d/'index.html').write_text(s,'utf-8');cards.append(f'<div class="card"><h2><a href="../intelligence/{slug}/">{name}</a></h2><p>현재 판단 · 변화 · 구조적 의미 · 전망 · 정책 시사점 · 관측 신호</p><p class="meta">관련 축적자료 {len(rows)}건</p></div>')
 idx=O/'intelligence_index'/'index.html'
 if idx.exists():
  s=idx.read_text('utf-8');a=s.find('<main>');b=s.rfind('</main>');body='<p>축적 정보를 연결해 현재 상황과 변화 방향을 판단하는 주제별 인텔리전스입니다.</p>'+''.join(cards);s=s[:a+6]+body+s[b:];idx.write_text(s,'utf-8')
 print('FALLBACK_ENHANCED',latest)
if __name__=='__main__':main()
