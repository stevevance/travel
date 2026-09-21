"""Build the day of trains: Rotterdam out to Alphen, Leiden and Amsterdam, and back.

Six rail legs, one metro, two ferries, three bicycle rides and two walks. It is
the most mixed day in this set, and the only one where a single Strava recording
holds more than one mode: the Amsterdam ride has two IJ crossings in it, because
the watch was left running on the GVB ferry both ways.

Where each line comes from:

  gps      the three Strava recordings in data/alphen-leiden-amsterdam/, and the
           two ferry crossings cut out of the middle one
  osm      the six rail and metro legs, sliced out of route relations
  routed   the Alphen and Leiden walks, which have no recording at all - their
           shape comes from the day's photographs and Valhalla's pedestrian
           router, and is drawn dashed so it cannot pass for a measurement

    python3 src/alphen-leiden-amsterdam/photo_walks.py   # once, needs Photos
    python3 src/alphen-leiden-amsterdam/build.py         # -> the page

Both Rotterdam rides were recorded from the door, so every fix within 100 m of
home is dropped before anything is drawn; see PRIVATE below.
"""
import json, math, os, sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from osm import HERE, ROOT, overpass, stitch, nearest, dist, length_m, valhalla

sys.setrecursionlimit(10000)          # rdp recurses once per retained point

DATADIR = os.path.join(ROOT, "data", "alphen-leiden-amsterdam")
PRIVATE = os.path.join(DATADIR, "private.json")
WALKS   = os.path.join(HERE, "walks.geojson")
OUT     = os.path.join(ROOT, "alphen-leiden-amsterdam-map.html")
CEST    = timezone(timedelta(hours=2))    # Strava stamps UTC; the day was CEST
RDP_M   = 1.5                             # a 1 s trace is finer than any map needs

# ------------------------------------------------------------------ stops ---
# Every one of these is a public place: a station, a tram stop, a ferry terminal,
# a road bridge, a cafe. The house the day starts from is not among them, and is
# not in this repository at all.
STOPS = {
    "wilgenlei":    (51.955190, 4.472790),   # tram stop, Schiebroek
    "rotterdam_cs": (51.925057, 4.469229),
    "gouda":        (52.017424, 4.706164),
    "alphen":       (52.124806, 4.657105),
    "julianabrug":  (52.134870, 4.662759),   # where the east steps meet the deck
    "leiden_cs":    (52.166319, 4.482286),
    "chummy":       (52.158400, 4.489866),   # Chummy Coffee, Breestraat 97
    "sloterdijk":   (52.389032, 4.838106),
    # On the ride, level with the middle of the park: the track runs beside the
    # Vondelpark for a quarter of an hour and never goes into it.
    "vondelpark":   (52.356366, 4.866333),
    "ijveer_cs":    (52.380601, 4.899695),   # GVB terminal behind Centraal
    "ndsm":         (52.401010, 4.891213),
    "ijver":        (52.401374, 4.895123),   # IJver, Scheepsbouwkade 72
    "buiksloterweg":(52.382146, 4.903173),
    "zuid":         (52.338807, 4.873191),
}
ORDER = [
    ("wilgenlei",     "Wilgenlei, Schiebroek"),
    ("rotterdam_cs",  "Rotterdam Centraal"),
    ("gouda",         "Gouda"),
    ("alphen",        "Alphen aan den Rijn"),
    ("julianabrug",   "Koningin Julianabrug"),
    ("leiden_cs",     "Leiden Centraal"),
    ("chummy",        "Chummy Coffee"),
    ("sloterdijk",    "Amsterdam Sloterdijk"),
    ("vondelpark",    "Vondelpark"),
    ("ijveer_cs",     "Amsterdam Centraal, the IJ ferries"),
    ("ndsm",          "NDSM pier"),
    ("ijver",         "IJver"),
    ("buiksloterweg", "Buiksloterweg"),
    ("zuid",          "Amsterdam Zuid"),
]
NUM  = {k: i + 1 for i, (k, _) in enumerate(ORDER)}
NAME = dict(ORDER)
NOTES = {
    "wilgenlei":    "The day starts and ends on this corner. Both rides were "
                    "recorded from the door; the first and last 100 m are cut",
    "rotterdam_cs": "Reached by bike at 12:48, and left from again at 20:35 "
                    "after the Intercity Direct got in",
    "gouda":        "A platform change only, 13:23 to about 13:32",
    "alphen":       "De Fietsappel stands outside the station - 970 covered "
                    "bicycle spaces stacked in a ramped drum. Then a walk east "
                    "along Stationsweg into the Lage Zijde",
    "julianabrug":  "The far end of the Alphen walk: a movable bridge carrying "
                    "Willem de Zwijgerlaan over the Oude Rijn. Crossed west, "
                    "then back south through the Hoge Zijde",
    "leiden_cs":    "Out into the old center at 14:38, back on a train at 15:33",
    "chummy":       "Breestraat 97, about 15:03 to 15:16",
    "sloterdijk":   "Off the Intercity at about 16:08, on the bike six minutes "
                    "later; back here at 19:05 for the metro",
    "vondelpark":   "Round the park and along its south side, 16:32 to 16:47, "
                    "on the way out to the Zuidas",
    "ijveer_cs":    "The GVB ferry slips on the De Ruijterkade, behind Centraal. "
                    "Used twice - out to NDSM at 17:10, and back from "
                    "Buiksloterweg at 18:41",
    "ndsm":         "Across the IJ, 13 minutes on the water",
    "ijver":        "A beer and a snack on the Scheepsbouwkade. Fifty-seven "
                    "minutes, 17:25 to 18:21 - the ride stands still longer "
                    "here than anywhere else",
    "buiksloterweg":"The short crossing back, seven minutes including the wait "
                    "on the slip",
    "zuid":         "Metro 50 in at 19:29, Intercity Direct out at about 19:39",
}
# Which mode reached each place: this rings the dot on the map and the number in
# the key, so the two cannot disagree. Wilgenlei and Rotterdam Centraal are the
# ambiguous ones - each was reached twice - and both take the bicycle, which is
# how the day both left and returned to them.
ARRIVE = {
    "wilgenlei": "bike",    "rotterdam_cs": "bike",  "gouda": "train",
    "alphen": "train",      "julianabrug": "walk",   "leiden_cs": "train",
    "chummy": "walk",       "sloterdijk": "train",   "vondelpark": "bike",
    "ijveer_cs": "bike",
    "ndsm": "ferry",        "ijver": "bike",         "buiksloterweg": "bike",
    "zuid": "metro",
}

