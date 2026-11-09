"""Build the 3D model of the 8 November ride, drawn like line-art vector maps:
white buildings outlined in ink, hatched water, and the city cut off in an
island around the route.

The route is read back out of chicago-south-side-ride-map.html rather than
rebuilt, so it is the published line - already clipped short of home - and
build.py stays the one place the ride is defined. Run that first.

Buildings, parks, water, the lake shore and streets come from Overpass for a
corridor around the line, are cut to it, projected to metres and written into
the page as integers.

    python3 src/chicago-south-side-ride/build.py      # the 2D map, first
    python3 src/chicago-south-side-ride/build_3d.py   # -> chicago-south-side-ride-3d.html
"""
import json, math, os, re, time, urllib.parse, urllib.request
from shapely.geometry import (LineString, MultiPolygon, Point,
                              Polygon, box)
from shapely.affinity import scale, translate
from shapely.geometry.polygon import orient
from shapely.ops import linemerge, polygonize, unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OVERPASS = "https://overpass-api.de/api/interpreter"
UA = {"User-Agent": "steven-personal-itinerary-map/1.0 (personal travel notes)"}

# How far the island reaches either side of the line, and how much the outline
# is rounded off so it reads as one landmass rather than a tube.
REACH_M = 420
ROUND_M = 350

# ------------------------------------------------------------- the route ---
page = open(os.path.join(ROOT, "chicago-south-side-ride-map.html")).read()
LINES = json.loads(re.search(r"const LINES = (\{.*?\});\n", page).group(1))
STOPS = json.loads(re.search(r"const STOPS = (\{.*?\});\n", page).group(1))

coords = [c for f in LINES["features"] for c in f["geometry"]["coordinates"]]
LON0 = sum(c[0] for c in coords) / len(coords)
LAT0 = sum(c[1] for c in coords) / len(coords)
KX = 111320 * math.cos(math.radians(LAT0))
KY = 110540


def xy(lon, lat):
    return ((lon - LON0) * KX, (lat - LAT0) * KY)


def lonlat(x, y):
    return (x / KX + LON0, y / KY + LAT0)


# Thinned to within 3 m of the routed line: Valhalla puts a node every few
# metres, and a bend made of slivers is what made the playback dot jitter.
route = [LineString([xy(*c) for c in f["geometry"]["coordinates"]]).simplify(3)
         for f in LINES["features"]]
island = unary_union(route).buffer(REACH_M + ROUND_M).buffer(-ROUND_M)
island = island.simplify(8)
if isinstance(island, MultiPolygon):
    island = max(island.geoms, key=lambda g: g.area)
island = Polygon(island.exterior)          # no holes in the landmass
print(f"island {island.area / 1e6:.1f} km2")

# --------------------------------------------------------------- overpass ---
def overpass(query, cache):
    path = os.path.join(HERE, cache)
    if os.path.exists(path):
        return json.load(open(path))
    req = urllib.request.Request(
        OVERPASS, data=urllib.parse.urlencode({"data": query}).encode(),
        headers=UA)
    d = json.load(urllib.request.urlopen(req, timeout=300))
    json.dump(d, open(path, "w"))
    time.sleep(1.1)
    return d


outline = island.buffer(60).simplify(40)
poly = " ".join(f"{lat:.5f} {lon:.5f}"
                for lon, lat in (lonlat(x, y) for x, y in outline.exterior.coords))
minx, miny, maxx, maxy = island.bounds
w, s = lonlat(minx - 3000, miny - 3000)
e, n = lonlat(maxx + 3000, maxy + 3000)
osm = overpass(f"""[out:json][timeout:240];
(
  way["building"](poly:"{poly}");
  relation["building"](poly:"{poly}");
  way["leisure"~"^(park|golf_course|pitch|garden|nature_reserve)$"](poly:"{poly}");
  way["landuse"~"^(grass|meadow|recreation_ground|cemetery)$"](poly:"{poly}");
  way["natural"~"^(water|wood|scrub|grassland|beach|sand)$"](poly:"{poly}");
  relation["natural"="water"](poly:"{poly}");
  way["highway"~"^(motorway|trunk|primary|secondary|tertiary|residential|unclassified|service|cycleway|footway|path|pedestrian|living_street|motorway_link|trunk_link|primary_link)$"](poly:"{poly}");
  way["railway"~"^(rail|light_rail|subway)$"](poly:"{poly}");
);
out geom;""", "osm_3d.json")
print(f"{len(osm['elements'])} OSM elements")

# Lake Michigan is not tagged as coastline in OSM but as one enormous water
# relation. Take only its member ways that reach the corridor's box.
shore_osm = overpass(f"""[out:json][timeout:120];
rel["name"="Lake Michigan"]["natural"="water"];
way(r)({s:.5f},{w:.5f},{n:.5f},{e:.5f});
out geom;""", "lake_3d.json")
for el in shore_osm["elements"]:
    el.setdefault("tags", {})["natural"] = "coastline"
osm["elements"] += shore_osm["elements"]


def ring(geom):
    return [xy(p["lon"], p["lat"]) for p in geom]


