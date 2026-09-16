"""Build the Bruges day: three Blue-bike rides, and nothing else.

This is the first map in the set with no routed geometry at all. Every metre
drawn here was recorded - three Strava exports in data/bruges/ - so unlike the
Utrecht page there is no dashed reconstruction to explain, and every leg carries
`source: "gps"`.

It is also the first map to carry photographs. The pictures are the day's own
camera roll, pulled out of Photos.app by pick_photos.py, placed by their EXIF
fix and spaced along each track by distance so a long stop does not spend the
whole quota in one place. That script writes photos.geojson next to this one; this
build only reads it, so re-running the build does not touch the Photos library.

    python3 src/bruges/pick_photos.py     # once, or after re-picking
    python3 src/bruges/build.py           # writes bruges-map.html
"""
import json, math, os, sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

sys.setrecursionlimit(10000)   # rdp recurses once per retained point

HERE  = os.path.dirname(os.path.abspath(__file__))
ROOT  = os.path.abspath(os.path.join(HERE, "..", ".."))
GPXDIR = os.path.join(ROOT, "data", "bruges")
PHOTOS = os.path.join(HERE, "photos.geojson")

# Strava stamps UTC; the phone stamped local. Belgium was on CEST all day.
TZ = timedelta(hours=2)
SNAP = 60.0    # metres: close a line on its marker only if it stopped this near

# ------------------------------------------------------------------ stops ---
# Every one of these is a public place: a bike-share dock, a sea wall, a pier,
# a street in the centre. The rides themselves start and end where the recording
# did, which is not always the same point - see the note on `zeebrugge`.
STOPS = {
    # The Blue-bike dock on the north side of Brugge station, 15 m from where
    # the first recording starts. The ride begins and the day ends here.
    "bluebike":    (51.196971, 3.218701),
    # Ride one stops on the Zeedijk at Zeebrugge; ride two starts 160 m south
    # on Londenstraat, by the Kusttram stop, after a walk along the sea wall.
    # The marker sits at the sea, where the ride out actually ended.
    "zeebrugge":   (51.328456, 3.176314),
    # Where the ride home stands still longest: 6 min 50 s, at the foot of the
    # pier. Longest within that one recording only - the day has far longer gaps
    # between the recordings, so do not call it the longest stop of the day.
    "blankenberge":(51.320130, 3.137270),
    # Oude Burg, in the centre. The ride back ends on this street; the evening
    # meander starts from it.
    "oudeburg":    (51.207566, 3.225410),
}
ORDER = [
    ("bluebike",     "Blue-bike, Brugge station"),
    ("zeebrugge",    "Zeebrugge, the Zeedijk"),
    ("blankenberge", "Blankenberge pier"),
    ("oudeburg",     "Oude Burg"),
]
NUM  = {k: i + 1 for i, (k, _) in enumerate(ORDER)}
NAME = dict(ORDER)
NOTES = {
    "bluebike":     "Picked the bike up here at 14:26, and put it back at 21:17",
    "zeebrugge":    "The sea, 21 km out. The ride back starts 160 m south, "
                    "on Londenstraat by the Kusttram stop",
    "blankenberge": "Turned west along the coast instead of south, and stood "
                    "seven minutes at the foot of the pier",
    "oudeburg":     "Back in the centre at 17:29, three and a half hours before "
                    "the evening ride",
}
# Not "bike", which every leg is. This page colours by ride, and `arrive` is what
# rings each stop, so it holds the ride that reached the place - which keeps the
# dot on the map and the number in the key the same colour. Stop 1 is the one
# ambiguous case: the purple ride left from it and the teal one came back to it
# nine hours later. It takes the ride that started there, and the key's own
# second row for it carries the teal.
ARRIVE = {"bluebike": "out", "zeebrugge": "out",
          "blankenberge": "back", "oudeburg": "back"}