# ------------------------------------------------------------------- rail ---
# (seq, relation, from, to, mode, label, note). Direction matters: each of these
# is the relation for the way the train was actually going.
#
# `seq` is where the leg falls in the day. The legs are computed in the order
# that is cheapest - all the rail together, then the walks, then the recordings -
# but the key on the page is built by walking the feature list, so the file has
# to come out in the order the day happened or the list reads Gouda, Amsterdam,
# then back to a bridge in Alphen. Sorted once, at the end.
#
# Three of the six services share their track with others that run the same
# stopping pattern, so the relation is chosen for its geometry and the label
# says the service, not the series number. The two that are unambiguous:
# Alphen-Leiden is the 8900 Sprinter, and Amsterdam Zuid-Rotterdam is the
# 12400 Intercity Direct over the HSL.
RAIL = [
    (20, 1323486,  "rotterdam_cs", "gouda",      "train", "Intercity",
     "Intercity to Utrecht, calling at Rotterdam Alexander"),
    (30, 325938,   "gouda",        "alphen",     "train", "Sprinter",
     "The Gouwelijn: Waddinxveen, Boskoop and the Gouwe"),
    (60, 4066162,  "alphen",       "leiden_cs",  "train", "Sprinter",
     "Sprinter 8900, by Leiden Lammenschans"),
    (90, 5218713,  "leiden_cs",    "sloterdijk", "train", "Intercity",
     "Intercity by the old coastal line, calling at Heemstede-Aerdenhout "
     "and Haarlem - not the Schiphol route"),
    (150, 4515354, "sloterdijk",   "zuid",       "metro", "Metro 50",
     "The Ringlijn, round the west and south of the city"),
    (160, 18413437, "zuid",        "rotterdam_cs", "train", "Intercity Direct",
     "Intercity Direct down the HSL, by Schiphol"),
]

