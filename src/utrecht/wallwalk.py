import urllib.request, json, time
def route(pts,costing='pedestrian'):
    body={'locations':[{'lat':p[0],'lon':p[1],'type':'through' if 0<i<len(pts)-1 else 'break'}
                       for i,p in enumerate(pts)],
          'costing':costing,'directions_options':{'units':'kilometers'}}
    req=urllib.request.Request('https://valhalla1.openstreetmap.de/route',data=json.dumps(body).encode(),
        headers={'Content-Type':'application/json','User-Agent':'travel-itinerary/1.0'})
    s=json.load(urllib.request.urlopen(req,timeout=60))['trip']['summary']; time.sleep(1.2)
    return round(s['length'],2), round(s['time']/60)

manen=(52.081652,5.124632); sonn=(52.085333,5.129051); lepel=(52.089171,5.128493)
lucas=(52.093946,5.12673); wolven=(52.096479,5.125309); beppe=(52.089419,5.121352)
twijn=(52.082122,5.12382); cs=(52.089393,5.109821); dom=(52.090934,5.121046)

print('S->N bolwerken arc (Manenburg..Wolvenplein):', route([manen,sonn,lepel,lucas,wolven]))
print('Full Singel loop (clockwise via 5 points back to start):', route([manen,sonn,lepel,lucas,wolven,cs,manen]))
print('Wolvenplein -> Pizza Beppe:', route([wolven,beppe]))
print('Twijnstraat -> Manenburg:', route([twijn,manen]))
print('Dom -> Manenburg:', route([dom,manen]))
