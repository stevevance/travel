"""Print the stop list of each candidate relation, to settle which service ran.

Two things have to match: the direction of travel, and the stopping pattern the
day actually had - an Intercity that called at Rotterdam Alexander, and another
that called at Heemstede-Aerdenhout. The name tag says neither.

Two queries, not one per relation: Overpass rate-limits hard enough that a dozen
round trips takes minutes, so the relations come back in one call and every stop
node's name in a second, and the mapping is rebuilt here.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from osm import overpass

CANDIDATES = {
    "R'dam CS -> Gouda": [1323486, 1323492, 5217346, 5224209, 325829, 5254169],
    "Leiden -> A'dam":   [325904, 5218713, 1323511, 5218757, 13543403, 13543404],
    "Gouda -> Alphen":   [325938, 7843400],
    "Alphen -> Leiden":  [4066162, 5280990, 16805491],
    "Zuid -> R'dam CS":  [18413437, 18413425, 18413462],
}
ids = [r for v in CANDIDATES.values() for r in v]
rels = overpass(f'[out:json][timeout:180];relation(id:{",".join(map(str, ids))});'
                f'out body;', "cand_rels.json")["elements"]

members = {}
want = set()
for r in rels:
    stops = [m["ref"] for m in r.get("members", [])
             if m["type"] == "node" and m.get("role", "").startswith("stop")]
    members[r["id"]] = (r.get("tags", {}), stops)
    want.update(stops)

nodes = overpass(f'[out:json][timeout:240];node(id:{",".join(map(str, sorted(want)))});'
                 f'out tags;', "cand_stop_nodes.json")["elements"]
NAME = {n["id"]: n.get("tags", {}).get("name", "?") for n in nodes}

for leg, rids in CANDIDATES.items():
    print(f"\n########## {leg}")
    for rid in rids:
        tags, stops = members[rid]
        print(f"\n  rel {rid}  ref {tags.get('ref','')}  {tags.get('name','')[:64]}")
        print(f"     service={tags.get('service','')} operator={tags.get('operator','')}")
        print("     " + " · ".join(NAME.get(s, "?") for s in stops))
