"""Pull the ride's pictures out of Photos.app and write photos.geojson.

Run this once, then build.py. Unlike Bruges there is no picking to do: one
album in Photos holds exactly the pictures for the page, and each one goes where
the phone says it was taken. With no recording there is no track to snap them
to. The album's name is an argument rather than written here, because it names
someone who was on the ride.

    python3 src/chicago-south-side-ride/pick_photos.py "<album name>"   # -> photos/chicago-south-side-ride/*.jpg
    python3 src/chicago-south-side-ride/build.py

Needs a Mac, osxphotos and the Photos library; build.py needs only the committed
geojson. Every picture was looked at before it shipped - see src/README.md.
"""
import json, os, subprocess, sys, tempfile

HERE   = os.path.dirname(os.path.abspath(__file__))
ROOT   = os.path.abspath(os.path.join(HERE, "..", ".."))
OUTDIR = os.path.join(ROOT, "photos", "chicago-south-side-ride")
GEO    = os.path.join(HERE, "photos.geojson")
if len(sys.argv) != 2:
    sys.exit("usage: pick_photos.py \"<album name in Photos>\"")
ALBUM  = sys.argv[1]
LONG_EDGE = 1400
JPEG_Q    = "45"


def osxphotos(*args):
    r = subprocess.run(["osxphotos", *args], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"osxphotos {args[0]} failed:\n{r.stderr[-2000:]}")
    return r.stdout


shots = json.loads(osxphotos("query", "--album", ALBUM, "--json"))
shots = [s for s in shots if s.get("latitude") is not None]
shots.sort(key=lambda s: s["date"])
print(f"{len(shots)} pictures with a location in '{ALBUM}'")

os.makedirs(OUTDIR, exist_ok=True)
with tempfile.TemporaryDirectory() as tmp:
    uu = os.path.join(tmp, "uuids.txt")
    open(uu, "w").write("\n".join(s["uuid"] for s in shots) + "\n")
    stage = os.path.join(tmp, "export")
    os.makedirs(stage)
    # Same flags as Bruges, for the same reasons: most originals are in iCloud,
    # no browser can be relied on for HEIC, and an edited picture comes out only
    # as _edited, so the lookup tries both names.
    osxphotos("export", stage, "--uuid-from-file", uu, "--download-missing",
              "--use-photokit", "--convert-to-jpeg", "--jpeg-quality", "0.92",
              "--skip-live", "--skip-original-if-edited", "--no-progress")
    for s in shots:
        stem = os.path.splitext(s["original_filename"])[0]
        found = sorted((n for n in os.listdir(stage)
                        if os.path.splitext(n)[0] in (stem + "_edited", stem)),
                       key=lambda n: "_edited" not in n)
        if not found:
            sys.exit(f"{s['original_filename']} did not come out of the export")
        dst = os.path.join(OUTDIR, stem.lower() + ".jpg")
        subprocess.run(["cp", os.path.join(stage, found[0]), dst], check=True)
        subprocess.run(["sips", "--resampleHeightWidthMax", str(LONG_EDGE),
                        "-s", "format", "jpeg", "-s", "formatOptions", JPEG_Q,
                        dst, "--out", dst], check=True, capture_output=True)
        s["img"] = "photos/chicago-south-side-ride/" + os.path.basename(dst)
        print(f"  {s['img']}  {os.path.getsize(dst)//1024} KB")

keep = {os.path.basename(s["img"]) for s in shots}
for stale in sorted(set(os.listdir(OUTDIR)) - keep):
    os.remove(os.path.join(OUTDIR, stale))
    print(f"  removed {stale}, no longer in the album")

fc = {"type": "FeatureCollection", "features": [
    {"type": "Feature",
     # Photos reports the local time, which is the time to print.
     "properties": {"img": s["img"], "file": s["original_filename"],
                    "time": s["date"][11:16]},
     "geometry": {"type": "Point",
                  "coordinates": [round(s["longitude"], 6),
                                  round(s["latitude"], 6)]}}
    for s in shots]}
json.dump(fc, open(GEO, "w"), indent=1)
print(f"wrote {GEO}; now caption each one in CAPTIONS in build.py")
