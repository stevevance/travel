"""
The Scheveningen out-and-back, shaped to match the route as actually walked.

Outbound: leave the Kurhaus tram stop, dogleg southwest along Gevers Deynootweg
onto Gevers Deynootplein, then northwest across the square and IN through the
Kurhaus, out the seaward side onto the boulevard, and southwest to Summertime.
Valhalla will not route through a building, so the hotel passage is drawn as a
straight segment between the landward and seaward doors -- the rest is routed.
"""
import json, math, urllib.parse, urllib.request
from walkroute import decode_polyline6

ENDPOINT     = "https://valhalla1.openstreetmap.de/route"
TRAM_SOUTH   = (52.113050, 4.283610)   # platform toward town
TRAM_NORTH   = (52.113490, 4.283730)   # platform toward Scheveningen
SUMMERTIME   = (52.113440, 4.280050)
PLEIN        = (52.112400, 4.282800)   # south end of Gevers Deynootplein
STAIRS_BOT   = (52.114502, 4.283216)
STAIRS_TOP   = (52.114719, 4.283199)

poly = [(p["lat"], p["lon"])
        for p in json.load(open("hotel_poly.json"))["elements"][0]["geometry"]]

def dist(a, b):
    dy = (a[0] - b[0]) * 111320.0
    dx = (a[1] - b[1]) * 111320.0 * math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)

def route(pts):
    locs = [{"lat": p[0], "lon": p[1],
             "type": "break" if i in (0, len(pts) - 1) else "through"}
            for i, p in enumerate(pts)]
    body = {"locations": locs, "costing": "pedestrian",
            "costing_options": {"pedestrian": {"step_penalty": 0}},
            "directions_options": {"units": "kilometers"}}
    req = urllib.request.Request(
        ENDPOINT + "?json=" + urllib.parse.quote(json.dumps(body)),
        headers={"User-Agent": "steven-personal-itinerary-map/1.0"})
    d = json.load(urllib.request.urlopen(req, timeout=45))
    out = []
    for lg in d["trip"]["legs"]:
        out.extend(decode_polyline6(lg["shape"]))
    return out, d["trip"]["summary"]["length"] * 1000

# Doors: the footprint corners facing the square and facing the sea
land_door = min(poly, key=lambda p: dist(p, PLEIN))
sea_door  = min(poly, key=lambda p: dist(p, SUMMERTIME))
print(f"landward door {land_door[0]:.5f},{land_door[1]:.5f}")
print(f"seaward  door {sea_door[0]:.5f},{sea_door[1]:.5f}")
print(f"hotel passage {dist(land_door, sea_door):.0f} m")

approach, m1 = route([TRAM_SOUTH, PLEIN, land_door])
beach,    m2 = route([sea_door, SUMMERTIME])
# Route the passage through the footprint centroid. Door-to-door alone traced
# the south facade, because both nearest corners sit on that side and the
# building is elongated -- which reads as walking AROUND the Kurhaus, not through.
cx = sum(p[0] for p in poly) / len(poly)
cy = sum(p[1] for p in poly) / len(poly)
centroid = (cx, cy)
def seg(a, b, n):
    return [(a[0] + (b[0] - a[0]) * t / n, a[1] + (b[1] - a[1]) * t / n) for t in range(n)]
passage = seg(land_door, centroid, 6) + seg(centroid, sea_door, 6) + [sea_door]
print(f"passage via centroid {centroid[0]:.5f},{centroid[1]:.5f}")
outbound = approach + passage + beach
m_pass = dist(land_door, centroid) + dist(centroid, sea_door)
m_out = m1 + m_pass + m2
print(f"outbound: {m1:.0f} m to the door + {m_pass:.0f} m through "
      f"+ {m2:.0f} m to Summertime = {m_out:.0f} m")

# ONE waypoint, at the middle of the stairway. Pinning both ends made Valhalla
# walk up, turn around and come back down, retracing 212 m of its own path --
# which drew as a heavy double-dashed stub. The midpoint threads the steps once.
STAIRS_MID = ((STAIRS_BOT[0] + STAIRS_TOP[0]) / 2, (STAIRS_BOT[1] + STAIRS_TOP[1]) / 2)
back, m_back = route([SUMMERTIME, STAIRS_MID, TRAM_NORTH])
print(f"return via the covered stairs: {m_back:.0f} m")

w = {"kurhaus|summertime": [[round(p[0], 6), round(p[1], 6)] for p in outbound],
     "summertime|kurhaus": [[round(p[0], 6), round(p[1], 6)] for p in back]}
json.dump(w, open("kurhaus_walks.json", "w"))
allw = json.load(open("walks.json")); allw.update(w)
json.dump(allw, open("walks.json", "w"))

def inside(pt, poly):
    x, y = pt[1], pt[0]; c = False; j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i][1], poly[i][0]; xj, yj = poly[j][1], poly[j][0]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            c = not c
        j = i
    return c
print("outbound points inside the hotel footprint:",
      sum(1 for p in outbound if inside(p, poly)), "of", len(outbound))