# ----------------------------------------------------------------- tunnel ---
# Both Rotterdam rides pass under the station through the Provenierstunnel, and
# a bicycle in a tunnel is a receiver with no sky: the morning trace teleports at
# 136 km/h and the evening one at 194 km/h, with a 14 and a 17 second hole in the
# middle, and what draws is a zigzag across the platforms rather than a line.
# The fixes on either side of the hole are good - both rides come within 15 m of
# a portal - so the blackout is replaced with the tunnel's own OSM geometry.
# This is the one place on the page where a `gps` leg is not entirely recorded,
# which is why the leg says so in its note and the caveat repeats it.
TUNNEL = {"way": 236247086, "name": "Provenierstunnel",
          "rides": ("morning", "evening"), "max_join": 40.0}

# -------------------------------------------------------------------- gps ---
RIDES = [
    {"seq": 10, "file": "Apartment_to_central_station.gpx", "key": "morning",
     "from": "wilgenlei", "to": "rotterdam_cs", "clip": "start",
     "note": "South through Schiebroek and Blijdorp to the station"},
    {"seq": 100, "file": "Bike_ride_about_Amsterdam_with_a_fellow_Chicagoan.gpx",
     "key": "amsterdam", "from": "sloterdijk", "to": "sloterdijk", "clip": None,
     "tail_R": 60.0,
     "note": "Round Amsterdam with a fellow Chicagoan, and twice over the IJ"},
    {"seq": 170, "file": "Last_ride_from_Rotterdam_Centraal_for_awhile.gpx",
     "key": "evening",
     "from": "rotterdam_cs", "to": "wilgenlei", "clip": "end",
     "note": "The same way back north, in the dark"},
]

# --------------------------------------------------------------- geometry ---
def read_gpx(path):
    # The traces are gitignored - they are finer than anything published and
    # this repo is public - so a fresh clone will not have them. Say so plainly.
    if not os.path.exists(path):
        raise SystemExit(
            f"missing {path}\n"
            "The Strava exports are deliberately not in git. Drop the three "
            "2026-09-20 .gpx files back into data/alphen-leiden-amsterdam/ "
            "to rebuild; see the notes file in that directory.")
    NS = "{http://www.topografix.com/GPX/1/1}"
    root = ET.parse(path).getroot()
    return [(float(p.get("lat")), float(p.get("lon")),
             datetime.strptime(p.findtext(NS + "time"), "%Y-%m-%dT%H:%M:%SZ")
             .replace(tzinfo=timezone.utc).astimezone(CEST))
            for p in root.iter(NS + "trkpt")]

def trim_loitering(pts, R=20.0, tail_R=None):
    """Drop the standing-around at each end of a recording.

    Strava was started before the bike moved and stopped after it had, so each
    trace opens and closes with a minute of sub-meter jitter that draws as a
    blot. Keep from the last fix still within R of the first, to the first fix
    already within R of the tail.

    The two ends can need different radii. Twenty meters catches a stationary
    start, but the Amsterdam ride finishes by wheeling the bicycle around the
    forecourt at Sloterdijk for over two minutes, covering fifty meters without
    going anywhere - a flailing knot on the map that twenty meters leaves
    entirely alone.
    """
    tail_R = R if tail_R is None else tail_R
    i = 0
    for k in range(len(pts)):
        if dist(pts[0][:2], pts[k][:2]) < R:
            i = k
    j = len(pts) - 1
    for k in range(len(pts) - 1, -1, -1):
        if dist(pts[-1][:2], pts[k][:2]) < tail_R:
            j = k
    return pts[i:j + 1]

def clip_home(pts, home, radius, which):
    """Cut the end of a ride that runs to the door.

    Not a trim for tidiness: the repository's rule is that a line ends at a
    public corner and never at a residence, and these two recordings start and
    finish inside the house. Every fix within `radius` of it goes.
    """
    keep = [i for i, p in enumerate(pts) if dist(p[:2], home) >= radius]
    if not keep:
        raise SystemExit("the whole ride is inside the privacy radius")
    cut = keep[0] if which == "start" else len(pts) - 1 - keep[-1]
    seg = pts[keep[0]:] if which == "start" else pts[:keep[-1] + 1]
    print(f"    clipped {cut} fixes at the {which} "
          f"({length_m([p[:2] for p in pts]) - length_m([p[:2] for p in seg]):.0f} m) "
          f"inside the {radius:.0f} m privacy radius")
    return seg

