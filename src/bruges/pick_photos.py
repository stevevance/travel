"""Pull the day's pictures out of Photos.app and place them on the three tracks.

Run this once, then build.py. It writes:

    photos/bruges/*.jpg      the pictures, resized for the web
    src/bruges/photos.geojson  where each one goes, and what it is

Everything here needs a Mac with the Photos library that holds 16 September
2026, so it is deliberately separate from build.py: a clone without the library
can still rebuild the page from the committed geojson.

Placement rule. Each still is matched to the ride whose recording window covers
its EXIF timestamp, then snapped to the nearest fix on that track. The brief was
at least one picture per three miles with a floor of one per ride; the picks are
spread evenly by distance along the track rather than by clock, so the six
minutes standing at Blankenberge pier do not eat a whole ride's quota.

Two things this has to get right and would fail silently on otherwise:

  - The GPX is UTC and Photos reports local. Belgium was on CEST all day, so the
    photo times get two hours taken off before any comparison. Skip that and
    every picture lands on the wrong ride, or on none.
  - The library holds three rows for IMG_0229.HEIC, one of them stamped exactly
    two hours early, which put a picture 2.2 km off the ride out. Duplicate
    original filenames are dropped, keeping the first, and anything further than
    200 m from its track is dropped as a bad fix.
"""
import json, math, os, subprocess, sys, tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

HERE   = os.path.dirname(os.path.abspath(__file__))
ROOT   = os.path.abspath(os.path.join(HERE, "..", ".."))
GPXDIR = os.path.join(ROOT, "data", "bruges")
OUTDIR = os.path.join(ROOT, "photos", "bruges")
GEO    = os.path.join(HERE, "photos.geojson")
# Reading the library takes two to three minutes, and choosing which pictures to
# keep takes several passes. Cache the query so that only the first one is slow;
# `--refresh` re-reads it, which is what you want after the phone has synced more
# of the day up to iCloud. Gitignored along with the rest of src/**/*.json.
CACHE  = os.path.join(HERE, "library.json")

DAY   = "2026-09-16"
TZ    = timedelta(hours=2)      # CEST: Photos reports local, Strava stamps UTC
MI    = 1609.344
PER_MI  = 2.0                   # aim for one picture every two miles...
FLOOR_MI = 3.0                  # ...and never fewer than one per three
MIN_GAP = 0.25 * MI             # two frames this close are the same view
MAX_OFF = 200.0                 # metres from the track before a fix is junk
LONG_EDGE = 1400                # plenty for a popup, small enough to ship
JPEG_Q  = "45"                  # sips quality; ~240 KB a picture at this size

RIDES = [("out",     "Bruges_to_Sea_Bruges.gpx"),
         ("back",    "Sea_Bruges_back_to_Bruges.gpx"),
         ("meander", "Meandering_ride_around_Bruges_to_return_the_bike.gpx")]

# Pictures taken off the bike that still belong on the map: the turnaround at
# the sea, between the two long rides, and the one after the bike went back.
# Keyed by original filename so a re-pick cannot renumber them.
EXTRA = {
    "IMG_0183.HEIC": "zeebrugge",
    "IMG_0185.HEIC": "zeebrugge",
    "IMG_0186.HEIC": "zeebrugge",
}

# Pictures to pass over, however well they happen to fall on the track. The
# spacing rule can tell where a photograph was taken; it cannot tell whether it
# is worth looking at, and without this the only way to refuse one is to move the
# spacing and disturb every other pick on that ride.
EXCLUDE = {
    # Empty suburban tarmac on the way out of Bruges. True to the ride, dull to
    # look at.
    "IMG_0148.HEIC",
    # Three frames of a crash barrier and a signpost, taken within a few seconds
    # of each other where the route meets the Boudewijnkanaal. Excluding one just
    # promotes the next, so the run goes as a run; the picker then reaches
    # IMG_0159, the raised bascule bridge at the same spot.
    "IMG_0156.HEIC",
    "IMG_0157.HEIC",
    "IMG_0158.HEIC",
    # The second of two frames of the same canal seven seconds apart. Dropping it
    # puts the evening meander under the one-per-three-miles floor, because
    # IMG_0266 is then the only picture taken anywhere on that ride; the run
    # warns about it rather than quietly shipping short.
    "IMG_0267.HEIC",
}

# Rides allowed to come in under the one-per-three-miles floor, and why. A ride
# can only be short because the pictures do not exist, so this is a note that
# someone looked and accepted it - not a way of lowering the bar. Any ride not
# named here that falls short still gets shouted about.
SHORT_OK = {
    "meander": "only two stills were taken on the whole ride, seven seconds "
               "apart at the same canal, and the second is excluded as a "
               "near-duplicate",
}

# Captions live in build.py, keyed by these same filenames. Keeping them out of
# here means writing one does not cost another pass over the Photos library.

