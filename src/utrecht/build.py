"""Build the Utrecht day as it actually happened: tram 22, two walks, one ride.

Unlike the Rotterdam and Hague maps, one leg here is not routed at all: the
evening bakfiets ride is the real Strava trace out of
data/utrecht/2026-09-14-cargoroo-ride.gpx. Every leg carries a `source`
property so the page can say which lines are measured and which are drawn by a
router. See data/utrecht/2026-09-14-actual.md for the day as described.
"""
import json, math, os, sys, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

sys.setrecursionlimit(10000)   # rdp recurses once per retained point

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
GPX  = os.path.join(ROOT, "data", "utrecht", "2026-09-14-cargoroo-ride.gpx")

UA = {"User-Agent": "stevevance-travel-maps/1.0 (+https://github.com/stevevance/travel)"}
VALHALLA = "https://valhalla1.openstreetmap.de/route"
OVERPASS = ["https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter"]

# Tram 22 is tagged route=light_rail, not route=tram, and is split by direction:
# 10396258 runs Centraal -> Science Park, 10396257 comes back. The outbound and
# return legs of this day use different relations, so both are fetched.
REL_OUT, REL_BACK = 10396258, 10396257

# ---------------------------------------------------------------- stops -----
# Tram stop positions are the OSM stop nodes, not the itinerary's hand-typed
# guesses: the plan page put Padualaan 140 m off the real platform.
STOPS = {
    "cs":         (52.089286, 5.111774),   # CS Centrumzijde, the Uithoflijn platform
    "padualaan":  (52.084821, 5.167958),
    "gardens":    (52.087981, 5.169072),   # Fort Hoofddijk and the botanic gardens
    "vaartsche":  (52.078802, 5.122570),   # Station Vaartsche Rijn
    "manenburg":  (52.081652, 5.124632),
    "sonnenborgh":(52.085333, 5.129051),
    "lepelenburg":(52.089171, 5.128493),
    # The corner by Villa Orloff (Lucasbolwerk 1), not the middle of the park.
    # The walk came north up the singel and turned left here; routing to the
    # bulwark's centre drew a there-and-back spur that never happened.
    "lucasbolwerk":(52.092829, 5.126486),
    "domtoren":   (52.090653, 5.121309),
    "beppe":      (52.089419, 5.121352),   # walked to it, then walked on
    "panuozzo":   (52.090442, 5.117155),   # O'Panuozzo, Mariastraat 35
    "bike":       (52.095258, 5.115366),   # Cargoroo picked up and returned here
}
ORDER = [
    ("cs",           "Utrecht Centraal"),
    ("padualaan",    "Padualaan"),
    ("gardens",      "Fort Hoofddijk"),
    ("vaartsche",    "Vaartsche Rijn"),
    ("manenburg",    "Manenburg"),
    ("sonnenborgh",  "Sonnenborgh"),
    ("lepelenburg",  "Lepelenburg"),
    ("lucasbolwerk", "Lucasbolwerk"),
    ("domtoren",     "Domtoren"),
    ("beppe",        "Pizza Beppe"),
    ("panuozzo",     "O'Panuozzo"),
    ("bike",         "The Cargoroo"),
]
NUM  = {k: i + 1 for i, (k, _) in enumerate(ORDER)}
NAME = dict(ORDER)
NOTES = {
    "cs":           "Boarded tram 22 at the CS Centrumzijde platform",
    "padualaan":    "Tram 22 stop, out and back",
    "gardens":      "Botanic gardens planted over a Waterlinie fort",
    "vaartsche":    "Got off here on the way back, and walked north",
    "manenburg":    "First bulwark, stone, 1550s",
    "sonnenborgh":  "The complete 1552 bastion, observatory on top",
    "lepelenburg":  "Earthen bolwerk of the 1570s",
    "lucasbolwerk": "Fourth bulwark. Turned left at Villa Orloff, short of Wolvenplein",
    "domtoren":     "Reached from the north, after turning west off the singel",
    "beppe":        "Walked to it, decided against it, kept walking",
    "panuozzo":     "Dinner, Mariastraat 35, about 18:00",
    "bike":         "Picked up the bakfiets on Waterstraat, and returned it here",
}