def rdp(pts, eps):
    """Ramer-Douglas-Peucker on (lat, lon, time) fixes, keeping the times."""
    if len(pts) < 3:
        return list(pts)
    a, b = pts[0], pts[-1]
    ab = dist(a[:2], b[:2])
    far, fi = -1.0, 0
    for i in range(1, len(pts) - 1):
        p = pts[i]
        if ab == 0:
            d = dist(p[:2], a[:2])
        else:
            ay = (a[0]-p[0])*111320.0; ax = (a[1]-p[1])*111320.0*math.cos(math.radians(p[0]))
            by = (b[0]-p[0])*111320.0; bx = (b[1]-p[1])*111320.0*math.cos(math.radians(p[0]))
            d = abs(ax*by - ay*bx) / ab
        if d > far:
            far, fi = d, i
    if far <= eps:
        return [a, b]
    return rdp(pts[:fi + 1], eps)[:-1] + rdp(pts[fi:], eps)

def splice_tunnel(pts, tunnel, label):
    """Swap the blacked-out fixes under the station for the tunnel itself.

    The two portals are the anchors: the fix nearest each one is where the
    recording was last trustworthy, and everything between them is replaced by
    the OSM way, laid in the direction of travel. If either portal is further
    than `max_join` from any fix the ride did not use this tunnel and the track
    is left alone - better a messy line than a confidently wrong one.
    """
    a, b = tunnel["line"][0], tunnel["line"][-1]
    ia, da = min(((i, dist(p[:2], a)) for i, p in enumerate(pts)), key=lambda x: x[1])
    ib, db = min(((i, dist(p[:2], b)) for i, p in enumerate(pts)), key=lambda x: x[1])
    if max(da, db) > tunnel["max_join"]:
        print(f"    {label}: no {tunnel['name']} portal within "
              f"{tunnel['max_join']:.0f} m ({da:.0f} m / {db:.0f} m); left as recorded")
        return pts
    line = tunnel["line"] if ia <= ib else list(reversed(tunnel["line"]))
    i, j = min(ia, ib), max(ia, ib)
    dropped = pts[i:j + 1]
    out = pts[:i] + [(la, lo, None) for la, lo in line] + pts[j + 1:]
    print(f"    {label}: {j - i + 1} fixes under the {tunnel['name']} "
          f"({length_m([p[:2] for p in dropped]):.0f} m of wander, "
          f"{(dropped[-1][2] - dropped[0][2]).total_seconds():.0f} s) replaced by "
          f"{len(line)} points of OSM way {tunnel['way']}; "
          f"joins {da:.0f} m / {db:.0f} m")
    return out

# ------------------------------------------------------------ the ferries ---
def water_rings():
    """Every water polygon around the IJ, as closed rings."""
    q = """[out:json][timeout:240];
(way[natural=water](52.36,4.83,52.42,4.95);
 relation[natural=water](52.36,4.83,52.42,4.95););
out geom;"""
    rings = []
    for e in overpass(q, "water.json")["elements"]:
        if e["type"] == "way" and "geometry" in e:
            rings.append([(p["lat"], p["lon"]) for p in e["geometry"]])
        elif e["type"] == "relation":
            for m in e.get("members", []):
                if m.get("role") == "outer" and "geometry" in m:
                    rings.append([(p["lat"], p["lon"]) for p in m["geometry"]])
    return [(min(p[0] for p in r), max(p[0] for p in r),
             min(p[1] for p in r), max(p[1] for p in r), r) for r in rings]

def in_water(pt, boxes):
    """Even-odd ray cast against the rings whose bbox could hold the point."""
    y, x = pt
    for mla, xla, mlo, xlo, ring in boxes:
        if not (mla <= y <= xla and mlo <= x <= xlo):
            continue
        c, n = False, len(ring)
        for i in range(n):
            y1, x1 = ring[i]
            y2, x2 = ring[(i + 1) % n]
            if (y1 > y) != (y2 > y):
                if x < x1 + (y - y1) / (y2 - y1) * (x2 - x1):
                    c = not c
        if c:
            return True
    return False

