import json, time, urllib.parse, urllib.request

QUERIES = [
    "Meijersplein, Rotterdam",
    "Meijersplein metrostation",
    "Hanno, Delft",
    "Lakila, Delft",
    "Kleiweg, Rotterdam",
]
for q in QUERIES:
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": q, "format": "json", "limit": 3}
    )
    req = urllib.request.Request(url, headers={"User-Agent": "steven-travel-map/1.0 (personal itinerary)"})
    try:
        data = json.load(urllib.request.urlopen(req, timeout=30))
    except Exception as e:
        print(f"{q}: ERROR {e}"); time.sleep(1.2); continue
    if not data:
        print(f"{q}: NOT FOUND")
    for d in data:
        print(f"{q:28s} {float(d['lat']):.5f}, {float(d['lon']):.5f}  | {d['display_name'][:80]}")
    print()
    time.sleep(1.2)