# Waypoints that hold a leg to the streets actually walked. Lucasbolwerk to the
# Domtoren has none: from the Villa Orloff corner the router already leaves west
# on Nobelstraat, and pinning Janskerkhof on top of that produced a U-turn.
VIA = {
    # Straight north up Budapestlaan to the gardens. Left alone the router loops
    # east by Genevelaan and Hoofddijk for 1.35 km, three times the walk really
    # taken; the red cycleway that looks like the obvious line is signed NL:G11,
    # so pedestrians are not on it and Valhalla is right to refuse it. One
    # waypoint on the footway puts it back on the short way, and the return leg
    # uses the same one.
    ("padualaan", "gardens"):    [(52.087175, 5.168715)],
    ("gardens", "padualaan"):    [(52.087175, 5.168715)],
    # North from dinner up Lange Elisabethstraat and Sint-Jacobsstraat. Without
    # this the router prefers the Oudegracht. Naming only Lange Elisabethstraat
    # is enough - Sint-Jacobsstraat follows on its own, and pinning it too only
    # adds a detour through Lange Viestraat.
    ("panuozzo", "bike"):        [(52.091317, 5.115808)],
}

# Where the reconstructed opening of the ride hands over to the recording.
#
# Sint-Jacobsstraat carries a one-way cycleway on each side; southbound is way
# 362720383, and this is its south end. Routing to the recording's own first fix
# instead sends the whole leg the wrong way: that fix sits ~27 m east of the
# cycleway, close enough to the Lange Viestraat junction that Valhalla snaps to
# it and then reaches it via Jacobskerkhof and the Oudegracht - three streets
# that were never ridden. Aiming at the cycleway gives Waterstraat, left onto
# Sint-Jacobsstraat, done, and the short straight hop from here to the first fix
# closes the join.
SJ_SOUTH = (52.093220, 5.114630)

# (mode, from, to)
LEGS = [
    ("tram", "cs",           "padualaan"),
    ("walk", "padualaan",    "gardens"),
    ("walk", "gardens",      "padualaan"),
    ("tram", "padualaan",    "vaartsche"),
    ("walk", "vaartsche",    "manenburg"),
    ("walk", "manenburg",    "sonnenborgh"),
    ("walk", "sonnenborgh",  "lepelenburg"),
    ("walk", "lepelenburg",  "lucasbolwerk"),
    ("walk", "lucasbolwerk", "domtoren"),
    ("walk", "domtoren",     "beppe"),
    ("walk", "beppe",        "panuozzo"),
    ("walk", "panuozzo",     "bike"),
]
ARRIVE = {"cs": "tram", "padualaan": "tram", "gardens": "walk", "vaartsche": "tram",
          "manenburg": "walk", "sonnenborgh": "walk", "lepelenburg": "walk",
          "lucasbolwerk": "walk", "domtoren": "walk", "beppe": "walk",
          "panuozzo": "walk", "bike": "walk"}   # arrived on foot; the ride starts here

# ------------------------------------------------------------- geometry -----
def dist(a, b):
    dy = (a[0]-b[0])*111320.0
    dx = (a[1]-b[1])*111320.0*math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)

def length_m(pts):
    return sum(dist(pts[i], pts[i+1]) for i in range(len(pts)-1))

def decode6(s):
    coords, lat, lon, i = [], 0, 0, 0
    while i < len(s):
        for who in range(2):
            shift = result = 0
            while True:
                b = ord(s[i]) - 63; i += 1
                result |= (b & 0x1f) << shift; shift += 5
                if b < 0x20: break
            d = ~(result >> 1) if result & 1 else (result >> 1)
            if who == 0: lat += d
            else: lon += d
        coords.append((lat/1e6, lon/1e6))
    return coords

def route(pts, costing):
    locs = [{"lat": p[0], "lon": p[1],
             "type": "break" if i in (0, len(pts)-1) else "through"}
            for i, p in enumerate(pts)]
    body = {"locations": locs, "costing": costing,
            "directions_options": {"units": "kilometers"}}
    req = urllib.request.Request(
        VALHALLA + "?json=" + urllib.parse.quote(json.dumps(body)), headers=UA)
    d = json.load(urllib.request.urlopen(req, timeout=45))
    out = []
    for lg in d["trip"]["legs"]:
        out.extend(decode6(lg["shape"]))
    return out, d["trip"]["summary"]["length"] * 1000

