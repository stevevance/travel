import json, time, urllib.parse, urllib.request
Q = [
    "Proveniersweg, Rotterdam",
    "Mobrigado, Rotterdam",
    "Erasmusbrug, Rotterdam",
    "Rijnhavenbrug, Rotterdam",
    "Koninginnebrug, Rotterdam",
    "Willemsbrug, Rotterdam",
    "Noorderbrug, Rotterdam",
    "Wilhelminapier, Rotterdam",
    "Soetendaalsekade, Rotterdam",
    "Juliana van Stolberglaan, Rotterdam",
    "Ringdijk, Rotterdam",
    "Wilgenlei, Rotterdam",
]
for q in Q:
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": q, "format": "json", "limit": 2})
    req = urllib.request.Request(url, headers={"User-Agent": "steven-travel-map/1.0 (personal itinerary)"})
    try:
        d = json.load(urllib.request.urlopen(req, timeout=30))
    except Exception as ex:
        print(f"{q:38s} ERROR {ex}"); time.sleep(1.2); continue
    if not d:
        print(f"{q:38s} NOT FOUND")
    for r in d[:2]:
        print(f"{q:38s} {float(r['lat']):.5f},{float(r['lon']):.5f}  {r['display_name'][:60]}")
    time.sleep(1.2)
