"""Which parts of the Amsterdam ride were actually over water?

Strava was left running on the NDSM ferry, so part of that recording is a boat,
not a bicycle. Rather than eyeball the shape, test the track against real water
polygons from OpenStreetMap: any run of fixes inside the IJ is a crossing.
"""
import os, sys, math
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from osm import overpass, dist, length_m, ROOT

GPX = os.path.join(ROOT, "data", "alphen-leiden-amsterdam",
                   "Bike_ride_about_Amsterdam_with_a_fellow_Chicagoan.gpx")
NS = "{http://www.topografix.com/GPX/1/1}"
TZ = timedelta(hours=2)          # Strava stamps UTC; Amsterdam was on CEST

root = ET.parse(GPX).getroot()
P = [(float(p.get("lat")), float(p.get("lon")),
      datetime.strptime(p.findtext(NS + "time"), "%Y-%m-%dT%H:%M:%SZ") + TZ)
     for p in root.iter(NS + "trkpt")]

q = """[out:json][timeout:240];
(way[natural=water](52.36,4.83,52.42,4.95);
 relation[natural=water](52.36,4.83,52.42,4.95););
out geom;"""
elements = overpass(q, "water.json")["elements"]

rings = []
for e in elements:
    if e["type"] == "way" and "geometry" in e:
        rings.append(([(p["lat"], p["lon"]) for p in e["geometry"]],
                      e.get("tags", {}).get("name", "")))
    elif e["type"] == "relation":
        for m in e.get("members", []):
            if m.get("role") == "outer" and "geometry" in m:
                rings.append(([(p["lat"], p["lon"]) for p in m["geometry"]],
                              e.get("tags", {}).get("name", "")))
print(f"{len(rings)} water rings in the bbox")

def inside(pt, ring):
    """Even-odd ray cast. Rings come back closed from Overpass."""
    y, x = pt
    n, c = len(ring), False
    for i in range(n):
        y1, x1 = ring[i]
        y2, x2 = ring[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xi = x1 + (y - y1) / (y2 - y1) * (x2 - x1)
            if x < xi:
                c = not c
    return c

# Only rings whose bbox could contain a fix are worth testing point by point.
boxes = []
for ring, name in rings:
    la = [p[0] for p in ring]; lo = [p[1] for p in ring]
    boxes.append((min(la), max(la), min(lo), max(lo), ring, name))

wet = []
for i, (la, lo, t) in enumerate(P):
    hit = ""
    for mla, xla, mlo, xlo, ring, name in boxes:
        if mla <= la <= xla and mlo <= lo <= xlo and inside((la, lo), ring):
            hit = name or "(unnamed water)"
            break
    wet.append(hit)

# Group consecutive wet fixes into crossings, tolerating a few dry outliers
# where the GPS wandered onto a quay polygon edge.
runs, i = [], 0
while i < len(P):
    if wet[i]:
        j = i
        gap = 0
        while j + 1 < len(P) and gap < 15:
            j += 1
            gap = gap + 1 if not wet[j] else 0
        while j > i and not wet[j]:
            j -= 1
        runs.append((i, j))
        i = j + 1
    else:
        i += 1

print("\nruns of fixes over water (>=30 s and >=150 m):")
for a, b in runs:
    secs = (P[b][2] - P[a][2]).total_seconds()
    m = length_m([(p[0], p[1]) for p in P[a:b + 1]])
    if secs < 30 or m < 150:
        continue
    names = {n for n in wet[a:b + 1] if n}
    print(f"  idx {a:6d}-{b:6d}  {P[a][2].time()}-{P[b][2].time()}  "
          f"{secs/60:5.1f} min  {m/1000:5.2f} km  {m/secs*3.6:5.1f} km/h avg")
    print(f"      {P[a][0]:.5f},{P[a][1]:.5f} -> {P[b][0]:.5f},{P[b][1]:.5f}   {sorted(names)}")
