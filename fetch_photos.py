import json, urllib.request, urllib.parse, os, time
Q = {"medical":"medical technology","law":"courthouse","chip":"semiconductor chip","robot":"robot","energy":"solar panels","art":"art studio","edu":"classroom","security":"cyber security","invest":"stock market","llm":"laptop code","launch":"smartphone","research":"laboratory","video":"stage lights","ai":"abstract technology","city":"city night"}
UA={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
os.makedirs("cand", exist_ok=True); meta={}
for k,q in Q.items():
    try:
        u="https://unsplash.com/napi/search/photos?per_page=20&query="+urllib.parse.quote(q)
        d=json.load(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=20))
    except Exception as e:
        meta[k]=str(e); continue
    n=0
    for r in d["results"]:
        if r.get("premium") or r.get("plus"): continue
        url=r["urls"]["raw"]+"&w=480&h=300&fit=crop&q=60&fm=jpg"
        fn=f"cand/{k}_{n}.jpg"
        try:
            open(fn,"wb").write(urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=20).read())
        except Exception as e:
            continue
        meta[fn]={"id":r["id"],"raw":r["urls"]["raw"],"user":r["user"]["name"],"alt":r.get("alt_description")}
        n+=1
        if n>=8: break
    time.sleep(1)
json.dump(meta,open("cand/meta.json","w"),indent=1,ensure_ascii=False)
