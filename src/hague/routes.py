"""
Assemble Overpass route relations into single ordered polylines, then slice each
polyline down to the segment actually traveled.
"""
import json, math

def load(fn):
    return {e["id"]: e for e in json.load(open(fn))["elements"]}

def stitch(rel):
    """
    Walk the relation's way members in order, flipping any way whose endpoints
    run against the direction of travel, and concatenate into one point list.
    Public-transport v2 relations list stops first (with roles) and the track
    ways last with an empty role, so only empty-role ways are track geometry.
    """
    ways = [m["geometry"] for m in rel.get("members", [])
            if m["type"] == "way" and m.get("role", "") == "" and "geometry" in m]
    if not ways:
        return []
    line = [(p["lat"], p["lon"]) for p in ways[0]]
    for w in ways[1:]:
        pts = [(p["lat"], p["lon"]) for p in w]
        # Pick the orientation whose first point is closest to where we left off
        if dist(line[-1], pts[-1]) < dist(line[-1], pts[0]):
            pts.reverse()
        line.extend(pts)
    return line

def dist(a, b):
    """Rough planar metres; fine at this latitude for nearest-point work."""
    dy = (a[0] - b[0]) * 111320.0
    dx = (a[1] - b[1]) * 111320.0 * math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)

def nearest_index(line, pt):
    best, bi = float("inf"), 0
    for i, p in enumerate(line):
        d = dist(p, pt)
        if d < best:
            best, bi = d, i
    return bi, best

def slice_line(line, origin, dest):
    """Cut the polyline between the points nearest the origin and destination."""
    i, di = nearest_index(line, origin)
    j, dj = nearest_index(line, dest)
    seg = line[i:j + 1] if i <= j else list(reversed(line[j:i + 1]))
    return seg, di, dj

STOPS = {
    "meijersplein":   (51.95585, 4.46268),
    "denhaag_cs":     (52.08084, 4.32455),
    "bierkade":       (52.07452, 4.31820),
    "kerkplein":      (52.07772, 4.30693),
    "ov_museum":      (52.06223, 4.30914),
    "kurhaus":        (52.113270, 4.283670),  # tram stop, not the hotel
    "summertime":     (52.113440, 4.280050),
    "malieveld":      (52.083630, 4.317370),  # tram stop, mean of both platforms
    "koekamp":        (52.083910, 4.322400),
    "binnenhof":      (52.079330, 4.312370),
    "grote_markt":    (52.07548, 4.30912),
    "prinsenhof":     (52.011725, 4.353380),  # tram 1 stop, not the museum
    "lakila":         (52.01287, 4.36099),
    "delft_station":  (52.007550, 4.356580),  # the station itself
    "rotterdam_cs":   (51.92502, 4.46893),
    "wilgenlei":      (51.95519, 4.47279),
}

if __name__ == "__main__":
    rels = load("routes_geom.json")
    rels.update(load("train_geom.json"))
    lines = {rid: stitch(r) for rid, r in rels.items()}
    for rid, ln in lines.items():
        print(rid, rels[rid]["tags"].get("name", "")[:45], "->", len(ln), "pts")

    # Which line actually serves the transport museum: tram 1 or tram 9?
    print("\nDistance from OV Museum to each line:")
    for rid in (1862707, 153659, 1923134):
        _, d = nearest_index(lines[rid], STOPS["ov_museum"])
        print(f"  {rels[rid]['tags'].get('name','')[:45]:48s} {d:7.0f} m")

    print("\nDistance from Kerkplein to each line:")
    for rid in (1862707, 153659, 1923134):
        _, d = nearest_index(lines[rid], STOPS["kerkplein"])
        print(f"  {rels[rid]['tags'].get('name','')[:45]:48s} {d:7.0f} m")

    print("\nSnap quality for key endpoints:")
    for rid, name, pts in [
        (2777287, "Metro E",  ["meijersplein", "denhaag_cs"]),
        (153659,  "Tram 9 S", ["denhaag_cs", "bierkade", "kurhaus", "malieveld"]),
        (1923134, "Tram 9 N", ["ov_museum", "kurhaus"]),
        (1862707, "Tram 1 S", ["grote_markt", "prinsenhof", "kerkplein", "ov_museum"]),
        (3009652, "Tram 8",   ["rotterdam_cs", "wilgenlei"]),
        (325507,  "NS train", ["delft_station", "rotterdam_cs"]),
    ]:
        for p in pts:
            _, d = nearest_index(lines[rid], STOPS[p])
            print(f"  {name:10s} {p:16s} {d:7.0f} m")