def overpass(query, cache):
    """Fetch once, then reuse. Deleting the cache just costs a re-fetch."""
    path = os.path.join(HERE, cache)
    if os.path.exists(path):
        return json.load(open(path))
    last = None
    for url in OVERPASS:
        try:
            req = urllib.request.Request(
                url, data=urllib.parse.urlencode({"data": query}).encode(),
                headers=UA)
            d = json.load(urllib.request.urlopen(req, timeout=180))
            json.dump(d, open(path, "w"))
            return d
        except Exception as ex:
            last = ex
            print(f"  overpass {url} failed: {ex}")
            time.sleep(4)
    raise SystemExit(f"both Overpass endpoints failed: {last}")

def stitch(rel):
    ways = [m["geometry"] for m in rel["members"]
            if m["type"] == "way" and m.get("role", "") == "" and "geometry" in m]
    line = [(p["lat"], p["lon"]) for p in ways[0]]
    for w in ways[1:]:
        pts = [(p["lat"], p["lon"]) for p in w]
        if dist(line[-1], pts[-1]) < dist(line[-1], pts[0]):
            pts.reverse()
        line.extend(pts)
    return line

def nearest(line, pt):
    best, bi = 1e18, 0
    for i, p in enumerate(line):
        d = dist(p, pt)
        if d < best: best, bi = d, i
    return bi, best

def slice_rail(line, a, b, label):
    i, di = nearest(line, STOPS[a])
    j, dj = nearest(line, STOPS[b])
    seg = line[i:j+1] if i <= j else list(reversed(line[j:i+1]))
    print(f"  {label}: {len(seg)} pts, snaps {di:.0f} m / {dj:.0f} m, "
          f"{length_m(seg)/1000:.2f} km")
    return seg

# ------------------------------------------------------------------ gpx -----
def read_gpx(path):
    # The trace itself is gitignored - it is finer than anything published and
    # this repo is public - so a fresh clone will not have it. Say so plainly
    # rather than dying on a missing file.
    if not os.path.exists(path):
        raise SystemExit(
            f"missing {path}\n"
            "The Strava export is deliberately not in git; see data/utrecht/"
            "2026-09-14-actual.md. Drop the .gpx back in that directory to rebuild.")
    NS = "{http://www.topografix.com/GPX/1/1}"
    root = ET.parse(path).getroot()
    return [(float(p.get("lat")), float(p.get("lon")))
            for p in root.iter(NS + "trkpt")]

def trim_loitering(pts, R=20.0):
    """Drop the standing-around at each end of the recording.

    Strava was started before the bike moved and stopped well after it had, so
    the raw track opens and closes with a minute of sub-metre jitter that draws
    as a blot. Keep from the last fix still within R of the first one, to the
    first fix already within R of the last."""
    i = 0
    for k in range(len(pts)):
        if dist(pts[0], pts[k]) < R: i = k
    j = len(pts) - 1
    for k in range(len(pts) - 1, -1, -1):
        if dist(pts[-1], pts[k]) < R: j = k
    return pts[i:j+1], i, len(pts) - 1 - j

def rdp(pts, eps):
    """Ramer-Douglas-Peucker. A one-second Strava trace is far denser than
    anything the router returns; without this the page carries 2,714 points
    for a single leg."""
    if len(pts) < 3:
        return list(pts)
    a, b = pts[0], pts[-1]
    ab = dist(a, b)
    far, fi = -1.0, 0
    for i in range(1, len(pts) - 1):
        p = pts[i]
        if ab == 0:
            d = dist(p, a)
        else:
            # Perpendicular distance in local metres, good enough at city scale.
            ay = (a[0]-p[0])*111320.0; ax = (a[1]-p[1])*111320.0*math.cos(math.radians(p[0]))
            by = (b[0]-p[0])*111320.0; bx = (b[1]-p[1])*111320.0*math.cos(math.radians(p[0]))
            d = abs(ax*by - ay*bx) / ab
        if d > far: far, fi = d, i
    if far <= eps:
        return [a, b]
    return rdp(pts[:fi+1], eps)[:-1] + rdp(pts[fi:], eps)

