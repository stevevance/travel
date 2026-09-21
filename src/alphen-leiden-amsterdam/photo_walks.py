"""Reconstruct the two walks from the day's photographs.

Alphen and Leiden were walked, not ridden, so Strava has nothing for either. The
camera does: seventeen stills in Alphen and sixteen in Leiden, each with a GPS
fix. Their positions in time order are the shape of the walk, and Valhalla's
pedestrian router joins them along real footways.

Run this once on a Mac with the Photos library, then build.py:

    python3 src/alphen-leiden-amsterdam/photo_walks.py
    python3 src/alphen-leiden-amsterdam/build.py

It writes walks.geojson, which IS committed - like bruges/photos.geojson - so a
clone with neither the Photos library nor a network can still rebuild the page.
The pictures themselves are not published here; only the routed line is.

The clock needs care, though not the care the Bruges day needed. The library
holds two rows for several of these pictures: one with a real +02:00 offset and
one written in UTC with no offset at all. The two are the SAME instant, so
nothing here is genuinely two hours out - but printing either with strftime
shows whatever offset that row happened to carry, which reads as a picture taken
two hours before the one before it. Every time is therefore parsed as
timezone-aware and converted to CEST before it is compared or shown, and the
duplicate rows are collapsed by original filename, preferring the row that
actually states its offset.
"""
import json, os, subprocess, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from osm import HERE, dist, length_m, VALHALLA, UA

CACHE = os.path.join(HERE, "library.json")      # gitignored: src/**/*.json
OUT   = os.path.join(HERE, "walks.geojson")     # committed
DAY   = "2026-09-20"

# Where each walk begins and ends, from OSM rather than from a photograph: a
# station entrance is a public, named point and the first fix is wherever the
# phone happened to come out of a pocket.
ANCHOR = {
    "alphen": (52.124806, 4.657105),            # Alphen aan den Rijn station
    "leiden": (52.166319, 4.482286),            # Leiden Centraal
}
# The boxes that sort the day's stills into the two walks. Everything else -
# Rotterdam, Gouda, the train windows, Amsterdam - falls outside both.
BOX = {
    "alphen": (52.120, 4.650, 52.140, 4.672),
    "leiden": (52.150, 4.475, 52.170, 4.495),
}
# The far end of each walk, where it turns around. Named so the page can say
# what the turn was rather than printing a coordinate.
# The Julianabrug's turn anchor is the point where the steps up from the east
# bank meet the deck, NOT the middle of the bridge. The middle is a
# `man_made=bridge` area rather than a routable path, and asking a pedestrian
# router to visit it sent both halves of the walk 200 m west to find a way up
# and then back again. Two waypoints on the steps themselves made that worse,
# not better - the same lesson as every other Valhalla bug in this repo.
TURN = {
    "alphen": ("julianabrug", (52.134870, 4.662759)),   # Koningin Julianabrug
    "leiden": ("chummy",      (52.158400, 4.489866)),   # Chummy Coffee
}
# Streets the router got wrong, corrected against the map by someone who walked
# them. A photograph fixes a point, not the way between two points, and where
# Leiden's old center offers two parallel routes a few tens of meters apart
# Valhalla picked the other one every time: Langebrug for Breestraat, the Stille
# Rijn for Haarlemmerstraat, and a loop out west by the Morspoort and Steenstraat
# instead of simply going down Stationsweg and along 2e Binnenvestgracht.
#
# Each of these is one point on the correct street, inserted into the waypoint
# list wherever it costs least - so it corrects the route without reordering it.
# Keep this list as short as it can be. The README's standing warning applies:
# over-constraining Valhalla makes it double back, and the fix for that is
# removing a waypoint, not adding another.
# Where a street has a parallel twin a few tens of meters away, one waypoint is
# not enough: the router visits it and rejoins the wrong street on either side.
# Those get two, at each end of the stretch, so the street has to be walked
# rather than touched.
VIA = {
    ("leiden", "out"):  [("Stationsweg",         (52.165115, 4.483949)),
                         ("2e Binnenvestgracht", (52.163795, 4.486000)),
                         ("Haarlemmerstraat",    (52.160751, 4.489171)),
                         ("Haarlemmerstraat",    (52.160260, 4.490999))],
    # One point, not two: IMG_0821 is already on Breestraat 11 m away, and
    # pinning both made the leg loop back around the block to reach them in
    # order. This is the README's warning in miniature - the fix was removing a
    # waypoint, not adding one.
    ("leiden", "back"): [("Breestraat",          (52.159821, 4.487664))],
}

# Photographs whose fix is a place the camera stood, not a street that was
# walked. IMG_0818 was taken from the Stille Rijn, 60 m off the Haarlemmerstraat
# the walk was actually on, and because a waypoint is an order rather than a hint
# it dragged the whole leg down onto the wrong quay and made it double back to
# get there. Dropping it as a WAYPOINT does not drop it as evidence: the two
# Haarlemmerstraat points above are where that stretch really went.
# Both frames, not one: they are the same view a second apart, and dropping only
# the first leaves the second pinning the identical spot.
DROP = {"IMG_0818.HEIC": "taken from the Stille Rijn; the walk was on Haarlemmerstraat",
        "IMG_0819.HEIC": "the same view one second later",
        # 11 m off Breestraat but it snaps to the lane behind, and as an order
        # rather than a hint it dragged 150 m of the walk onto Langebrug and
        # made the leg double back to reach it. The Breestraat point below is
        # where that stretch actually ran.
        "IMG_0821.HEIC": "snaps to Langebrug; the walk was on Breestraat"}

MIN_GAP = 40.0      # meters: two frames closer than this are one waypoint
CEST = timezone(timedelta(hours=2))   # the Netherlands, all of this day

