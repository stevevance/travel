"""Build a commute from Printers Row to Aurora, by bike and Metra.

The odd one out again, four ways:

  - It is someone else's route, and it arrived as a drawing, traced by hand on
    drawonamap.com in three colours. `data/bike-metra-commute/drawn.geojson`
    is that drawing with the styling stripped and each stroke's colour kept as
    `stress`: `low`, `high` or `metra`.
  - Colour here is not mode. Two of the three colours are the same bicycle, so
    the page keys its palette off `stress` instead (`categoryBy` in the
    template), the way Bruges keys off `ride`. High stress is the rider's
    definition: a speed limit of 35 mph or more and no bike infrastructure of
    any kind.
  - The bicycle legs are map-matched, not routed. Asking Valhalla for a route
    through the drawn vertices doubled back four times over - exactly the
    over-constraining the README warns about - so each run of one colour goes
    to `trace_route` instead, which snaps the drawing to the ways under it
    rather than choosing a way of its own. Pedestrian costing, because bicycle
    costing gave up on one path between two cul-de-sacs; the result stays
    within a few metres of the drawing, and the build checks that it does.
    The legs still carry `source: "routed"` and draw dashed: nobody recorded
    this.
  - It is not linked from the index, and names nobody. Neither end of the
    commute is in the data. The drawing ran from a door to a workplace; the
    stroke from the door to Harrison Street and everything past Molitor Road
    and Diehl Road were dropped before the file was committed, so the line
    starts at one public corner and stops at another, well short of where it
    was going. Do not put either end back.

The train is the BNSF relation from OSM, cut between Halsted Street and
Route 59, and draws solid like every other `osm` leg.

    python3 src/bike-metra-commute/build.py   # -> bike-metra-commute-map.html

Overpass and Valhalla responses are cached next to this file and gitignored.
"""
import json, math, os, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
DRAWN = os.path.join(ROOT, "data", "bike-metra-commute", "drawn.geojson")
OVERPASS = ["https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter"]
TRACE = "https://valhalla1.openstreetmap.de/trace_route"
ATTRS = "https://valhalla1.openstreetmap.de/trace_attributes"
UA = {"User-Agent": "steven-personal-itinerary-map/1.0 (personal travel notes)"}
BNSF = 933014            # Metra BNSF Railway: Chicago => Aurora

# ------------------------------------------------------------------ stops ---
# One stop wherever the colour changes, so the key reads as the ride does:
# each row is the next stretch and says what kind of stretch it was. Stop k
# sits at the start of run k (counting from 1), and the last at the end.
PHOTO_DIR = "photos/bike-metra-commute/"
CREDIT = "Image: Google Street View."


def spot(img, size, alt, caption):
    """A picture inside a stop's popup. These are Street View frames, not
    photographs of the ride, and are credited as such. A stop's picture goes
    in its popup rather than on the photo layer because a camera dot at a
    stop's own coordinates sits under the stop and cannot be clicked."""
    return (f'<img class="spot" loading="lazy" src="{PHOTO_DIR}{img}" '
            f'style="aspect-ratio:{size[0]}/{size[1]}" alt="{alt}">'
            f'{caption} {CREDIT}')


STOPS = [
 dict(key="start", name="Harrison & Dearborn, Printers Row",
      note="Start of the ride."),
 dict(key="halsted", name="Halsted Street Metra station",
      note="On the BNSF line, at 16th Street."),
 dict(key="route59", name="Route 59 Metra station",
      note="Off the train and back on the bike."),
 dict(key="sidepath", name="North Aurora Road, end of the sidepath",
      note="The path beside the road stops here, and the next stretch is in "
           "the roadway."
           + spot("north-aurora-road-sidepath-end.jpg", (1400, 904),
                  "North Aurora Road looking west: the sidepath on the right "
                  "stops short of a low rail viaduct, and the two-lane road "
                  "goes on under it with no shoulder.",
                  "Looking west toward the rail viaduct.")),
 dict(key="pensbury", name="Pensbury Lane",
      note="Off North Aurora Road and onto side streets."
           + spot("pensbury-lane-signal.jpg", (1400, 1106),
                  "A signalised corner on North Aurora Road, with a marked "
                  "crosswalk and a two-lane residential street running "
                  "north between houses and trees.",
                  "The signal at Pensbury Lane, looking north.")),
 dict(key="molitor", name="Molitor Road at Diehl Road",
      note="Where the map stops, short of the end of the ride."),
]
for i, s_ in enumerate(STOPS):
    s_["n"] = i + 1

