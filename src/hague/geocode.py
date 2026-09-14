import json, sys, time, urllib.parse, urllib.request

QUERIES = [
    "Meijersplein metro station, Rotterdam",
    "Den Haag Centraal station",
    "Bierkade, Den Haag",
    "Kerkplein, Den Haag",
    "Haags Openbaar Vervoer Museum, Den Haag",
    "Kurhaus, Scheveningen",
    "Malieveld, Den Haag",
    "Grote Markt, Den Haag",
    "Museum Prinsenhof Delft",
    "Delft station",
    "Rotterdam Centraal",
    "Wilgenlei, Rotterdam",
]

for q in QUERIES:
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": q, "format": "json", "limit": 1}
    )
    req = urllib.request.Request(url, headers={"User-Agent": "steven-travel-map/1.0 (personal itinerary)"})
    try:
        data = json.load(urllib.request.urlopen(req, timeout=30))
    except Exception as e:
        print(f"{q:45s} ERROR {e}")
        time.sleep(1.2)
        continue
    if not data:
        print(f"{q:45s} NOT FOUND")
    else:
        d = data[0]
        name = d["display_name"][:65]
        print(f"{q:45s} {float(d['lat']):.5f}, {float(d['lon']):.5f}  | {name}")
    time.sleep(1.2)