def polygons(el):
    """A way or multipolygon relation as shapely polygons, or nothing."""
    if el["type"] == "way":
        pts = ring(el.get("geometry", []))
        if len(pts) < 4 or pts[0] != pts[-1]:
            return []
        p = Polygon(pts)
        return [p if p.is_valid else p.buffer(0)]
    outer = [LineString(ring(m["geometry"])) for m in el.get("members", [])
             if m.get("role") == "outer" and m.get("geometry")]
    inner = [LineString(ring(m["geometry"])) for m in el.get("members", [])
             if m.get("role") == "inner" and m.get("geometry")]
    o = unary_union(list(polygonize(linemerge(outer)))) if outer else None
    if o is None or o.is_empty:
        return []
    if inner:
        o = o.difference(unary_union(list(polygonize(linemerge(inner)))))
    return [o]


# Stories from the City of Chicago's building footprints, for the buildings
# OSM gives no height or levels - about half of them here.
CITY = "https://data.cityofchicago.org/resource/vmwt-djju.json"


def city_footprints():
    path = os.path.join(HERE, "footprints_3d.json")
    if os.path.exists(path):
        return json.load(open(path))
    bw, bs = lonlat(minx - 200, miny - 200)
    be, bn = lonlat(maxx + 200, maxy + 200)
    # The portal errors at random and more often on big pages, so ask for
    # small ones, keep asking, and keep each page so a rerun picks up again.
    pages = os.path.join(HERE, "footprints_pages")
    os.makedirs(pages, exist_ok=True)
    rows, off, size = [], 0, 1000
    while True:
        cache = os.path.join(pages, f"{off}.json")
        if os.path.exists(cache):
            page = json.load(open(cache))
        else:
            q = urllib.parse.urlencode({
                "$select": "stories,the_geom", "$limit": size, "$offset": off,
                "$where": f"within_box(the_geom,{bn:.5f},{bw:.5f},{bs:.5f},{be:.5f})"})
            for tries in range(40):
                try:
                    page = json.load(urllib.request.urlopen(
                        urllib.request.Request(CITY + "?" + q, headers=UA), timeout=300))
                    break
                except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
                    if tries == 39:
                        raise
                    time.sleep(10)
            json.dump(page, open(cache, "w"))
            print(f"  footprints {off + len(page)}", flush=True)
        # A filter on stories makes the portal time out; drop zeros here.
        rows += [r for r in page if r.get("stories") not in (None, "0")]
        if len(page) < size:
            break
        off += size
    json.dump(rows, open(path, "w"))
    return rows


from shapely.geometry import shape
from shapely.strtree import STRtree
_fp, _st = [], []
for r in city_footprints():
    try:
        st = float(r["stories"])
        g = shape(r["the_geom"])
    except (KeyError, ValueError, TypeError):
        continue
    if st <= 0 or st > 120:
        continue
    _fp.append(Polygon([xy(*c) for c in max(
        (g.geoms if hasattr(g, "geoms") else [g]), key=lambda q: q.area).exterior.coords]))
    _st.append(st)
TREE = STRtree(_fp)
print(f"{len(_fp)} city footprints with stories")


def city_stories(poly):
    pt = poly.representative_point()
    for i in TREE.query(pt):
        if _fp[i].contains(pt):
            return _st[i]
    return None


def height(t, poly=None):
    for k in ("height", "building:height"):
        v = t.get(k)
        if v:
            try:
                return float(re.sub(r"[^\d.]", "", v.split(";")[0]))
            except ValueError:
                pass
    lv = t.get("building:levels")
    if lv:
        try:
            return float(lv.split(";")[0]) * 3.6 + 1.5
        except ValueError:
            pass
    st = city_stories(poly) if poly is not None else None
    if st:
        return st * 3.6 + 1.5
    b = t.get("building")
    if b in ("garage", "garages", "shed", "carport", "roof"):
        return 3.5
    if b in ("house", "detached", "semidetached_house"):
        return 8.5
    return 10.0


def pieces(g):
    """Every polygon in g, as lists of integer rings."""
    if g.is_empty:
        return []
    geoms = g.geoms if hasattr(g, "geoms") else [g]
    out = []
    for p in geoms:
        if p.geom_type != "Polygon" or p.area < 6:
            continue
        # Outer ring counter-clockwise, holes clockwise: the page draws a wall
        # from one side only, so a ring the wrong way round loses its walls.
        p = orient(p, 1.0)
        rings = [p.exterior] + list(p.interiors)
        out.append([[[round(x), round(y)] for x, y in r.coords[:-1]]
                    for r in rings])
    return out


def strokes(g):
    if g.is_empty:
        return []
    geoms = g.geoms if hasattr(g, "geoms") else [g]
    return [[[round(x), round(y)] for x, y in l.coords]
            for l in geoms if l.geom_type == "LineString" and l.length > 5]


# The Obama Presidential Center's museum tower is one flat outline in OSM with
# nine levels on it. The real thing is about 235 ft and not a prism: straight
# for its lower part, flaring outward above that, with a notch in its
# northeast corner and a crown that draws back in a little. Drawn as lofts,
# walls leaning from one outline to another, read off Apple Maps' model.
OBAMA_TOWER = 1434240394
OBAMA_H = 72.0          # metres, about 235 ft


