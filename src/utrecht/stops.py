import urllib.request, urllib.parse, json, math, time
q='''[out:json][timeout:60];
(
 node["public_transport"="stop_position"](around:1200,52.087981,5.169072);
 node["highway"="bus_stop"](around:1200,52.087981,5.169072);
 node["railway"="tram_stop"](around:1200,52.087981,5.169072);
);
out body;'''
for host in ['https://overpass-api.de/api/interpreter','https://overpass.kumi.systems/api/interpreter']:
    try:
        r=urllib.request.urlopen(urllib.request.Request(host,data=urllib.parse.urlencode({'data':q}).encode(),
            headers={'User-Agent':'travel-itinerary/1.0'}),timeout=90)
        d=json.load(r); break
    except Exception as e:
        print('fail',host,e); time.sleep(3)
G=(52.087981,5.169072)
def hav(a,b):
    R=6371000; p=math.radians
    dla=p(b[0]-a[0]); dlo=p(b[1]-a[1])
    x=math.sin(dla/2)**2+math.cos(p(a[0]))*math.cos(p(b[0]))*math.sin(dlo/2)**2
    return 2*R*math.asin(math.sqrt(x))
seen={}
for el in d['elements']:
    n=el.get('tags',{}).get('name')
    if not n: continue
    dm=hav(G,(el['lat'],el['lon']))
    if n not in seen or dm<seen[n][0]: seen[n]=(dm,el['lat'],el['lon'],el.get('tags',{}).get('railway') or el.get('tags',{}).get('highway',''))
for n,(dm,la,lo,kind) in sorted(seen.items(), key=lambda x:x[1][0])[:10]:
    print(f'{dm:7.0f} m  {n:35s} {kind:12s} {la:.5f},{lo:.5f}')