def ferry_runs(pts, boxes, min_s=30, min_m=150):
    """Runs of fixes out on the water: the crossings Strava recorded as cycling.

    Found by testing the track against real water polygons rather than by
    looking at the shape, because the ride crosses the IJ twice and crosses
    canals on bridges a dozen more times. A few dry fixes are tolerated inside a
    run - the GPS wanders onto a quay polygon's edge - and a candidate has to be
    both long enough and slow enough to be a boat rather than a bridge.
    """
    wet = [in_water(p[:2], boxes) for p in pts]
    runs, i = [], 0
    while i < len(pts):
        if wet[i]:
            j, gap = i, 0
            while j + 1 < len(pts) and gap < 15:
                j += 1
                gap = gap + 1 if not wet[j] else 0
            while j > i and not wet[j]:
                j -= 1
            secs = (pts[j][2] - pts[i][2]).total_seconds()
            if secs >= min_s and dist(pts[i][:2], pts[j][:2]) >= min_m:
                runs.append((i, j))
            i = j + 1
        else:
            i += 1
    return runs

# ---------------------------------------------------------------- collect ---
if not os.path.exists(PRIVATE):
    raise SystemExit(
        f"missing {PRIVATE}\n"
        "It holds the point the two Rotterdam rides are clipped around, and is "
        "gitignored on purpose. Write {\"home\": [lat, lon], \"radius_m\": 100}.")
priv   = json.load(open(PRIVATE))
HOME   = tuple(priv["home"])
RADIUS = float(priv["radius_m"])

TUNNEL["line"] = [(p["lat"], p["lon"]) for p in overpass(
    f"[out:json][timeout:120];way({TUNNEL['way']});out geom;",
    f"way_{TUNNEL['way']}.json")["elements"][0]["geometry"]]

features = []
def add(seq, mode, a, b, pts, source, line, note, ride=None, km=None):
    features.append({
        "type": "Feature",
        "seq": seq,
        "properties": {
            "mode": mode, "from": NAME[a], "to": NAME[b],
            "from_n": NUM[a], "to_n": NUM[b], "line": line,
            "km": round((km if km is not None else length_m([p[:2] for p in pts])) / 1000, 2),
            "source": source, "note": note, **({"ride": ride} if ride else {}),
        },
        "geometry": {"type": "LineString",
                     "coordinates": [[round(p[1], 6), round(p[0], 6)] for p in pts]},
    })
    p = features[-1]["properties"]
    print(f"  {mode:6s} {NAME[a][:22]:24s} -> {NAME[b][:22]:24s} "
          f"{p['km']:6.2f} km  {len(pts):5d} pts  [{source}]")

print("rail and metro geometry")
for seq, rid, a, b, mode, line, note in RAIL:
    rel = overpass(f"[out:json][timeout:120];rel({rid});out geom;",
                   f"rel_geom_{rid}.json")["elements"][0]
    ln = stitch(rel)
    i, di = nearest(ln, STOPS[a])
    j, dj = nearest(ln, STOPS[b])
    seg = ln[i:j + 1] if i <= j else list(reversed(ln[j:i + 1]))
    print(f"  rel {rid:<9d} {line:17s} snaps {di:5.0f} m / {dj:5.0f} m")
    if max(di, dj) > 250:
        raise SystemExit(f"rel {rid} does not reach {a}->{b}; wrong relation?")
    add(seq, mode, a, b, [(p[0], p[1], None) for p in seg], "osm", line, note)

print("\nthe walks, reconstructed from the day's photographs")
walks = json.load(open(WALKS))
WALK_LEG = {("alphen", "out"):  (40, "alphen", "julianabrug"),
            ("alphen", "back"): (50, "julianabrug", "alphen"),
            ("leiden", "out"):  (70, "leiden_cs", "chummy"),
            ("leiden", "back"): (80, "chummy", "leiden_cs")}
for f in walks["features"]:
    p = f["properties"]
    seq, a, b = WALK_LEG[(p["city"], p["half"])]
    pts = [(c[1], c[0], None) for c in f["geometry"]["coordinates"]]
    add(seq, "walk", a, b, pts, "routed", "Walk",
        f"{p['from_t']} to {p['to_t']}, through {p['waypoints']} places the "
        f"photographs put us", km=p["km"] * 1000)

