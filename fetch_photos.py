import json, urllib.request, urllib.parse, os, time
Q = {"robot2":"robot arm","robot3":"humanoid robot","law2":"gavel","law3":"court building","edu2":"library books","edu3":"students studying","lab2":"microscope","lab3":"science laboratory","art3":"concert crowd","art4":"painting brushes","gov":"government building","net":"server room"}
UA={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
os.makedirs("cand", exist_ok=True)
import shutil; shutil.rmtree("cand"); os.makedirs("cand"); meta={}
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