# ------------------------------------------------------------ build legs ----
print("tram 22 geometry")
rail_out  = stitch(overpass(f"[out:json][timeout:90];rel({REL_OUT});out geom;",
                            "tram22_out.json")["elements"][0])
rail_back = stitch(overpass(f"[out:json][timeout:90];rel({REL_BACK});out geom;",
                            "tram22_back.json")["elements"][0])
RAIL = {("cs", "padualaan"):        slice_rail(rail_out,  "cs", "padualaan", "out"),
        ("padualaan", "vaartsche"): slice_rail(rail_back, "padualaan", "vaartsche", "back")}

print("\nlegs")
features = []
def add(mode, a, b, pts, km, source, note=""):
    features.append({
        "type": "Feature",
        "properties": {"mode": mode, "from": NAME[a], "to": NAME[b],
                       "from_n": NUM[a], "to_n": NUM[b],
                       "line": {"tram": "Tram 22", "bike": "Bakfiets", "walk": "Walk"}[mode],
                       "km": round(km, 2), "source": source, "note": note},
        "geometry": {"type": "LineString",
                     "coordinates": [[round(p[1], 6), round(p[0], 6)] for p in pts]},
    })
    print(f"  {mode:5s} {NAME[a]:16s} -> {NAME[b]:16s} {km:5.2f} km  "
          f"{len(pts):4d} pts  [{source}]")

for mode, a, b in LEGS:
    if mode == "tram":
        pts = RAIL[(a, b)]
        add(mode, a, b, pts, length_m(pts)/1000, "osm")
    else:
        pts, m = route([STOPS[a]] + VIA.get((a, b), []) + [STOPS[b]],
                       "bicycle" if mode == "bike" else "pedestrian")
        add(mode, a, b, pts, m/1000, "routed")
        time.sleep(0.8)

# The ride: a routed opening, then the recording itself.
raw = read_gpx(GPX)
track, lead, tail = trim_loitering(raw)
# End the drawn line on the marker rather than a few metres off it, so the ride
# closes cleanly at the corner where the bike went back.
track = track + [STOPS["bike"]]
simple = rdp(track, 1.5)
print(f"\ngpx: {len(raw)} points, trimmed {lead} loitering at the start and "
      f"{tail} at the end")
print(f"     {len(track)} -> {len(simple)} after rdp(1.5 m), "
      f"{length_m(raw)/1000:.2f} km raw / {length_m(simple)/1000:.2f} km drawn")

gap, gap_m = route([STOPS["bike"], SJ_SOUTH], "bicycle")
gap = gap + [track[0]]
gap_m += dist(SJ_SOUTH, track[0])
add("bike", "bike", "bike", gap, gap_m/1000, "routed",
    "Before Strava started recording: out Waterstraat, left onto Sint-Jacobsstraat")
add("bike", "bike", "bike", simple, length_m(raw)/1000, "gps",
    "The recorded ride, 19:07 to 19:52")

stops_fc = {"type": "FeatureCollection", "features": [
    {"type": "Feature",
     "properties": {"n": NUM[k], "name": n, "arrive": ARRIVE[k],
                    "key": k, "note": NOTES.get(k, "")},
     "geometry": {"type": "Point",
                  "coordinates": [round(STOPS[k][1], 6), round(STOPS[k][0], 6)]}}
    for k, n in ORDER]}
lines_fc = {"type": "FeatureCollection", "features": features}

tpl = open(os.path.join(HERE, "template.html")).read()
tpl = tpl.replace("__LINES__", json.dumps(lines_fc, separators=(",", ":")))
tpl = tpl.replace("__STOPS__", json.dumps(stops_fc, separators=(",", ":")))
out = os.path.join(ROOT, "utrecht-map.html")
open(out, "w").write(tpl)

tot = {}
for f in features:
    p = f["properties"]; tot[p["mode"]] = tot.get(p["mode"], 0) + p["km"]
print("\ntotals:", ", ".join(f"{k} {v:.2f} km" for k, v in sorted(tot.items())))
print(f"total distance {sum(tot.values()):.2f} km")
print(f"wrote {out}, {len(tpl)} bytes")
