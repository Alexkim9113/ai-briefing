import json, urllib.request, os, shutil
UA={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
shutil.rmtree("cand", ignore_errors=True); os.makedirs("cand")
for p in json.load(open("picks2.json")):
    try: open(f"cand/{p['file']}","wb").write(urllib.request.urlopen(urllib.request.Request(p["url"],headers=UA),timeout=40).read())
    except Exception as e: print(p["key"], e)
