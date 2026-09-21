"""What the Alphen walk actually passed: the station bike garage and the bridge.

The walk has no GPS trace, only photographs. Their coordinates say where it went;
these queries say what is there, so the note can name the bridge and the water
it crosses rather than describing a turn.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from osm import overpass

q = """[out:json][timeout:180];
(way[man_made=bridge](around:220,52.134803,4.663133);
 way[bridge][highway](around:220,52.134803,4.663133);
 way[waterway=canal](around:300,52.134803,4.663133);
 way[waterway=river](around:300,52.134803,4.663133);
 way[amenity=bicycle_parking](around:260,52.124806,4.657105);
 node[amenity=bicycle_parking](around:260,52.124806,4.657105);
 way[waterway](around:200,52.128942,4.661678););
out center tags;"""
for e in overpass(q, "alphen_places.json")["elements"]:
    t = e.get("tags", {})
    lat = e.get("lat") or e.get("center", {}).get("lat")
    lon = e.get("lon") or e.get("center", {}).get("lon")
    kind = (t.get("man_made") or t.get("amenity") or t.get("waterway")
            or t.get("highway") or "?")
    print(f"{kind:18s} {str(lat)[:9]:9s},{str(lon)[:8]:8s}  name={t.get('name','')!r:38s} "
          f"ref={t.get('ref','')} bridge={t.get('bridge','')} "
          f"capacity={t.get('capacity','')} covered={t.get('covered','')}")
