"""Export the route legs and stops as GeoJSON for the MapLibre map."""
import json
from mapkit import LEGS, leg_points, ORDER, NUM, NAME, ARRIVE, NOTES
from routes import STOPS

LINE_LABEL = {"E": "Metro E", "9": "Tram 9", "1": "Tram 1",
              "8": "Tram 8", "IC": "Intercity"}

import math
def length_m(pts):
    """Great-circle length of a lat/lon point list, in metres."""
    tot = 0.0
    for i in range(len(pts) - 1):
        (la1, lo1), (la2, lo2) = pts[i], pts[i + 1]
        dy = (la2 - la1) * 111320.0
        dx = (lo2 - lo1) * 111320.0 * math.cos(math.radians((la1 + la2) / 2))
        tot += math.hypot(dx, dy)
    return tot

features = []
for i, leg in enumerate(LEGS):
    mode, badge, rid, a, b = leg
    pts = leg_points(leg)
    features.append({
        "type": "Feature",
        "properties": {
            "leg": i + 1,
            "mode": mode,
            "badge": badge or "walk",
            "line": LINE_LABEL.get(badge, "Walk"),
            "from": NAME[a],
            "to": NAME[b],
            "from_n": NUM[a],
            "to_n": NUM[b],
            "km": round(length_m(pts) / 1000, 2),
        },
        # GeoJSON is lon,lat; our stop tuples are lat,lon
        "geometry": {"type": "LineString",
                     "coordinates": [[round(p[1], 6), round(p[0], 6)] for p in pts]},
    })

stops = []
for key, name in ORDER:
    lat, lon = STOPS[key]
    stops.append({
        "type": "Feature",
        "properties": {"n": NUM[key], "name": name, "arrive": ARRIVE[key],
               "key": key, "note": NOTES.get(key, "")},
        "geometry": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]},
    })

# Stop-to-platform access walks, drawn dashed like any other walking
for a in json.load(open("access.json")):
    features.append({
        "type": "Feature",
        "properties": {"leg": 0, "mode": "walk", "badge": "access",
                       "line": "Walk to stop", "from": NAME[a["stop"]],
                       "to": "platform", "from_n": NUM[a["stop"]],
                       "to_n": NUM[a["stop"]], "km": round(a["m"] / 1000, 2),
                       "access": 1},
        "geometry": {"type": "LineString",
                     "coordinates": [[p[1], p[0]] for p in a["pts"]]},
    })

json.dump({"type": "FeatureCollection", "features": features},
          open("route_lines.geojson", "w"))
json.dump({"type": "FeatureCollection", "features": stops},
          open("route_stops.geojson", "w"))

tot = sum(len(f["geometry"]["coordinates"]) for f in features)
print(f"{len(features)} legs, {tot} coordinates, {len(stops)} stops")
for f in features:
    p = f["properties"]
    print(f"  {p['leg']:2d}. {p['line']:9s} {p['from']:22s} -> {p['to']:22s} "
          f"{len(f['geometry']['coordinates']):5d} pts")
