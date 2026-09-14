"""Download OSM basemap tiles covering a bbox and stitch them into one image."""
import math, os, time, urllib.request
from PIL import Image

TILE_PX = 256
UA = "steven-personal-itinerary-map/1.0 (one-off personal travel map)"

def deg2num(lat, lon, z):
    n = 2.0 ** z
    x = (lon + 180.0) / 360.0 * n
    y = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n
    return x, y

def fetch(bbox, zoom, out):
    """bbox = (min_lat, min_lon, max_lat, max_lon). Stitches whole tiles, then
    crops to the exact bbox so the image has no dead margin."""
    min_lat, min_lon, max_lat, max_lon = bbox
    x0f, y0f = deg2num(max_lat, min_lon, zoom)
    x1f, y1f = deg2num(min_lat, max_lon, zoom)
    x0, y0, x1, y1 = int(x0f), int(y0f), int(x1f), int(y1f)
    cols, rows = x1 - x0 + 1, y1 - y0 + 1
    print(f"  z{zoom}: {cols}x{rows}={cols*rows} tiles", flush=True)

    canvas = Image.new("RGB", (cols * TILE_PX, rows * TILE_PX), "#f2efe9")
    os.makedirs("tilecache", exist_ok=True)
    for xi in range(x0, x1 + 1):
        for yi in range(y0, y1 + 1):
            path = f"tilecache/{zoom}_{xi}_{yi}.png"
            if not os.path.exists(path):
                url = f"https://tile.openstreetmap.org/{zoom}/{xi}/{yi}.png"
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": UA})
                    with urllib.request.urlopen(req, timeout=45) as r, open(path, "wb") as f:
                        f.write(r.read())
                except Exception as e:
                    print(f"    tile {zoom}/{xi}/{yi} failed: {e}")
                    continue
                time.sleep(0.08)
            if os.path.exists(path):
                canvas.paste(Image.open(path).convert("RGB"),
                             ((xi - x0) * TILE_PX, (yi - y0) * TILE_PX))

    # Crop to the requested bbox
    left  = int((x0f - x0) * TILE_PX)
    top   = int((y0f - y0) * TILE_PX)
    right = int((x1f - x0) * TILE_PX)
    bot   = int((y1f - y0) * TILE_PX)
    canvas = canvas.crop((left, top, right, bot))
    canvas.save(out)
    return {"zoom": zoom, "x0": x0, "y0": y0, "tile_px": TILE_PX,
            "crop": [left, top], "size": canvas.size, "out": out}
