#!/usr/bin/env python3
"""Replace empty no-LLM brief/intelligence placeholders with conservative synthesis from mx.b/mx.p/tags."""
import html,json,re
from collections import defaultdict
from pathlib import Path
R=Path(__file__).resolve().parents[2]; D=R/'data'; O=R/'intel_private'/'operator'
def items():
 a=[]
 for p in sorted(D.glob('20??-??-??.json')):
  try:
   d=json.loads(p.read_text('utf-8'))
   for x in d.get('items',[]): x=dict(x);x['_date']=d.get('date',p.stem);a.append(x)
  except:pass
 return a
def synth(rows,maxg=7):
 g=defaultdict(list)
 for x in rows:
  m=x.get('mx') or {}; ts=m.get('t') or []; k=(ts[0] if ts else x.get('field') or x.get('category') or 'AI 일반');g[str(k)].append(x)
 gs=sorted(g.items(),key=lambda z:len(z[1]),reverse=True)[:maxg]; out=['수집된 자료를 사건 단위가 아니라 반복되는 변화 신호 중심으로 재구성했습니다.']
 for k,xs in gs:
  x=xs[0];m=x.get('mx') or {}; fact=m.get('b') or x.get('summary') or x.get('title','');meaning=m.get('p') or '현재 자료만으로 장기적 방향을 단정하기보다 후속 정책·기업 행동·독립 출처의 반복 여부를 확인할 필요가 있습니다.'
  out += [f'\n{k}',f'무슨 일이 있었나: {fact}',f'왜 중요한가: {meaning}',f'관측: 관련 자료 {len(xs)}건. 후속 제도 변화·투자·채택·반대 사례가 이어지는지 추적합니다.']
 out += ['\n불확실성','이 분석은 현재 METAXIS 수집 범위에 한정되며 미수집 출처와 반대 사례가 존재할 수 있습니다.']
 return '\n'.join(out)
def main():
 allx=items(); latest=max((x['_date'] for x in allx),default='')
 for p in (O/'brief').glob('*/index.html'):
  s=p.read_text('utf-8')
  if 'LLM 분석을 사용할 수 없어' not in s:continue
  m=re.search(r'기간 (\d{4}-\d{2}-\d{2}) ~ (\d{4}-\d{2}-\d{2})',s); rows=allx
  if m: rows=[x for x in allx if m.group(1)<=x['_date']<=m.group(2)]
  text=html.escape(synth(rows)); start=s.find('<div class="prose">'); end=s.find('</div>',start)
  if start>=0 and end>=0:s=s[:start]+'<div class="prose">'+text+'</div>'+s[end+6:]
  p.write_text(s,'utf-8')
 for p in (O/'intelligence').glob('*/index.html'):
  s=p.read_text('utf-8')
  if 'LLM 분석을 사용할 수 없어' not in s:continue
  text=html.escape(synth(allx,6)); start=s.find('<div class="prose">'); end=s.find('</div>',start)
  if start>=0 and end>=0:s=s[:start]+'<div class="prose">'+text+'</div>'+s[end+6:]
  p.write_text(s,'utf-8')
 print('FALLBACK_ENHANCED',latest)
if __name__=='__main__':main()
