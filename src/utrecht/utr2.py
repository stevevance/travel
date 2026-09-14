import urllib.request, urllib.parse, json, time
UA={'User-Agent':'chicagocityscape-travel-itinerary/1.0'}
def geo(q):
    u='https://nominatim.openstreetmap.org/search?'+urllib.parse.urlencode({'q':q,'format':'json','limit':1})
    d=json.load(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=30)); time.sleep(1.1)
    return (float(d[0]['lat']),float(d[0]['lon']),d[0]['display_name'][:70]) if d else None
hl=geo("Heidelberglaan tram stop, Utrecht, Netherlands")
print('Heidelberglaan stop', hl)
def route(a,b,costing='pedestrian'):
    body={'locations':[{'lat':a[0],'lon':a[1]},{'lat':b[0],'lon':b[1]}],'costing':costing,
          'directions_options':{'units':'kilometers'}}
    req=urllib.request.Request('https://valhalla1.openstreetmap.de/route',data=json.dumps(body).encode(),
        headers={'Content-Type':'application/json','User-Agent':'travel-itinerary/1.0'})
    s=json.load(urllib.request.urlopen(req,timeout=60))['trip']['summary']; time.sleep(1.2)
    return round(s['length'],2), round(s['time']/60)
garden=(52.087981,5.169072)
if hl: print('Heidelberglaan -> garden entrance:', route((hl[0],hl[1]),garden))
