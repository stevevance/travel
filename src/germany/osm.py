"""Overpass and Valhalla access, shared by the discovery and build scripts.

Same contract as the other city directories: fetch once into a gitignored cache
next to this file, fall back to the second Overpass mirror, and sleep between
calls because both of them rate-limit.
"""
import json, math, os, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OVERPASS = ["https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter"]
VALHALLA = "https://valhalla1.openstreetmap.de/route"
UA = {"User-Agent": "steven-personal-itinerary-map/1.0 (personal travel notes)"}


def overpass(query, cache, tries=4):
    """Fetch once, then reuse. Deleting the cache just costs a re-fetch.

    Both mirrors rate-limit, and this day needs a dozen queries, so a failure is
    retried around the mirrors with a widening wait rather than given up on: a
    429 means "later", not "no".
    """
    path = os.path.join(HERE, cache)
    if os.path.exists(path):
        return json.load(open(path))
    last = None
    for attempt in range(tries):
        for url in OVERPASS:
            try:
                req = urllib.request.Request(
                    url, data=urllib.parse.urlencode({"data": query}).encode(),
                    headers=UA)
                # 90 s, not 300: a mirror that has gone sick accepts the
                # connection and then never answers, and a long timeout there
                # costs more than simply asking the other one. Overpass's own
                # [timeout:] in the query is the server-side limit; this is only
                # how long to wait for a mirror that has stopped talking.
                d = json.load(urllib.request.urlopen(req, timeout=90))
                json.dump(d, open(path, "w"))
                return d
            except Exception as ex:
                last = ex
                wait = 5 * 2 ** attempt
                print(f"  overpass {url.split('/')[2]} failed ({ex}); "
                      f"waiting {wait}s")
                time.sleep(wait)
    raise SystemExit(f"both Overpass endpoints failed after {tries} rounds: {last}")


def dist(a, b):
    """Rough planar meters; fine at this latitude for nearest-point work."""
    dy = (a[0] - b[0]) * 111320.0
    dx = (a[1] - b[1]) * 111320.0 * math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)


def length_m(pts):
    return sum(dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def stitch(rel):
    """Walk a relation's track ways in order into one polyline.

    Public-transport v2 relations list stops first with roles and the track ways
    last with an empty role, so only empty-role ways are geometry. Ways whose
    endpoints run against the direction of travel get flipped.
    """
    ways = [m["geometry"] for m in rel.get("members", [])
            if m["type"] == "way" and m.get("role", "") == "" and "geometry" in m]
    if not ways:
        return []
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
        if d < best:
            best, bi = d, i
    return bi, best


def decode6(shape):
    """Valhalla returns its shapes as polyline6."""
    coords, lat, lon, i = [], 0, 0, 0
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


def valhalla(points, costing, cache):
    """Route through every point, ends as breaks, cached like Overpass."""
    path = os.path.join(HERE, cache)
    if os.path.exists(path):
        d = json.load(open(path))
    else:
        locs = [{"lat": p[0], "lon": p[1],
                 "type": "break" if i in (0, len(points) - 1) else "through"}
                for i, p in enumerate(points)]
        body = {"locations": locs, "costing": costing,
                "directions_options": {"units": "kilometers"}}
        req = urllib.request.Request(
            VALHALLA + "?json=" + urllib.parse.quote(json.dumps(body)), headers=UA)
        d = json.load(urllib.request.urlopen(req, timeout=60))
        json.dump(d, open(path, "w"))
    out = []
    for lg in d["trip"]["legs"]:
        out.extend(decode6(lg["shape"]))
    return out, d["trip"]["summary"]["length"] * 1000