# The three recordings, in the order they were ridden, and where each one is cut.
# The ride home is one Strava file but two legs of the day: it runs west along
# the coast to Blankenberge before turning inland, and splitting it at the pier
# is what lets the key say so.
RIDES = [
    {"key": "out",     "file": "Bruges_to_Sea_Bruges.gpx",
     "from": "bluebike", "to": "zeebrugge", "split": None,
     "note": "Out through Sint-Pieters and along the Boudewijnkanaal"},
    {"key": "back",    "file": "Sea_Bruges_back_to_Bruges.gpx",
     "from": "zeebrugge", "to": "oudeburg", "split": "blankenberge",
     "note": "West along the coast, then inland down the Blankenbergse Dijk"},
    {"key": "meander", "file": "Meandering_ride_around_Bruges_to_return_the_bike.gpx",
     "from": "oudeburg", "to": "bluebike", "split": None,
     "note": "Out to the Coupure and back round to the station, after dark"},
]

# --------------------------------------------------------------- geometry ---
def dist(a, b):
    dy = (a[0]-b[0])*111320.0
    dx = (a[1]-b[1])*111320.0*math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)

def length_m(pts):
    return sum(dist(pts[i], pts[i+1]) for i in range(len(pts)-1))

def read_gpx(path):
    # The traces are gitignored - they are finer than anything published and this
    # repo is public - so a fresh clone will not have them. Say so plainly.
    if not os.path.exists(path):
        raise SystemExit(
            f"missing {path}\n"
            "The Strava exports are deliberately not in git. Drop the three "
            "Bruges .gpx files back into data/bruges/ to rebuild.")
    NS = "{http://www.topografix.com/GPX/1/1}"
    root = ET.parse(path).getroot()
    return [(float(p.get("lat")), float(p.get("lon")),
             datetime.strptime(p.findtext(NS+"time"), "%Y-%m-%dT%H:%M:%SZ"))
            for p in root.iter(NS + "trkpt")]

def trim_loitering(pts, R=20.0):
    """Drop the standing-around at each end of a recording.

    Strava was started before the bike moved and stopped after it had, so each
    raw track opens and closes with sub-metre jitter that draws as a blot. Keep
    from the last fix still within R of the first, to the first already within R
    of the last."""
    i = 0
    for k in range(len(pts)):
        if dist(pts[0][:2], pts[k][:2]) < R: i = k
    j = len(pts) - 1
    for k in range(len(pts) - 1, -1, -1):
        if dist(pts[-1][:2], pts[k][:2]) < R: j = k
    return pts[i:j+1], i, len(pts) - 1 - j

def rdp(pts, eps):
    """Ramer-Douglas-Peucker. A one-second Strava trace is far denser than a page
    needs; these three files carry 11,562 points between them."""
    if len(pts) < 3:
        return list(pts)
    a, b = pts[0], pts[-1]
    ab = dist(a, b)
    far, fi = -1.0, 0
    for i in range(1, len(pts) - 1):
        p = pts[i]
        if ab == 0:
            d = dist(p, a)
        else:
            # Perpendicular distance in local metres, good enough at city scale.
            ay = (a[0]-p[0])*111320.0; ax = (a[1]-p[1])*111320.0*math.cos(math.radians(p[0]))
            by = (b[0]-p[0])*111320.0; bx = (b[1]-p[1])*111320.0*math.cos(math.radians(p[0]))
            d = abs(ax*by - ay*bx) / ab
        if d > far: far, fi = d, i
    if far <= eps:
        return [a, b]
    return rdp(pts[:fi+1], eps)[:-1] + rdp(pts[fi:], eps)

def nearest(pts, target):
    return min(range(len(pts)), key=lambda i: dist(pts[i][:2], target))

def hhmm(t):
    return (t + TZ).strftime("%H:%M")

# ------------------------------------------------------------- build legs ---
features = []

