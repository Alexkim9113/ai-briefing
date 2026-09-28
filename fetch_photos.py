import json, urllib.request, urllib.parse, os, time
Q = {"medical":"medical technology","law":"courthouse","chip":"semiconductor chip","robot":"robot","energy":"solar panels","art":"art studio","edu":"classroom","security":"cyber security","invest":"stock market","llm":"laptop code","launch":"smartphone","research":"laboratory","video":"stage lights","ai":"abstract technology","city":"city night"}
UA={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
os.makedirs("cand", exist_ok=True); meta={}
for k,q in Q.items():
    try:
        u="https://api.openverse.org/v1/images/?page_size=20&license=cc0,pdm&aspect_ratio=wide&size=large&q="+urllib.parse.quote(q)
        d=json.load(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=30))
    except Exception as e:
        meta[k]=str(e); continue
    n=0
    for r in d["results"]:
        fn=f"cand/{k}_{n}.jpg"
        try:
            img=urllib.request.urlopen(urllib.request.Request(r["thumbnail"],headers=UA),timeout=30).read()
            open(fn,"wb").write(img)
        except Exception as e:
            continue
        meta[fn]={k2:r.get(k2) for k2 in ("id","url","foreign_landing_url","license","creator","source","title","width","height")}
        n+=1
        if n>=8: break
    time.sleep(1)
json.dump(meta,open("cand/meta.json","w"),indent=1,ensure_ascii=False)