# ------------------------------------------------------------------ helpers --
def dist(a, b):
    dy = (a[0]-b[0])*111320.0
    dx = (a[1]-b[1])*111320.0*math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)

def read_track(path):
    NS = "{http://www.topografix.com/GPX/1/1}"
    pts = [(float(p.get("lat")), float(p.get("lon")),
            datetime.strptime(p.findtext(NS+"time"), "%Y-%m-%dT%H:%M:%SZ"))
           for p in ET.parse(path).getroot().iter(NS+"trkpt")]
    cum = [0.0]
    for i in range(1, len(pts)):
        cum.append(cum[-1] + dist(pts[i-1][:2], pts[i][:2]))
    return pts, cum

def osxphotos(*args):
    r = subprocess.run(["osxphotos", *args], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"osxphotos {args[0]} failed:\n{r.stderr[-2000:]}")
    return r

# ------------------------------------------------------------------- query --
if os.path.exists(CACHE) and "--refresh" not in sys.argv:
    library = json.load(open(CACHE))
    print(f"reading {os.path.basename(CACHE)} ({len(library)} items cached); "
          "pass --refresh to re-read the library")
else:
    print("reading the Photos library (this takes a couple of minutes)")
    library = json.loads(osxphotos("query", "--from-date", DAY,
                                   "--to-date", "2026-09-17",
                                   "--json", "--mute").stdout)
    json.dump(library, open(CACHE, "w"))
print(f"  {len(library)} items on {DAY}")

seen = set()
stills = []
for p in library:
    if p.get("ismovie") or not p.get("latitude"):
        continue
    fn = p.get("original_filename")
    if fn in seen:                      # see the note about IMG_0229 above
        print(f"  duplicate {fn} at {p['date'][11:19]}, dropped")
        continue
    seen.add(fn)
    if fn in EXCLUDE:
        print(f"  excluded {fn} at {p['date'][11:19]}")
        continue
    stills.append(p)
print(f"  {len(stills)} located stills after de-duplication")

def utc(p):
    return datetime.strptime(p["date"][:19], "%Y-%m-%dT%H:%M:%S") - TZ

# ------------------------------------------------------------------- place --
tracks = {k: read_track(os.path.join(GPXDIR, f)) for k, f in RIDES}
cand = {k: [] for k, _ in RIDES}
extra = []

for p in stills:
    t, here = utc(p), (p["latitude"], p["longitude"])
    ride = next((k for k, _ in RIDES
                 if tracks[k][0][0][2] <= t <= tracks[k][0][-1][2]), None)
    rec = {"uuid": p["uuid"], "file": p["original_filename"],
           "time": p["date"][11:16], "lat": p["latitude"], "lon": p["longitude"]}
    if ride:
        pts, cum = tracks[ride]
        off, i = min((dist(q[:2], here), i) for i, q in enumerate(pts))
        if off > MAX_OFF:
            print(f"  off-track {rec['file']} at {rec['time']}, {off:.0f} m "
                  f"from the {ride} ride, dropped")
            continue
        cand[ride].append({**rec, "ride": ride, "along": cum[i], "off": off})
    elif rec["file"] in EXTRA:
        extra.append({**rec, "ride": "stop", "stop": EXTRA[rec["file"]]})

def spread(items, n, min_gap):
    """n pictures as evenly spaced along the track as the day allows."""
    items = sorted(items, key=lambda x: x["along"])
    if not items:
        return []
    total = items[-1]["along"] or 1.0
    out = []
    for k in range(n):
        want = total * (k + 0.5) / n
        taken = {y["uuid"] for y in out}
        free = [x for x in items if x["uuid"] not in taken
                and all(abs(x["along"] - y["along"]) >= min_gap for y in out)]
        if not free:
            break
        out.append(min(free, key=lambda x: abs(x["along"] - want)))
    return sorted(out, key=lambda x: x["along"])

picked = []
for key, _ in RIDES:
    miles = tracks[key][1][-1] / MI
    floor = math.ceil(miles / FLOOR_MI)
    n = max(1, floor, round(miles / PER_MI))
    got = spread(cand[key], n, MIN_GAP)
    if len(got) < floor:
        # The floor outranks the spacing: the evening meander only has pictures
        # from one spot, and the brief still wants two.
        got = spread(cand[key], n, 0.0)
    print(f"\n{key}: {miles:.2f} mi, floor {floor}, {len(got)} of "
          f"{len(cand[key])} candidates")
    if len(got) < floor:
        # Only reachable when the day simply has no more pictures to give - every
        # candidate excluded, or none taken. A ride quietly coming in under the
        # floor is exactly the kind of thing nobody notices, so it is either
        # accounted for in SHORT_OK or it is shouted about.
        if key in SHORT_OK:
            print(f"   {len(got)} for {miles:.2f} mi, under the floor of {floor} "
                  f"and accepted: {SHORT_OK[key]}")
        else:
            print(f"   UNDER THE FLOOR: {len(got)} picture(s) for {miles:.2f} mi, "
                  f"wanted {floor}. The ride has {len(cand[key])} candidate(s) "
                  "in all. Either find one, or add the ride to SHORT_OK.")
    for x in got:
        print(f"   {x['time']}  {x['along']/MI:5.2f} mi  {x['file']}")
    picked += got