if not os.path.exists(CACHE):
    print("reading the Photos library (a couple of minutes)")
    r = subprocess.run(["osxphotos", "query", "--from-date", DAY,
                        "--to-date", "2026-09-21", "--json", "--mute"],
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"osxphotos failed:\n{r.stderr[-2000:]}")
    json.dump(json.loads(r.stdout), open(CACHE, "w"))
library = json.load(open(CACHE))

# ------------------------------------------------------------------ clock ---
by_file = {}
for p in library:
    fn = p.get("original_filename")
    if p.get("ismovie") or not p.get("latitude"):
        continue
    # Of the duplicate rows keep the one that states its offset; both describe
    # the same instant, but only one of them prints as local time.
    if fn in by_file and by_file[fn]["tz"] is not None:
        continue
    by_file[fn] = {"file": fn, "tz": p.get("tzoffset"),
                   "t": datetime.fromisoformat(p["date"]).astimezone(CEST),
                   "pt": (p["latitude"], p["longitude"])}
stills = sorted(by_file.values(), key=lambda s: s["t"])
dupes = sum(1 for p in library
            if p.get("latitude") and not p.get("ismovie")) - len(stills)
print(f"{len(stills)} located stills, {dupes} duplicate rows collapsed; "
      f"all times shown in CEST")

# ------------------------------------------------------------- waypoints ---
def within(pt, box):
    return box[0] <= pt[0] <= box[2] and box[1] <= pt[1] <= box[3]

def route(pts):
    """Pedestrian route through every point, ends as breaks."""
    locs = [{"lat": p[0], "lon": p[1],
             "type": "break" if i in (0, len(pts) - 1) else "through"}
            for i, p in enumerate(pts)]
    body = {"locations": locs, "costing": "pedestrian",
            "directions_options": {"units": "kilometers"}}
    req = urllib.request.Request(
        VALHALLA + "?json=" + urllib.parse.quote(json.dumps(body)), headers=UA)
    try:
        d = json.load(urllib.request.urlopen(req, timeout=60))
    except urllib.error.HTTPError as ex:
        # Valhalla says what it could not do, and its message is specific -
        # which waypoint it failed to snap, or that two are the same. Losing it
        # to a bare "400 Bad Request" turns a two-minute fix into guesswork.
        raise SystemExit(f"Valhalla refused this leg: {ex.read().decode()[:500]}\n"
                         f"waypoints: {pts}")
    out = []
    for lg in d["trip"]["legs"]:
        shape, lat, lon, i = lg["shape"], 0, 0, 0
        while i < len(shape):
            for axis in range(2):
                sh, res, b = 0, 0, 0x20
                while b >= 0x20:
                    b = ord(shape[i]) - 63; i += 1
                    res |= (b & 0x1f) << sh; sh += 5
                d_ = ~(res >> 1) if res & 1 else res >> 1
                if axis == 0: lat += d_
                else:         lon += d_
            out.append((lat / 1e6, lon / 1e6))
    return out, d["trip"]["summary"]["length"] * 1000

features = []
for city, box in BOX.items():
    shots = [s for s in stills if within(s["pt"], box)]
    turn_key, turn_pt = TURN[city]
    # Split at the frame nearest the turnaround: everything up to it is the way
    # out, everything after is the way back.
    ti = min(range(len(shots)), key=lambda i: dist(shots[i]["pt"], turn_pt))
    print(f"\n{city}: {len(shots)} stills, "
          f"{shots[0]['t'].strftime('%H:%M')}-{shots[-1]['t'].strftime('%H:%M')}, "
          f"turn at {shots[ti]['file']} {shots[ti]['t'].strftime('%H:%M')} "
          f"({dist(shots[ti]['pt'], turn_pt):.0f} m from {turn_key})")

    for half, group, a, b in (("out",  shots[:ti + 1], ANCHOR[city], turn_pt),
                              ("back", shots[ti:],     turn_pt, ANCHOR[city])):
        way = [a]
        for s in group:
            if s["file"] in DROP:
                print(f"   {half:4s} not a waypoint: {s['file']} - {DROP[s['file']]}")
                continue
            if dist(way[-1], s["pt"]) >= MIN_GAP:
                way.append(s["pt"])
        if dist(way[-1], b) >= MIN_GAP:
            way.append(b)
        for street, pt in VIA.get((city, half), []):
            k = min(range(1, len(way)),
                    key=lambda i: dist(way[i - 1], pt) + dist(pt, way[i])
                                  - dist(way[i - 1], way[i]))
            way.insert(k, pt)
            print(f"   {half:4s} via {street} at waypoint {k}")
        # The public Valhalla takes ten locations and refuses the eleventh with a
        # bare 400. Every waypoint past that has to earn its place by replacing
        # one, not by being added to the end.
        if len(way) > 10:
            raise SystemExit(
                f"{city} {half}: {len(way)} waypoints, and Valhalla allows 10. "
                "Drop a photograph that only repeats its neighbour, or a VIA "
                "that a nearer one already covers.")
        pts, m = route(way)
        features.append({
            "type": "Feature",
            "properties": {"city": city, "half": half,
                           "waypoints": len(way),
                           "from_t": group[0]["t"].strftime("%H:%M"),
                           "to_t": group[-1]["t"].strftime("%H:%M"),
                           "km": round(m / 1000, 2)},
            "geometry": {"type": "LineString",
                         "coordinates": [[round(p[1], 6), round(p[0], 6)]
                                         for p in pts]},
        })
        print(f"   {half:4s} {len(way):2d} waypoints -> {m/1000:.2f} km, "
              f"{len(pts)} points")
        time.sleep(1.0)

json.dump({"type": "FeatureCollection", "features": features},
          open(OUT, "w"), separators=(",", ":"))
print(f"\nwrote {OUT}")