# Pictures that are not at a stop go on the photo layer, as camera dots.
# map-common prints `time` as the popup's heading; these have no time worth
# printing, so it carries the place instead.
PHOTOS = [
 dict(lat=41.7815605, lng=-88.2351135, img="north-aurora-road-city-limit.jpg",
      time="North Aurora Road, the Aurora city limit",
      caption="A sidewalk starts on the north side at the city sign; the "
              "roadway is still two lanes with no shoulder. " + CREDIT),
]
ICONS = {"start": "bike", "halsted": "train", "route59": "train"}
LINE = {"low": "low stress", "high": "high stress", "metra": "Metra BNSF"}


# --------------------------------------------------------------- geometry ---
def dist(a, b):
    """Rough planar metres between (lat, lon) pairs; fine at this latitude."""
    dy = (a[0] - b[0]) * 111320.0
    dx = (a[1] - b[1]) * 111320.0 * math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)


def length_m(pts):
    return sum(dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def seg_dist(p, a, b):
    """Metres from p to the segment a-b."""
    k = math.cos(math.radians(p[0]))
    px, py = (p[1] - a[1]) * 111320.0 * k, (p[0] - a[0]) * 111320.0
    bx, by = (b[1] - a[1]) * 111320.0 * k, (b[0] - a[0]) * 111320.0
    L = bx * bx + by * by
    t = 0 if L == 0 else max(0.0, min(1.0, (px * bx + py * by) / L))
    return math.hypot(px - t * bx, py - t * by)


def deviation(line, ref):
    """The farthest any point of `line` gets from the polyline `ref`."""
    return max(min(seg_dist(p, ref[i], ref[i + 1]) for i in range(len(ref) - 1))
               for p in line)


def densify(pts, step=15):
    """trace_route matches points, not segments: a 1.5 km stroke with a vertex
    at each end gives it nothing to follow. One point every 15 m does."""
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(dist(a, b) // step))
        out += [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n)
                for i in range(1, n + 1)]
    return out


def decode6(shape):
    """Valhalla returns its geometry as a polyline6."""
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


# ---------------------------------------------------------------- fetches ---
def trace(url, pts, cache, extra=None):
    """Hand a drawn run to Valhalla's map-matcher. Cached; deleting the cache
    only costs a re-fetch."""
    path = os.path.join(HERE, cache)
    if os.path.exists(path):
        return json.load(open(path))
    body = {"shape": [{"lat": p[0], "lon": p[1]} for p in densify(pts)],
            "costing": "pedestrian", "shape_match": "map_snap",
            "trace_options": {"search_radius": 25, "gps_accuracy": 10,
                              "turn_penalty_factor": 200},
            "directions_options": {"units": "kilometers"}}
    body.update(extra or {})
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers=dict(UA, **{"Content-Type": "application/json"}))
    try:
        d = json.load(urllib.request.urlopen(req, timeout=60))
    except urllib.error.HTTPError as ex:
        # The body says which limit was hit; a bare 400 does not.
        raise SystemExit(f"{cache}: {ex.code} {ex.read()[:300]}")
    json.dump(d, open(path, "w"))
    time.sleep(1.1)
    return d


def match(pts, cache):
    """Snap a drawn run to the ways under it."""
    d = trace(TRACE, pts, cache)
    out = []
    for lg in d["trip"]["legs"]:
        out.extend(decode6(lg["shape"]))
    return out, d["trip"]["summary"]["length"]        # km


