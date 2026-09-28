import json, urllib.request, urllib.parse, os, shutil, time
UA={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
Q={"car":"self driving car","drone":"drone flying","hand":"handshake business","stage":"conference presentation","gov":"capitol building","doctor":"doctor hospital","call":"call center headset","bank":"bank money","factory":"factory manufacturing","farm":"farm field tractor","sat":"satellite space","coins":"coins money","news":"newspaper","camera":"film camera","mic":"microphone podcast","meet":"office meeting","brain":"brain","chess":"chess","soldier":"military soldier","ev":"electric car charging","power":"power lines electricity","wind":"wind turbine","pills":"pills medicine","xray":"x-ray","phoneapp":"mobile app","seoul":"seoul city","ship":"cargo ship port","plane":"airplane","shop":"shopping retail","music":"music studio","write":"writing notebook","kids":"children learning","code":"programming code screen","vr":"virtual reality headset"}
shutil.rmtree("cand", ignore_errors=True); os.makedirs("cand"); meta={}
for k,q in Q.items():
    try:
        u="https://api.openverse.org/v1/images/?page_size=20&license=cc0,pdm&aspect_ratio=wide&size=large&source=stocksnap,rawpixel&q="+urllib.parse.quote(q)
        d=json.load(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=30))
    except Exception as e:
        print(k,e); continue
    n=0
    for r in d["results"]:
        try: open(f"cand/{k}_{n}.jpg","wb").write(urllib.request.urlopen(urllib.request.Request(r["thumbnail"],headers=UA),timeout=30).read())
        except Exception: continue
        meta[f"{k}_{n}"]={x:r.get(x) for x in ("id","url","foreign_landing_url","license","creator","source","title")}
        n+=1
        if n>=6: break
    time.sleep(1)
json.dump(meta,open("cand/meta.json","w"),indent=1)