print("\nthe recordings")
boxes = None
for r in RIDES:
    raw = read_gpx(os.path.join(DATADIR, r["file"]))
    pts = trim_loitering(raw, tail_R=r.get("tail_R"))
    print(f"  {r['file']}")
    print(f"    {len(raw)} fixes, {pts[0][2]:%H:%M}-{pts[-1][2]:%H:%M}, "
          f"{length_m([p[:2] for p in raw])/1000:.2f} km recorded")
    if r["clip"]:
        pts = clip_home(pts, HOME, RADIUS, r["clip"])
    if r["key"] in TUNNEL["rides"]:
        pts = splice_tunnel(pts, TUNNEL, r["key"])

    if r["key"] != "amsterdam":
        simple = rdp(pts, RDP_M)
        add(r["seq"], "bike", r["from"], r["to"], simple, "gps", "By bicycle",
            f"{pts[0][2]:%H:%M} to {pts[-1][2]:%H:%M}. {r['note']}, and under the "
            f"station through the {TUNNEL['name']}, where the recording is the "
            f"tunnel's own line rather than the lost fixes",
            ride=r["key"])
        continue

    # The Amsterdam recording is one file and five legs: bicycle, ferry,
    # bicycle, ferry, bicycle. Strava was left running on both boats.
    boxes = water_rings()
    runs = ferry_runs(pts, boxes)
    print(f"    {len(runs)} runs of fixes out on the open IJ:")
    for i, j in runs:
        secs = (pts[j][2] - pts[i][2]).total_seconds()
        print(f"      {pts[i][2]:%H:%M}-{pts[j][2]:%H:%M}  {secs/60:4.1f} min  "
              f"{length_m([p[:2] for p in pts[i:j+1]])/1000:4.2f} km")
    if len(runs) != 2:
        raise SystemExit(
            f"expected two IJ crossings in the Amsterdam ride, found {len(runs)}. "
            "Check them against the GVB ferry routes before trusting the split.")

    # Both crossings are confirmed against GVB's own routes rather than assumed:
    # a boat leg has to start and finish on a real ferry line.
    fr = overpass('[out:json][timeout:240];relation[route=ferry]'
                  '(52.36,4.85,52.42,4.93);out geom;', "ferry_routes.json")
    lines = [(f.get("tags", {}), stitch(f)) for f in fr["elements"]]
    lines = [(t, l) for t, l in lines if l]
    for i, j in runs:
        best = min(((max(nearest(l, pts[i][:2])[1], nearest(l, pts[j][:2])[1]), t)
                    for t, l in lines), key=lambda x: x[0])
        print(f"      {pts[i][2]:%H:%M} crossing snaps to "
              f"{best[1].get('ref','?')} {best[1].get('name','')[:46]} "
              f"at {best[0]:.0f} m")
        if best[0] > 80:
            raise SystemExit("a crossing does not lie on any GVB ferry route")

    # The recording starts 585 m from the station, already rolling east along
    # the Haarlemmerweg, so the first thing the day does in Amsterdam is missing
    # from it. Valhalla's bicycle route fills the gap, and takes exactly the way
    # described: west out of Sloterdijk onto Radarweg, then south and east along
    # the Haarlemmerweg. It is 1.7 km because there is no shorter way out of
    # that station - the rail corridor has to be got round. Drawn dashed, with
    # both ends on the same stop so it never becomes a step in the key.
    conn, conn_m = valhalla([STOPS["sloterdijk"], (pts[0][0], pts[0][1])],
                            "bicycle", "connector.json")
    add(r["seq"] - 5, "bike", "sloterdijk", "sloterdijk",
        [(p[0], p[1], None) for p in conn], "routed", "By bicycle",
        f"Before the recording started: out of Sloterdijk by Radarweg and the "
        f"Haarlemmerweg to where the trace begins, {conn_m/1000:.1f} km",
        ride="amsterdam", km=conn_m)

    FERRY_LEG = [("ijveer_cs", "ndsm", "GVB ferry",
                  "Centraal to NDSM, 13 minutes. OpenStreetMap carries this "
                  "crossing as both F4 and F5, so the page does not pick a number"),
                 ("buiksloterweg", "ijveer_cs", "GVB ferry F3",
                  "Buiksloterweg back to Centraal, the short way over")]
    # The middle stretch is one length of recording but two legs of the day: it
    # stops 57 minutes at IJver, which is longer than the ride stands still
    # anywhere else, and splitting it there is what lets the key say so.
    BIKE_LEG  = [("sloterdijk", "ijveer_cs", "vondelpark",
                  "South through the Baarsjes to the park",
                  "On to the Zuidas, then north through the center"),
                 ("ndsm", "buiksloterweg", "ijver",
                  "Along the north bank to the Scheepsbouwkade",
                  "On east to Buiksloterweg after the stop"),
                 ("ijveer_cs", "sloterdijk", None,
                  "Back west along the IJ to Sloterdijk", None)]
    # The trimmed tail now ends ~50 m short of the station; close it on the
    # marker so the day's loop actually shuts.
    pts = pts + [(STOPS["sloterdijk"][0], STOPS["sloterdijk"][1], pts[-1][2])]
    cuts = [0] + [x for i, j in runs for x in (i, j)] + [len(pts) - 1]
    for n in range(5):
        seg = pts[cuts[n]:cuts[n + 1] + 1]
        simple = rdp(seg, RDP_M)
        when = f"{seg[0][2]:%H:%M} to {seg[-1][2]:%H:%M}. "
        if n % 2:
            a, b, line, note = FERRY_LEG[n // 2]
            add(r["seq"] + n * 10, "ferry", a, b, simple, "gps", line,
                when + note, ride="amsterdam")
        else:
            a, b, split, note, note2 = BIKE_LEG[n // 2]
            if split is None:
                add(r["seq"] + n * 10, "bike", a, b, simple, "gps", "By bicycle",
                    when + note, ride="amsterdam")
                continue
            # Cut the segment at its closest approach to the stop it pauses at.
            k, d = min(((x, dist(q[:2], STOPS[split])) for x, q in enumerate(seg)),
                       key=lambda t: t[1])
            if d > 120:
                raise SystemExit(f"{split} is {d:.0f} m off this segment; "
                                 "check the split before trusting it")
            print(f"    split at {NAME[split]}: closest approach {d:.0f} m, "
                  f"{seg[k][2]:%H:%M}")
            for x, (aa, bb, part) in enumerate((
                    (a, split, seg[:k + 1]), (split, b, seg[k:]))):
                add(r["seq"] + n * 10 + x * 5, "bike", aa, bb, rdp(part, RDP_M),
                    "gps", "By bicycle",
                    f"{part[0][2]:%H:%M} to {part[-1][2]:%H:%M}. " +
                    (note if x == 0 else note2),
                    ride="amsterdam")

# ----------------------------------------------------------------- output ---
stops_fc = {"type": "FeatureCollection", "features": [
    {"type": "Feature",
     "properties": {"n": NUM[k], "name": n, "arrive": ARRIVE[k], "key": k,
                    "note": NOTES.get(k, "")},
     "geometry": {"type": "Point",
                  "coordinates": [round(STOPS[k][1], 6), round(STOPS[k][0], 6)]}}
    for k, n in ORDER]}
# Into the order the day happened. The sort key rides along into the page as a
# property rather than being stripped here: map-common.js orders the numbered
# key by it when every leg has one, so the list cannot fall back into source
# order if a leg is ever added to this file in the wrong place.
features.sort(key=lambda f: f["seq"])
for f in features:
    f["properties"]["seq"] = f.pop("seq")
lines_fc = {"type": "FeatureCollection", "features": features}

tpl = open(os.path.join(HERE, "template.html")).read()
tpl = tpl.replace("__LINES__", json.dumps(lines_fc, separators=(",", ":")))
tpl = tpl.replace("__STOPS__", json.dumps(stops_fc, separators=(",", ":")))
open(OUT, "w").write(tpl)

tot = {}
for f in features:
    p = f["properties"]
    tot[p["mode"]] = tot.get(p["mode"], 0) + p["km"]
print("\ntotals: " + ", ".join(f"{k} {v:.2f} km" for k, v in sorted(tot.items())))
print(f"the day came to {sum(tot.values()):.1f} km")
print(f"wrote {OUT}, {len(tpl)} bytes")