def add(ride, a, b, pts, raw_km, note, t0, t1):
    features.append({
        "type": "Feature",
        # `ride` names which of the three recordings this leg came out of, so the
        # page can group the four legs back into three rides - and match them to
        # the pictures, which carry the same key.
        "properties": {"mode": "bike", "ride": ride,
                       "from": NAME[a], "to": NAME[b],
                       "from_n": NUM[a], "to_n": NUM[b], "line": "Blue-bike",
                       "km": round(raw_km, 2), "mi": round(raw_km / 1.609344, 2),
                       "source": "gps", "note": note,
                       "start": hhmm(t0), "end": hhmm(t1),
                       "mins": round((t1 - t0).total_seconds() / 60)},
        "geometry": {"type": "LineString",
                     "coordinates": [[round(p[1], 6), round(p[0], 6)] for p in pts]},
    })
    print(f"  {NAME[a]:26s} -> {NAME[b]:26s} {raw_km:5.2f} km  "
          f"{len(pts):4d} pts  {hhmm(t0)}-{hhmm(t1)}")

print("rides")
for r in RIDES:
    raw = read_gpx(os.path.join(GPXDIR, r["file"]))
    track, lead, tail = trim_loitering(raw)
    print(f"\n{r['key']}: {len(raw)} points, trimmed {lead} loitering at the "
          f"start and {tail} at the end, {length_m([p[:2] for p in raw])/1000:.2f} km raw")

    # Close a drawn line on its marker when the recording stops a few metres
    # short of it - but only then. The ride back begins 160 m from the marker at
    # Zeebrugge, because that distance was walked along the sea wall between the
    # two recordings, and drawing it as ridden would be a lie. SNAP is the line
    # between "the GPS stopped early" and "something happened here".
    a, b = r["from"], r["to"]
    if dist(track[0][:2], STOPS[a]) < SNAP:
        track = [(STOPS[a][0], STOPS[a][1], track[0][2])] + track
    else:
        print(f"  start left {dist(track[0][:2], STOPS[a]):.0f} m short of "
              f"{NAME[a]}, not snapped")
    if dist(track[-1][:2], STOPS[b]) < SNAP:
        track = track + [(STOPS[b][0], STOPS[b][1], track[-1][2])]
    else:
        print(f"  end left {dist(track[-1][:2], STOPS[b]):.0f} m short of "
              f"{NAME[b]}, not snapped")

    if r["split"]:
        c = r["split"]
        i = nearest(track, STOPS[c])
        # The pier sits on the track, so the split point is the track's own fix,
        # not the stop coordinate: snapping it would shift the line sideways.
        first, second = track[:i+1], track[i:]
        for (x, y, seg) in ((a, c, first), (c, b, second)):
            simple = rdp(seg, 2.0)
            add(r["key"], x, y, simple, length_m([p[:2] for p in seg])/1000,
                r["note"], seg[0][2], seg[-1][2])
            print(f"    {len(seg)} -> {len(simple)} after rdp(2 m)")
    else:
        simple = rdp(track, 2.0)
        add(r["key"], a, b, simple, length_m([p[:2] for p in track])/1000,
            r["note"], track[0][2], track[-1][2])
        print(f"    {len(track)} -> {len(simple)} after rdp(2 m)")

stops_fc = {"type": "FeatureCollection", "features": [
    {"type": "Feature",
     "properties": {"n": NUM[k], "name": n, "arrive": ARRIVE[k],
                    "key": k, "note": NOTES.get(k, "")},
     "geometry": {"type": "Point",
                  "coordinates": [round(STOPS[k][1], 6), round(STOPS[k][0], 6)]}}
    for k, n in ORDER]}
lines_fc = {"type": "FeatureCollection", "features": features}

