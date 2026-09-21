"""Find the OSM route relations that carry each leg of the day.

A relation is a candidate for a leg only if it passes close to BOTH ends of it,
so the query is one cheap tags-only fetch per station and an intersection here.
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from osm import overpass

ST = {
    "rotterdam_cs":  (51.925057, 4.469229),
    "alexander":     (51.951716, 4.552483),
    "gouda":         (52.017424, 4.706164),
    "alphen":        (52.124806, 4.657105),
    "leiden_cs":     (52.166319, 4.482286),
    "heemstede":     (52.359505, 4.606786),
    "haarlem":       (52.388078, 4.638579),
    "sloterdijk":    (52.389032, 4.838106),
    "zuid":          (52.338807, 4.873191),
}
MODES = "train|light_rail|subway"

def near(key):
    lat, lon = ST[key]
    q = (f'[out:json][timeout:120];'
         f'relation[route~"^({MODES})$"](around:400,{lat},{lon});out tags;')
    els = overpass(q, f"rel_{key}.json")["elements"]
    time.sleep(1.0)
    return {e["id"]: e.get("tags", {}) for e in els}

CACHE = {k: near(k) for k in ST}
for k, v in CACHE.items():
    print(f"{k:14s} {len(v):3d} relations")

LEGS = [("rotterdam_cs", "gouda"), ("gouda", "alphen"), ("alphen", "leiden_cs"),
        ("leiden_cs", "sloterdijk"), ("sloterdijk", "zuid"), ("zuid", "rotterdam_cs")]
for a, b in LEGS:
    both = set(CACHE[a]) & set(CACHE[b])
    print(f"\n=== {a} -> {b}: {len(both)} relations touch both ===")
    for rid in sorted(both):
        t = CACHE[a][rid]
        print(f"  rel {rid:<11d} {t.get('route',''):10s} {t.get('ref',''):>6s} "
              f"{t.get('name','')[:70]}")