def limits(pts, cache):
    """Posted speed limits along a run, as OSM has them: one sign for each
    stretch of one street at one limit, placed at the middle of the stretch.

    Only where a way carries `maxspeed`; most of the side streets here do not,
    and a missing tag is not a limit. Stretches under 150 m are left out: the
    one on this route is a ten-metre fragment of Harrison Street tagged
    20 mph, and a sign for it would speak for the whole street."""
    d = trace(ATTRS, pts, cache, {"filters": {"action": "include", "attributes": [
        "edge.names", "edge.length", "edge.speed_limit",
        "edge.begin_shape_index", "edge.end_shape_index", "shape"]}})
    shape = decode6(d["shape"])
    groups = []
    for e in d["edges"]:
        k = (e.get("names", [""])[0], e.get("speed_limit") or 0)
        if groups and groups[-1][0] == k:
            groups[-1][2] = e["end_shape_index"]
        else:
            groups.append([k, e["begin_shape_index"], e["end_shape_index"]])
    out = []
    for (name, kph), i0, i1 in groups:
        seg = shape[i0:i1 + 1]
        if not kph or len(seg) < 2 or length_m(seg) < 150:
            continue
        # The point halfway along, by distance rather than by vertex count.
        half, run = length_m(seg) / 2, 0.0
        for a, c in zip(seg, seg[1:]):
            step = dist(a, c)
            if run + step >= half:
                t = (half - run) / step if step else 0
                mid = (a[0] + (c[0] - a[0]) * t, a[1] + (c[1] - a[1]) * t)
                break
            run += step
        out.append({"name": name, "mph": 5 * round(kph / 1.609344 / 5),
                    "lat": round(mid[0], 6), "lng": round(mid[1], 6)})
    return out


def overpass(query, cache):
    path = os.path.join(HERE, cache)
    if os.path.exists(path):
        return json.load(open(path))
    last = None
    for attempt in range(3):
        for url in OVERPASS:
            try:
                req = urllib.request.Request(
                    url, data=urllib.parse.urlencode({"data": query}).encode(),
                    headers=UA)
                d = json.load(urllib.request.urlopen(req, timeout=90))
                json.dump(d, open(path, "w"))
                return d
            except Exception as ex:
                last = ex
                wait = 5 * 2 ** attempt
                print(f"  overpass {url.split('/')[2]} failed ({ex}); "
                      f"waiting {wait}s")
                time.sleep(wait)
    raise SystemExit(f"both Overpass endpoints failed: {last}")


def stitch(rel):
    """Walk a relation's track ways in order into one polyline. Only the
    empty-role ways are track; ways running against the direction of travel
    get flipped."""
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
    return min(range(len(line)), key=lambda i: dist(line[i], pt))


# ------------------------------------------------------------------- runs ---
# Consecutive strokes of one colour are one run, and one leg on the map.
runs = []
for f in json.load(open(DRAWN))["features"]:
    pts = [(c[1], c[0]) for c in f["geometry"]["coordinates"]]
    if runs and runs[-1][0] == f["properties"]["stress"]:
        runs[-1][1].extend(pts[1:])
    else:
        runs.append([f["properties"]["stress"], pts])
if len(runs) != len(STOPS) - 1:
    raise SystemExit(f"{len(runs)} runs in the drawing but {len(STOPS)} stops: "
                     "the colours changed somewhere STOPS does not know about.")

features, signs = [], []
print("legs")
for i, (stress, pts) in enumerate(runs):
    a, b = STOPS[i], STOPS[i + 1]
    a.setdefault("at", pts[0]); b["at"] = pts[-1]
    if stress == "metra":
        rel = overpass(f"[out:json][timeout:60];relation({BNSF});out geom;",
                       "rel_bnsf.json")["elements"][0]
        track = stitch(rel)
        i0, i1 = nearest(track, pts[0]), nearest(track, pts[-1])
        for end, idx in ((pts[0], i0), (pts[-1], i1)):
            if dist(end, track[idx]) > 150:
                print(f"  ! station end {dist(end, track[idx]):.0f} m from the track")
        shape = track[i0:i1 + 1]
        km = length_m(shape) / 1000
        mode, source, part = "train", "osm", "train"
    else:
        shape, km = match(pts, f"trace_{i}_{stress}.json")
        # The whole point of matching rather than routing is that the line
        # stays where it was drawn. Say so loudly if it did not.
        off = max(deviation(shape, pts), deviation(pts, shape))
        drawn = length_m(pts) / 1000
        if off > 40 or abs(km - drawn) > 0.1 * drawn + 0.02:
            print(f"  ! run {i} strays {off:.0f} m from the drawing, "
                  f"{km:.2f} km against {drawn:.2f} drawn")
        mode, source = "bike", "routed"
        signs += limits(pts, f"attrs_{i}_{stress}.json")
        part = "chicago" if i == 0 else "aurora"
    features.append({
        "type": "Feature",
        "properties": {
            "mode": mode, "stress": stress, "part": part, "seq": i + 1,
            "line": LINE[stress], "source": source,
            "from": a["name"], "to": b["name"],
            "from_n": a["n"], "to_n": b["n"], "km": round(km, 2)},
        "geometry": {"type": "LineString",
                     "coordinates": [[round(p[1], 6), round(p[0], 6)]
                                     for p in shape]},
    })
    print(f"  {a['n']} -> {b['n']}  {stress:5s} {km:6.2f} km / "
          f"{km/1.609344:5.2f} mi  {len(shape):4d} pts")

