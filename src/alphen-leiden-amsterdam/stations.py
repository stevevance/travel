"""Station and metro-stop coordinates, straight from OSM rather than guessed."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from osm import overpass

WANT = ["Rotterdam Centraal", "Rotterdam Alexander", "Gouda",
        "Alphen aan den Rijn", "Leiden Centraal", "Heemstede-Aerdenhout",
        "Haarlem", "Amsterdam Sloterdijk", "Amsterdam Zuid"]
# Filtered by name in the query rather than scanned out of a bbox: the whole
# Randstad's stations time Overpass out at 504.
NAMES = "|".join(WANT).replace(" ", "[ ]")
q = f"""[out:json][timeout:180];
(node[railway~"^(station|halt)$"]["name"~"^({NAMES})$"](51.88,4.20,52.45,4.95);
 way[railway~"^(station|halt)$"]["name"~"^({NAMES})$"](51.88,4.20,52.45,4.95););
out center tags;"""
els = overpass(q, "stations.json")["elements"]
for w in WANT:
    hits = [e for e in els if e.get("tags", {}).get("name", "") == w]
    for e in hits:
        lat = e.get("lat") or e["center"]["lat"]
        lon = e.get("lon") or e["center"]["lon"]
        t = e["tags"]
        print(f"{w:22s} {lat:.6f}, {lon:.6f}   {e['type']}/{e['id']}  "
              f"railway={t.get('railway')} {t.get('network','')[:30]}")
    if not hits:
        print(f"{w:22s} NOT FOUND")
