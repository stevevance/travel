"""Cut the Prague transit legs out of the PID GTFS feed.

OpenStreetMap is out of date for the one leg that matters most here. Its AE
relation runs from the Hlavní nádraží by the Hlávkův most, 670 m from where
Wednesday's photographs put the bus on the Štefánikův most; PID's own feed has
the route the bus actually took, within 40 m of every photograph. So the city's
transit comes from the operator's GTFS rather than from OSM route relations,
which is the one way this page differs from every other map in the repo.

For each leg this finds the line's trips that call at the boarding stop before
the alighting stop, takes their commonest shape, and slices it between the two
stops. Where more than one line could have been taken it tries each, and keeps
the first that passes every photograph listed against the leg, so the choice is
made by the evidence and not by the order of the list.

    python3 src/prague/gtfs_lines.py    # -> data/prague/transit.geojson

The feed is 50 MB and is cached, gitignored, at data/prague/PID_GTFS.zip.
Its output is committed, so a clone with no network can rebuild the page.
"""
import csv, io, json, os, sys, urllib.request, zipfile
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from osm import ROOT, nearest, dist

FEED = "https://data.pid.cz/PID_GTFS.zip"
ZIP  = os.path.join(ROOT, "data", "prague", "PID_GTFS.zip")
OUT  = os.path.join(ROOT, "data", "prague", "transit.geojson")
TOL  = 120        # m; GTFS shapes are sparse, so a straight run cuts corners

# key: (lines to try, board at, alight at, photo fixes the leg must pass)
LEGS = {
    "mon_tram_out": (["9", "22", "23"], "Lazarská", "Újezd",
                     [(50.08140, 14.41290)]),             # on the Most Legií, 13:17
    "mon_tram_castle": (["22", "23"], "Pohořelec", "Malostranská",
                        [(50.09167, 14.38906),             # Brusnice, 14:47
                         (50.09409, 14.40490),             # Royal Garden, 14:51
                         (50.09270, 14.40660)]),           # Chotkova, 14:53
    "mon_metro_a":  (["A"], "Malostranská", "Muzeum", []),
    "mon_tram_river": (["17", "2"], "Právnická fakulta", "Jiráskovo náměstí",
                       [(50.08512, 14.41370)]),            # the embankment, 18:55
    "mon_metro_b":  (["B"], "Karlovo náměstí", "Náměstí Republiky", []),
    "wed_ae":       (["AE"], "Hlavní nádraží", "Terminál 2",
                     [(50.09465, 14.42691),                # Štefánikův most, 07:26
                      (50.09939, 14.42199),                # Letná, 07:28
                      (50.10071, 14.39607),                # Vítězné náměstí, 07:32
                      (50.09869, 14.36629),                # Evropská, 07:36
                      (50.09268, 14.32468)]),              # Divoká Šárka, 07:41
}

def table(z, name):
    return csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8-sig"))

if not os.path.exists(ZIP):
    print(f"fetching {FEED}")
    urllib.request.urlretrieve(FEED, ZIP)
z = zipfile.ZipFile(ZIP)

lines = {l for v in LEGS.values() for l in v[0]}
route = {r["route_id"]: r["route_short_name"] for r in table(z, "routes.txt")
         if r["route_short_name"] in lines}
trips = {t["trip_id"]: (route[t["route_id"]], t["shape_id"])
         for t in table(z, "trips.txt") if t["route_id"] in route}
stops = {s["stop_id"]: (s["stop_name"], float(s["stop_lat"]), float(s["stop_lon"]))
         for s in table(z, "stops.txt")}
calls = {}
for st in table(z, "stop_times.txt"):         # the big one: stream it, keep ours
    if st["trip_id"] in trips:
        calls.setdefault(st["trip_id"], []).append(
            (int(st["stop_sequence"]), st["stop_id"]))
need = {trips[t][1] for t in calls}
shapes = {}
for p in table(z, "shapes.txt"):
    if p["shape_id"] in need:
        shapes.setdefault(p["shape_id"], []).append(
            (int(p["shape_pt_sequence"]), float(p["shape_pt_lat"]),
             float(p["shape_pt_lon"])))
shapes = {k: [(a, b) for _, a, b in sorted(v)] for k, v in shapes.items()}

def off(line, pt):
    """Distance from pt to the polyline, not just to its nearest vertex."""
    best = float("inf")
    for a, b in zip(line, line[1:]):
        for f in (i / 10 for i in range(11)):
            q = (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
            best = min(best, dist(q, pt))
    return best

features = []
for key, (cands, frm, to, fixes) in LEGS.items():
    done = False
    for line in cands:
        found = Counter()
        for t, cs in calls.items():
            if trips[t][0] != line:
                continue
            cs.sort()
            names = [stops[s][0] for _, s in cs]
            if frm in names and to in names[names.index(frm) + 1:]:
                i = names.index(frm)
                j = names.index(to, i + 1)
                found[(trips[t][1], cs[i][1], cs[j][1])] += 1
        if not found:
            print(f"  {key}: line {line} never runs {frm} -> {to}")
            continue
        (shape, sa, sb), n = found.most_common(1)[0]
        ln = shapes[shape]
        i, di = nearest(ln, stops[sa][1:])
        j, dj = nearest(ln, stops[sb][1:])
        seg = [stops[sa][1:]] + ln[i:j + 1] + [stops[sb][1:]]
        miss = [round(off(seg, f)) for f in fixes]
        if any(m > TOL for m in miss):
            print(f"  {key}: line {line} misses the photographs by {miss} m")
            continue
        print(f"  {key}: line {line}, shape {shape} ({n} trips), "
              f"{len(seg)} pts, photographs within {miss} m")
        features.append({
            "type": "Feature",
            "properties": {"key": key, "line": line, "shape_id": shape,
                           "from": frm, "to": to,
                           "from_pt": [stops[sa][2], stops[sa][1]],
                           "to_pt": [stops[sb][2], stops[sb][1]]},
            "geometry": {"type": "LineString",
                         "coordinates": [[round(b, 6), round(a, 6)] for a, b in seg]}})
        done = True
        break
    if not done:
        raise SystemExit(f"{key}: no line in {cands} fits")

json.dump({"type": "FeatureCollection", "features": features},
          open(OUT, "w"), ensure_ascii=False, indent=1)
print(f"wrote {OUT}")
