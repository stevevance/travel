"""Name the two IJ crossings by snapping them to GVB's ferry routes in OSM."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from osm import overpass, stitch, nearest, dist

q = """[out:json][timeout:240];
relation[route=ferry](52.36,4.85,52.42,4.93);
out geom;"""
rels = overpass(q, "ferry_routes.json")["elements"]
print(f"{len(rels)} ferry relations near the IJ\n")

CROSS = {
    "outbound 17:10-17:23": ((52.38084, 4.89922), (52.40114, 4.89140)),
    "return   18:34-18:41": ((52.38219, 4.90322), (52.38062, 4.89967)),
}
for label, (a, b) in CROSS.items():
    print(label)
    best = []
    for r in rels:
        line = stitch(r)
        if not line:
            continue
        _, da = nearest(line, a)
        _, db = nearest(line, b)
        best.append((max(da, db), r["id"], r.get("tags", {}), len(line)))
    for worst, rid, tags, n in sorted(best, key=lambda x: x[0])[:3]:
        print(f"   {worst:7.0f} m worst-end  rel {rid:<10d} {tags.get('ref',''):>6s}  "
              f"{tags.get('name','')[:60]}  ({tags.get('operator','')})")
    print()
