import urllib.request, urllib.parse, json, time
UA={'User-Agent':'stevevance-travel-maps/1.0 (+https://github.com/stevevance/travel)'}
def geo(q):
    u='https://nominatim.openstreetmap.org/search?'+urllib.parse.urlencode({'q':q,'format':'json','limit':1})
    r=urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=30)
    d=json.load(r)
    time.sleep(1.1)
    if not d: return None
    return (round(float(d[0]['lat']),6), round(float(d[0]['lon']),6), d[0]['display_name'][:80])
for q in ["Budapestlaan 17, Utrecht, Netherlands",
          "Isotopenweg 55, Utrecht, Netherlands",
          "Oudegracht 178, Utrecht, Netherlands",
          "Twijnstraat 54, Utrecht, Netherlands",
          "Utrecht Centraal station, Utrecht, Netherlands",
          "Domplein 9, Utrecht, Netherlands",
          "Padualaan, Utrecht, Netherlands"]:
    print(q, '->', geo(q))
