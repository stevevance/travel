"""One-off lookups for the places the day's notes name. Nominatim, 1 req/s."""
import json, sys, time, urllib.parse, urllib.request
UA = {"User-Agent": "steven-personal-itinerary-map/1.0 (personal travel notes)"}

def find(q, limit=4):
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": q, "format": "json", "limit": limit})
    req = urllib.request.Request(url, headers=UA)
    try:
        d = json.load(urllib.request.urlopen(req, timeout=30))
    except Exception as ex:
        print(f"{q}: ERROR {ex}"); return []
    if not d:
        print(f"{q}: NOT FOUND")
    for r in d:
        print(f"  {float(r['lat']):.6f}, {float(r['lon']):.6f}  "
              f"{r.get('type',''):18s} {r['display_name'][:88]}")
    return d

for q in sys.argv[1:]:
    print(f"\n### {q}")
    find(q)
    time.sleep(1.2)
