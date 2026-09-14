import urllib.request, json, time
P={
 'dom':(52.090934,5.121046),'garden':(52.087981,5.169072),'water':(52.106621,5.07469),
 'beppe':(52.089419,5.121352),'cs':(52.089393,5.109821),'padua':(52.0847,5.169337),
 'twijn':(52.082122,5.12382),
}
def route(a,b,costing):
    body={'locations':[{'lat':P[a][0],'lon':P[a][1]},{'lat':P[b][0],'lon':P[b][1]}],
          'costing':costing,'directions_options':{'units':'kilometers'}}
    req=urllib.request.Request('https://valhalla1.openstreetmap.de/route',
        data=json.dumps(body).encode(),headers={'Content-Type':'application/json','User-Agent':'travel-itinerary/1.0'})
    s=json.load(urllib.request.urlopen(req,timeout=60))['trip']['summary']
    time.sleep(1.2)
    return round(s['length'],2), round(s['time']/60)
for a,b,c in [('dom','garden','bicycle'),('garden','water','bicycle'),('dom','water','bicycle'),
              ('water','beppe','bicycle'),('cs','water','bicycle'),('padua','garden','pedestrian'),
              ('cs','dom','pedestrian'),('beppe','twijn','pedestrian')]:
    km,mn=route(a,b,c)
    print(f'{a:7s} -> {b:7s} {c:10s} {km:6.2f} km  {mn:3d} min')
