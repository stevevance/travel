"""Build the 8 November 2026 ride: the lakefront to Jackson Park, lunch at
Medici on 57th, and back through Washington Park, Kenwood and the lakefront.

Like the new-things ride it was not recorded, so every leg is Valhalla's
bicycle route through the turns the ride actually made, `source: "routed"`,
and draws dashed. Unlike it, the ride did happen: the vias below are the
streets and park drives that were really taken, not a suggestion.

It starts and ends at home, which is not on the map and not in this file:
the line starts and ends at two public corners a few blocks short of it, and
nothing is routed from or to the door.

    python3 src/chicago-south-side-ride/build.py   # -> chicago-south-side-ride-map.html
"""
import json, math, os, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
VALHALLA = "https://valhalla1.openstreetmap.de/route"
UA = {"User-Agent": "steven-personal-itinerary-map/1.0 (personal travel notes)"}

# A leg's points are routed as one request, except where BREAK splits them:
# each side is routed on its own and the gap is drawn straight. It is for the
# few metres where the ride went somewhere the bicycle costing will not, and
# where pedestrian costing would put the whole leg on the sidewalks instead.
BREAK = None

# ------------------------------------------------------------------ stops ---
# The places the ride went to, in order. The first and last are public corners
# in the South Loop, not home.
STOPS = [
 dict(key="start", lat=41.872285, lng=-87.629528,
      name="South Loop", note="Start of the ride"),
 dict(key="museumcampus", lat=41.868514, lng=-87.615688,
      name="Lakefront Trail at the Museum Campus",
      note="Onto the Lakefront Trail, and south"),
 dict(key="lakefront63", lat=41.782217, lng=-87.575125,
      name="Lakefront Trail at 63rd Street",
      note="The south end of the trail run, by 63rd Street Beach"),
 dict(key="cornell", lat=41.780716, lng=-87.584244,
      name="Jackson Park, Cornell Drive",
      note="Into Jackson Park on its paths"),
 dict(key="bikeparking", lat=41.786254, lng=-87.585024,
      name="Bike parking, Cornell Drive",
      note="North on the park paths to park the bike"),
 dict(key="medici", lat=41.791219, lng=-87.593747,
      name="Medici on 57th",
      note="1327 E 57th St, Hyde Park"),
 dict(key="ellsworth51", lat=41.802094, lng=-87.615638,
      name="Washington Park, Ellsworth Drive at 51st",
      note="Through Washington Park on Payne, Morgan and Ellsworth drives"),
 dict(key="drexel51", lat=41.802705, lng=-87.603793,
      name="Drexel Boulevard at 51st",
      note="East on 51st Street"),
 dict(key="finish", lat=41.872285, lng=-87.628609,
      name="Back in the South Loop",
      note="Drexel, Oakwood, the lakefront, the 11th Street underpass, Wabash and 8th"),
]

