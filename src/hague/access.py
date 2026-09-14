"""Route each stop-to-platform access hop on the pedestrian network."""
import json, time, urllib.parse, urllib.request
from mapkit import access_connectors
from walkroute import decode_polyline6

ENDPOINT = "https://valhalla1.openstreetmap.de/route"

def route(p1, p2):
    body = {"locations": [{"lat": p1[0], "lon": p1[1]}, {"lat": p2[0], "lon": p2[1]}],
            "costing": "pedestrian", "directions_options": {"units": "kilometers"}}
    req = urllib.request.Request(
        ENDPOINT + "?json=" + urllib.parse.quote(json.dumps(body)),
        headers={"User-Agent": "steven-personal-itinerary-map/1.0"})
    d = json.load(urllib.request.urlopen(req, timeout=45))
    pts = []
    for lg in d["trip"]["legs"]:
        pts.extend(decode_polyline6(lg["shape"]))
    return pts, d["trip"]["summary"]["length"] * 1000

out = []
for c in access_connectors():
    a, b = c["pts"]
    try:
        pts, m = route(a, b)
        out.append({"stop": c["stop"], "m": round(m),
                    "pts": [[round(p[0], 6), round(p[1], 6)] for p in pts]})
        print(f"  {c['stop']:16s} straight {c['m']:4d} m -> walked {m:5.0f} m ({len(pts)} pts)")
    except Exception as e:
        print(f"  {c['stop']}: FAILED {e}; keeping straight hop")
        out.append({"stop": c["stop"], "m": c["m"],
                    "pts": [[round(a[0], 6), round(a[1], 6)], [round(b[0], 6), round(b[1], 6)]]})
    time.sleep(0.9)

json.dump(out, open("access.json", "w"))
print(f"saved {len(out)} access walks")
