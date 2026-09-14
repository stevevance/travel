import urllib.request, urllib.parse, json, time
UA={'User-Agent':'chicagocityscape-travel-itinerary/1.0'}
def geo(q):
    u='https://nominatim.openstreetmap.org/search?'+urllib.parse.urlencode({'q':q,'format':'json','limit':1})
    d=json.load(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=30)); time.sleep(1.1)
    return (round(float(d[0]['lat']),6),round(float(d[0]['lon']),6),d[0]['display_name'][:60]) if d else None
qs=["Sonnenborgh Zonnenburg 2, Utrecht","Lepelenburg park, Utrecht","Wolvenplein, Utrecht",
    "Lucasbolwerk, Utrecht","Begijnebolwerk, Utrecht","Bijlhouwerstoren, Utrecht",
    "Stadsschouwburg Utrecht, Lucasbolwerk 24","Catharijnesingel, Utrecht","Nieuwegracht, Utrecht",
    "Museum Speelklok, Utrecht","Bibliotheek Neude, Utrecht","Manenburg bastion Utrecht"]
pts={}
for q in qs:
    r=geo(q); print(f'{q:45s} -> {r}')
    if r: pts[q]=r
json.dump({k:[v[0],v[1]] for k,v in pts.items()}, open('walls_pts.json','w'), indent=1)