def obama_tower(base):
    # 35 nodes on four nearly straight sides: square it off to four corners.
    base = orient(base.simplify(1.5), 1.0)
    c = base.centroid
    ring_ = lambda p: [[round(x, 1), round(y, 1)] for x, y in p.exterior.coords[:-1]]
    grow = lambda p, f: scale(p, f, f, origin=c)
    wide = grow(base, 1.18)
    # The notch: a quarter of each side in from the northeast corner.
    pts = [Point(q) for q in wide.exterior.coords[:-1]]
    k = max(range(len(pts)), key=lambda i: pts[i].x + pts[i].y)
    v, a, b = pts[k], pts[k - 1], pts[(k + 1) % len(pts)]
    da, db = ((a.x - v.x) * 0.25, (a.y - v.y) * 0.25), ((b.x - v.x) * 0.25, (b.y - v.y) * 0.25)
    notch = Polygon([(v.x, v.y), (v.x + da[0], v.y + da[1]),
                     (v.x + da[0] + db[0], v.y + da[1] + db[1]), (v.x + db[0], v.y + db[1])])
    notched = orient(wide.difference(notch.buffer(0.01, join_style=2)).simplify(0.05), 1.0)
    H = OBAMA_H
    stages = [(0, 0.40, base, base),                          # straight
              (0.40, 0.56, base, wide),                       # flaring out
              (0.56, 0.88, notched, grow(notched, 1.03)),     # notched, leaning on
              (0.88, 1.00, grow(wide, 1.03), grow(wide, 0.99))]  # crown, drawing in
    return [[round(z0 * H, 1), round(z1 * H, 1), ring_(lo), ring_(up)]
            for z0, z1, lo, up in stages]


buildings, lofts, green, water, roads, rails, coast = [], [], [], [], [], [], []
for el in osm["elements"]:
    t = el.get("tags", {})
    if t.get("natural") == "coastline":
        coast.append(LineString(ring(el["geometry"])))
        continue
    if "building" in t:
        # building=no is an indoor room or corridor drawn inside a real
        # building (the Obama Center's Forum, restaurant, auditorium).
        if (t.get("building") == "no" or "indoor" in t
                or t.get("location") == "underground"):
            continue
        if el["id"] == OBAMA_TOWER:
            lofts.extend(obama_tower(polygons(el)[0]))
            continue
        mh = 0.0
        try:
            mh = float(re.sub(r"[^\d.]", "", t.get("min_height", "0")) or 0)
        except ValueError:
            pass
        for p in polygons(el):
            h = height(t, p)
            for pc in pieces(p.intersection(island)):
                buildings.append([round(h, 1), round(mh, 1)] + [pc])
        continue
    if "highway" in t or "railway" in t:
        line = LineString(ring(el["geometry"]))
        cut = line.intersection(island)
        hw = t.get("highway", "")
        kind = (3 if hw in ("motorway", "trunk", "motorway_link", "trunk_link")
                else 2 if hw in ("primary", "secondary", "primary_link")
                else 0 if hw in ("footway", "path", "cycleway", "pedestrian", "service")
                else 1)
        for s_ in strokes(cut):
            (rails if "railway" in t else roads).append(
                s_ if "railway" in t else [kind] + [s_])
        continue
    target = water if t.get("natural") == "water" else green
    for p in polygons(el):
        target.extend(pieces(p.intersection(island)))

# The lake: cut a box around the island into faces along the shore, and every
# face that reaches the box's east side is lake.
frame = box(minx - 1500, miny - 1500, maxx + 1500, maxy + 1500)
faces = polygonize(unary_union([frame.boundary] +
                               [c.intersection(frame) for c in coast]))
east = LineString([(maxx + 1500, miny - 1500), (maxx + 1500, maxy + 1500)])
lake = unary_union([f for f in faces if f.distance(east) < 1]).intersection(island)
water.extend(pieces(lake))
print(f"{len(buildings)} buildings, {len(green)} green, {len(water)} water, "
      f"{len(roads)} roads, {len(rails)} rails, lake {lake.area / 1e6:.1f} km2")

# --------------------------------------------------------------------- out ---
model = {
    "island": pieces(island)[0],
    "buildings": buildings,
    "lofts": lofts,
    "green": green,
    "water": water,
    "roads": roads,
    "rails": rails,
    "route": [[[round(x), round(y)] for x, y in l.coords] for l in route],
    "stops": [{"n": f["properties"]["n"], "name": f["properties"]["name"],
               "xy": [round(v) for v in xy(*f["geometry"]["coordinates"])]}
              for f in STOPS["features"]],
    "miles": round(sum(f["properties"]["km"] for f in LINES["features"])
                   / 1.609344, 1),
}
tpl = open(os.path.join(HERE, "template_3d.html")).read()
html = tpl.replace("__MODEL__", json.dumps(model, separators=(",", ":")))
out = os.path.join(ROOT, "chicago-south-side-ride-3d.html")
open(out, "w").write(html)
print(f"wrote {out}, {len(html) / 1e6:.2f} MB")