print(f"\noff the bike: {len(extra)} of {len(EXTRA)} wanted")
for x in extra:
    print(f"   {x['time']}  {x['file']}  at {x['stop']}")
picked += extra
picked.sort(key=lambda x: x["time"])

missing = set(EXTRA) - {x["file"] for x in extra}
if missing:
    print(f"\nwarning: EXTRA names {sorted(missing)}, which the library did not "
          "return as located stills on this day")

# ------------------------------------------------------------------ export --
# Most of these live only in iCloud, so the export has to pull them down first;
# --use-photokit is the fast path for that. HEIC goes to JPEG because no browser
# can be relied on for HEIC.
print(f"\nexporting {len(picked)} originals")
os.makedirs(OUTDIR, exist_ok=True)
with tempfile.TemporaryDirectory() as tmp:
    uu = os.path.join(tmp, "uuids.txt")
    open(uu, "w").write("\n".join(x["uuid"] for x in picked) + "\n")
    stage = os.path.join(tmp, "export")
    os.makedirs(stage)
    # --skip-original-if-edited matters: without it an edited picture comes out
    # twice, as IMG_0235.jpeg and IMG_0235_edited.jpeg. With it, only the
    # _edited file is written and there is no plain-named one at all - which is
    # why the lookup below has to go looking for both names.
    osxphotos("export", stage, "--uuid-from-file", uu, "--download-missing",
              "--use-photokit", "--convert-to-jpeg", "--jpeg-quality", "0.92",
              "--skip-live", "--skip-original-if-edited", "--no-progress")

    for x in picked:
        stem = os.path.splitext(x["file"])[0]
        # Prefer the edit, since that is the version worth showing, and fall
        # back to the untouched original. Extensions vary: HEIC becomes .jpeg,
        # anything already JPEG keeps whatever it had.
        found = [os.path.join(stage, n) for n in sorted(os.listdir(stage))
                 if os.path.splitext(n)[0] in (stem + "_edited", stem)]
        found.sort(key=lambda n: "_edited" not in n)
        if not found:
            sys.exit(f"{x['file']} did not come out of the export - is it still "
                     "downloading from iCloud?")
        src = found[0]
        dst = os.path.join(OUTDIR, os.path.splitext(x["file"])[0].lower() + ".jpg")
        # sips ships with macOS, so no image library to install. It resamples in
        # place, hence the copy first.
        subprocess.run(["cp", src, dst], check=True)
        # sips resamples the stored pixels and leaves the EXIF orientation tag
        # alone, which is what we want: half of these were shot in portrait and
        # every current browser rotates from the tag.
        subprocess.run(["sips", "--resampleHeightWidthMax", str(LONG_EDGE),
                        "-s", "format", "jpeg", "-s", "formatOptions", JPEG_Q,
                        dst, "--out", dst],
                       check=True, capture_output=True)
        x["img"] = "photos/bruges/" + os.path.basename(dst)
        print(f"  {x['img']}  {os.path.getsize(dst)//1024} KB")

# Sweep out anything left over from an earlier pick. Without this an excluded or
# superseded picture stays on disk, out of the geojson and so invisible on the
# page, and gets committed anyway.
keep = {os.path.basename(x["img"]) for x in picked}
for stale in sorted(set(os.listdir(OUTDIR)) - keep):
    os.remove(os.path.join(OUTDIR, stale))
    print(f"  removed {stale}, no longer picked")

# ----------------------------------------------------------------- geojson --
fc = {"type": "FeatureCollection", "features": [
    {"type": "Feature",
     # `file` is what build.py keys its captions on, and what lets a picture on
     # the page be traced back to the library it came out of.
     "properties": {"img": x["img"], "file": x["file"], "time": x["time"],
                    "ride": x["ride"], "stop": x.get("stop")},
     "geometry": {"type": "Point",
                  "coordinates": [round(x["lon"], 6), round(x["lat"], 6)]}}
    for x in picked]}
json.dump(fc, open(GEO, "w"), indent=1)
total = sum(os.path.getsize(os.path.join(ROOT, f["properties"]["img"]))
            for f in fc["features"])
print(f"\nwrote {GEO}, {len(fc['features'])} pictures, {total//1024} KB of JPEG")
print("now write a caption for each in CAPTIONS in build.py, and run it")