# Waypoints that pin the ride to the streets it took. Each one is an OSM
# intersection or a point mid-block on the named street, not a stop. Keep them
# few: over-constraining Valhalla makes it double back (see src/README.md).
VIA = {
    # Midway Plaisance's north roadway, then Blackstone north to 57th, then
    # west on 57th to the door.
    ("bikeparking", "medici"): [(41.787600, -87.588000),    # Midway Plaisance N
                                (41.789645, -87.590212),    # Blackstone & 58th
                                (41.791506, -87.590260)],   # Blackstone & 57th
    # West on 57th to Ellis, south on Ellis to 58th, west on 58th - across
    # the quad, then the street - to Cottage Grove, the path into Washington
    # Park, then north on Payne Drive, west on Morgan, north on Ellsworth.
    # OSM has the step from Ellis onto the quad as bicycle=no with steps, and
    # the path from Cottage to Payne as a footway, so both are BREAKs: the
    # bicycle costing would detour, and pedestrian costing takes the sidewalks.
    ("medici", "ellsworth51"): [(41.791377, -87.601307),    # Ellis & 57th
                                (41.789700, -87.601250),    # Ellis, at 58th
                                BREAK,
                                (41.789570, -87.601400),    # 58th, the quad
                                (41.789520, -87.606120),    # 58th & Cottage
                                BREAK,
                                (41.789260, -87.607540),    # Payne, at the path
                                (41.791620, -87.608140),    # Payne & Morgan
                                (41.793540, -87.612450),    # Morgan Drive
                                (41.797420, -87.614140)],   # Ellsworth Drive
    # The way home: Drexel north to 39th (Oakwood Boulevard), east over the
    # Drive to the Lakefront Trail, north to the 11th Street underpass, through
    # Grant Park to 11th, then Wabash to 8th.
    # Off the trail at 55th and round Promontory Point on the path that hugs
    # its shore (OSM way 1410736764, bicycle=yes), clockwise, then south again.
    ("museumcampus", "lakefront63"): [(41.796666, -87.576745),    # north shore
                                      (41.796173, -87.575604),    # the tip
                                      (41.795406, -87.576452)],   # south shore
    ("drexel51", "finish"): [
            (41.813000, -87.603940),    # Drexel Blvd, northbound side
            (41.822796, -87.606108),    # Drexel & Oakwood (39th)
            (41.824600, -87.602400),    # Oakwood bridge over the Drive
            # The underpass is under Columbus Drive; a pin inside it snaps to
            # the road overhead, so pin the path at each portal instead.
            (41.868550, -87.619280),    # 11th Street underpass, east side
            (41.868750, -87.621130),    # 11th Street underpass, west side
            (41.869278, -87.625889),    # Wabash & 11th
            (41.871848, -87.625950)],   # Wabash & 8th
}
# Legs routed with Valhalla's pedestrian costing: out of the bike parking by
# the footpaths to the Midway, which the bicycle costing would rather do by
# riding up Cornell and U-turning. Still drawn as a bike ride.
LOOSE = {("bikeparking", "medici")}

# ------------------------------------------------------------------ route ---
def decode6(shape):
    coords, i, lat, lon = [], 0, 0, 0
    while i < len(shape):
        for axis in range(2):
            sh, res, b = 0, 0, 0x20
            while b >= 0x20:
                b = ord(shape[i]) - 63; i += 1
                res |= (b & 0x1f) << sh; sh += 5
            d = ~(res >> 1) if res & 1 else res >> 1
            if axis == 0: lat += d
            else:         lon += d
        coords.append((lat / 1e6, lon / 1e6))
    return coords


def valhalla(points, cache, loose=False):
    """Route a bicycle through every point, cached and gitignored."""
    path = os.path.join(HERE, cache)
    if os.path.exists(path):
        d = json.load(open(path))
    else:
        if len(points) > 10:
            raise SystemExit(f"{cache}: {len(points)} locations; Valhalla takes ten.")
        locs = [{"lat": p[0], "lon": p[1],
                 "type": "break" if i in (0, len(points) - 1) else "through"}
                for i, p in enumerate(points)]
        body = {"locations": locs,
                "costing": "pedestrian" if loose else "bicycle",
                "costing_options": {"bicycle": {"bicycle_type": "hybrid",
                                                "use_roads": 0.3,
                                                "use_hills": 0.5}},
                "directions_options": {"units": "kilometers"}}
        req = urllib.request.Request(
            VALHALLA + "?json=" + urllib.parse.quote(json.dumps(body)), headers=UA)
        try:
            d = json.load(urllib.request.urlopen(req, timeout=60))
        except urllib.error.HTTPError as e:
            raise SystemExit(f"{cache}: {e} {e.read().decode()[:300]}")
        json.dump(d, open(path, "w"))
        time.sleep(1.1)
    out = []
    for lg in d["trip"]["legs"]:
        out.extend(decode6(lg["shape"]))
    return out


def dist(a, b):
    R = 6371000.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(h))


def length_km(pts):
    return sum(dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)) / 1000




legs = []
for a, b in zip(STOPS, STOPS[1:]):
    pts = [(a["lat"], a["lng"])] + VIA.get((a["key"], b["key"]), []) \
        + [(b["lat"], b["lng"])]
    loose = (a["key"], b["key"]) in LOOSE
    pieces, cur = [], []
    for p in pts:
        if p is BREAK:
            pieces.append(cur); cur = []
        else:
            cur.append(p)
    pieces.append(cur)
    shape = []
    for k, piece in enumerate(pieces):
        tag = f"_{k}" if len(pieces) > 1 else ""
        shape += valhalla(piece, f"leg_{a['key']}_{b['key']}{tag}.json", loose)
    legs.append((a, b, shape))