# ------------------------------------------------------------------ write ---
arrive = ["low"] + [f["properties"]["stress"] for f in features]
stops_fc = {"type": "FeatureCollection", "features": [
    {"type": "Feature",
     "properties": {"n": s["n"], "name": s["name"], "key": s["key"],
                    "arrive": arrive[j], "note": s["note"]},
     "geometry": {"type": "Point",
                  "coordinates": [round(s["at"][1], 6), round(s["at"][0], 6)]}}
    for j, s in enumerate(STOPS)]}
lines_fc = {"type": "FeatureCollection", "features": features}
photos_fc = {"type": "FeatureCollection", "features": [
    {"type": "Feature",
     "properties": {"img": PHOTO_DIR + ph["img"], "time": ph["time"],
                    "caption": ph["caption"]},
     "geometry": {"type": "Point", "coordinates": [ph["lng"], ph["lat"]]}}
    for ph in PHOTOS]}


def miles(pred):
    return sum(f["properties"]["km"] for f in features
               if pred(f["properties"])) / 1.609344

low = miles(lambda p: p["stress"] == "low")
high = miles(lambda p: p["stress"] == "high")
train = miles(lambda p: p["stress"] == "metra")

tpl = open(os.path.join(HERE, "template.html")).read()
tpl = tpl.replace("__LINES__", json.dumps(lines_fc, separators=(",", ":")))
tpl = tpl.replace("__STOPS__", json.dumps(stops_fc, separators=(",", ":")))
tpl = tpl.replace("__PHOTOS__", json.dumps(photos_fc, separators=(",", ":")))
tpl = tpl.replace("__SIGNS__", json.dumps(signs, separators=(",", ":")))
tpl = tpl.replace("__ICONS__", json.dumps(ICONS, separators=(",", ":")))
# The satellite chooser needs a Mapbox public token, and this repo holds none.
# Give the build one in MAPBOX_KEY, or as "mapbox_key" in the gitignored
# data/bike-metra-commute/private.json; without it the page is built without
# the chooser. The token lands in the generated page, which is committed and
# public, so it must be one whose URL restrictions allow this site.
PRIVATE = os.path.join(ROOT, "data", "bike-metra-commute", "private.json")
mapbox = os.environ.get("MAPBOX_KEY", "")
if not mapbox and os.path.exists(PRIVATE):
    mapbox = json.load(open(PRIVATE)).get("mapbox_key", "")
if mapbox and not mapbox.startswith("pk."):
    raise SystemExit("MAPBOX_KEY is not a public (pk.) token; a secret one "
                     "must never be written into a page.")
tpl = tpl.replace("__MAPBOX__", json.dumps(mapbox))
print("satellite chooser:", "on" if mapbox else "off (no Mapbox token)")
# The copy quotes these, so they come from the legs rather than being typed.
tpl = tpl.replace("__BIKE__", f"{low + high:.1f}")
tpl = tpl.replace("__LOW__", f"{low:.1f}")
tpl = tpl.replace("__HIGH__", f"{high:.1f}")
tpl = tpl.replace("__TRAIN__", f"{train:.0f}")
tpl = tpl.replace("__PCT__", f"{100 * high / (low + high):.0f}")
out = os.path.join(ROOT, "bike-metra-commute-map.html")
open(out, "w").write(tpl)

print("\nspeed limits:", ", ".join(f"{s['name']} {s['mph']}" for s in signs))
print(f"bike {low + high:.2f} mi: {low:.2f} low stress, {high:.2f} high "
      f"({100 * high / (low + high):.0f}%); train {train:.1f} mi")
print(f"wrote {out}, {len(tpl)} bytes")
