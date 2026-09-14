"""
Walks that need a waypoint to follow the path actually taken.

Valhalla's own shortest path for Prinsenhof -> Lakila swings north and doubles
back (1366 m against a 537 m straight line). Pinning it to the canal gives the
route as walked, 715 m.
"""
import json, urllib.parse, urllib.request
from walkroute import decode_polyline6
from routes import STOPS

VIAS = {
    ("prinsenhof", "lakila"): [(52.01220, 4.35560), (52.01300, 4.35930)],
}

def route(pts):
    locs = [{"lat": p[0], "lon": p[1], "type": "break" if i in (0, len(pts)-1) else "through"}
            for i, p in enumerate(pts)]
    body = {"locations": locs, "costing": "pedestrian",
            "directions_options": {"units": "kilometers"}}
    req = urllib.request.Request(
        "https://valhalla1.openstreetmap.de/route?json=" + urllib.parse.quote(json.dumps(body)),
        headers={"User-Agent": "steven-personal-itinerary-map/1.0"})
    d = json.load(urllib.request.urlopen(req, timeout=45))
    out = []
    for lg in d["trip"]["legs"]:
        out.extend(decode_polyline6(lg["shape"]))
    return out, d["trip"]["summary"]["length"] * 1000

walks = json.load(open("walks.json"))
for (a, b), vias in VIAS.items():
    pts, m = route([STOPS[a]] + vias + [STOPS[b]])
    walks[f"{a}|{b}"] = [[round(p[0], 6), round(p[1], 6)] for p in pts]
    print(f"{a} -> {b}: {m:.0f} m via the canal ({len(pts)} pts)")

# Keep the Scheveningen pair, which hotel_pass.py owns
walks.update(json.load(open("kurhaus_walks.json")))
json.dump(walks, open("walks.json", "w"))
print("walks.json:", len(walks), "legs")