ALL = STOPS
for i, s in enumerate(ALL):
    s["n"] = i + 1

features = []
print("legs")
for i, (a, b, shape) in enumerate(legs):
    km = length_km(shape)
    features.append({
        "type": "Feature",
        "properties": {"mode": "bike", "seq": i + 1, "line": "by bike",
                       "from": a["name"], "to": b["name"],
                       "from_n": a["n"], "to_n": b["n"],
                       "km": round(km, 2), "note": b["note"],
                       # Ridden, but not recorded: `routed` draws it dashed.
                       "source": "routed"},
        "geometry": {"type": "LineString",
                     "coordinates": [[round(p[1], 6), round(p[0], 6)]
                                     for p in shape]},
    })
    print(f"  {a['n']:2d} -> {b['n']:2d}  {km:5.2f} km / {km/1.609344:4.1f} mi"
          f"  {len(shape):4d} pts  {a['key']} -> {b['key']}")

# ------------------------------------------------------------------ write ---
stops_fc = {"type": "FeatureCollection", "features": [
    {"type": "Feature",
     "properties": {"n": s["n"], "name": s["name"], "key": s["key"],
                    "arrive": "bike", "note": s["note"]},
     "geometry": {"type": "Point",
                  "coordinates": [round(s["lng"], 6), round(s["lat"], 6)]}}
    for s in ALL]}
lines_fc = {"type": "FeatureCollection", "features": features}
icons = {"medici": "food", "bikeparking": "bike", "cornell": "park",
         "ellsworth51": "park"}

# Pictures: placed by pick_photos.py, captioned here. A script can say where a
# picture was taken; it cannot say what is in it.
CAPTIONS = {
    "IMG_3960.HEIC": "A merchandise stand setting up at the Grant Park underpass "
                     "by the Museum Campus",
    "IMG_3961.HEIC": "The Lakefront Trail through the prairie grasses near "
                     "63rd Street",
    "IMG_3966.HEIC": "The Obama Presidential Center's museum tower, from the "
                     "Jackson Park paths",
    "IMG_3967.HEIC": "A black glass hall on the Obama Presidential Center campus",
    "IMG_3969.HEIC": "The Hadiya Pendleton Atrium, inside the Obama Presidential "
                     "Center",
    "IMG_3973.HEIC": "The Mansueto Library dome beside the Regenstein, on Ellis "
                     "Avenue",
    "IMG_3975.HEIC": "A yellow brick apartment building on 51st Street",
    "IMG_3978.HEIC": "A red brick Italianate house by Drexel and Oakwood",
}
GEO = os.path.join(HERE, "photos.geojson")
if not os.path.exists(GEO):
    raise SystemExit(f"missing {GEO}\nRun pick_photos.py first.")
photos_fc = json.load(open(GEO))
for f in photos_fc["features"]:
    f["properties"]["caption"] = CAPTIONS.get(f["properties"]["file"], "")
    if not f["properties"]["caption"]:
        print(f"  ! no caption for {f['properties']['file']}")

tpl = open(os.path.join(HERE, "template.html")).read()
tpl = tpl.replace("__LINES__", json.dumps(lines_fc, separators=(",", ":")))
tpl = tpl.replace("__STOPS__", json.dumps(stops_fc, separators=(",", ":")))
tpl = tpl.replace("__PHOTOS__", json.dumps(photos_fc, separators=(",", ":")))
tpl = tpl.replace("__ICONS__", json.dumps(icons, separators=(",", ":")))
km = sum(f["properties"]["km"] for f in features)
tpl = tpl.replace("__MILES__", f"{km/1.609344:.0f}")
out = os.path.join(ROOT, "chicago-south-side-ride-map.html")
open(out, "w").write(tpl)
print(f"\ntotal {km:.2f} km / {km/1.609344:.2f} mi over {len(features)} legs")
print(f"wrote {out}, {len(tpl)} bytes")