# ----------------------------------------------------------------- photos ---
# What each picture is, keyed by the original filename pick_photos.py recorded.
# A script can place a photograph but it cannot say what is in it, so this is the
# one hand-written table in the build. It lives here rather than in the picker so
# that writing a caption costs a one-second rebuild, not another pass over the
# Photos library.
CAPTIONS = {
    # Out of Bruges, north through the polders to the sea
    "IMG_0132.HEIC": "The ring canal at the Buiten Smedenvest, five minutes out "
                     "of the station",
    "IMG_0145.HEIC": "Brick terraces and a red cycleway on the Dudzeelse "
                     "Steenweg",
    "IMG_0155.HEIC": "A piebald horse grazing in the polder at Dudzele",
    # Two movable bridges stand within 350 m of this spot, the Dudzeelse Brug and
    # the Herdersbrug, and the picture does not say which one is up. It says a
    # bascule bridge instead.
    "IMG_0159.HEIC": "A bascule bridge up over the Boudewijnkanaal, and the "
                     "traffic waiting for it",
    "IMG_0171.HEIC": "A sculler out on the Boudewijnkanaal at Lissewege",
    "IMG_0178.HEIC": "Brick gables on the Lisseweegse Steenweg, and a turbine "
                     "standing over them",
    "IMG_0181.HEIC": "Into Zeebrugge: lorries on the road, a separated path "
                     "beside it",
    # The turnaround, on foot at the sea
    "IMG_0183.HEIC": "Low tide at Zeebrugge, the cabins in one long white row",
    "IMG_0185.HEIC": "Beach cabins on the sand, container cranes behind them",
    "IMG_0186.HEIC": "A Kusttram at the stop, and a cyclist waiting with it",
    # Back west along the coast, then south down the Blankenbergse Dijk
    "IMG_0191.HEIC": "A board on the Kustlaan naming the birds of the Zeebos",
    "IMG_0204.HEIC": "The Zeedijk at Blankenberge, shops and awnings a block "
                     "back from the sea",
    # Two-thirds of this frame is sky. The animals on the green strip beyond the
    # stubble are too far off to name, so the caption does not try.
    "IMG_0208.HEIC": "A cloud bank over a harvested field, the polder flat all "
                     "the way to the treeline",
    "IMG_0215.HEIC": "The Blankenbergse Dijk runs dead straight through "
                     "Zuienkerke",
    "IMG_0222.HEIC": "The bike itself: a Blue-bike, orange-walled tyres, hired "
                     "at the station",
    "IMG_0230.HEIC": "A sheep beside the path, on the last stretch into Bruges",
    "IMG_0235.HEIC": "Through the Ezelpoort, back inside the ring",
    # The evening meander. Its only picture: the ride has no other, which is why
    # pick_photos.py prints UNDER THE FLOOR for it.
    "IMG_0266.HEIC": "The canal at the Kruisvest after dark",
}

if not os.path.exists(PHOTOS):
    raise SystemExit(
        f"missing {PHOTOS}\nRun `python3 src/bruges/pick_photos.py` first; it "
        "reads the Photos library and writes the picks this build draws.")
photos_fc = json.load(open(PHOTOS))
missing = []
for f in photos_fc["features"]:
    p = f["properties"]
    p["caption"] = CAPTIONS.get(p["file"], "")
    if not p["caption"]:
        missing.append(p["file"])
    img = os.path.join(ROOT, p["img"])
    if not os.path.exists(img):
        raise SystemExit(f"{p['img']} is in photos.geojson but not on disk. "
                         "Re-run pick_photos.py.")
print(f"\nphotos: {len(photos_fc['features'])} placed")
if missing:
    print(f"  no caption yet for {len(missing)}: {', '.join(sorted(missing))}")

# ------------------------------------------------------------------ write ---
tpl = open(os.path.join(HERE, "template.html")).read()
tpl = tpl.replace("__LINES__",  json.dumps(lines_fc,  separators=(",", ":")))
tpl = tpl.replace("__STOPS__",  json.dumps(stops_fc,  separators=(",", ":")))
tpl = tpl.replace("__PHOTOS__", json.dumps(photos_fc, separators=(",", ":")))
out = os.path.join(ROOT, "bruges-map.html")
open(out, "w").write(tpl)

km = sum(f["properties"]["km"] for f in features)
print(f"\ntotal {km:.2f} km / {km/1.609344:.2f} mi over {len(features)} legs")
print(f"wrote {out}, {len(tpl)} bytes")
