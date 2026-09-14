"""Render the Hague-day transportation route as a static PNG."""
import json, math
from PIL import Image, ImageDraw, ImageFont
from routes import load, stitch, slice_line, STOPS

# ---------------------------------------------------------------- palette ----
# Categorical by MODE (3 slots, validated all-pairs light via the dataviz
# validator). Line identity rides on direct-labeled badges, not on hue.
METRO = "#2a78d6"   # slot 1 blue
TRAM  = "#eb6834"   # slot 2 orange
TRAIN = "#1baf7a"   # slot 3 aqua
WALK  = "#6b6862"   # neutral, dashed
INK       = "#14201c"
INK_SOFT  = "#5a5346"
SURFACE   = "#ffffff"

meta = json.load(open("basemap_meta.json"))
Z, X0, Y0, TP = meta["zoom"], meta["x0"], meta["y0"], meta["tile_px"]

def project(lat, lon):
    """lat/lon -> pixel coordinates on the stitched tile canvas."""
    n = 2.0 ** Z
    x = (lon + 180.0) / 360.0 * n
    y = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n
    return ((x - X0) * TP, (y - Y0) * TP)

# ------------------------------------------------------------------ legs -----
rels = load("routes_geom.json"); rels.update(load("train_geom.json"))
LINES = {rid: stitch(r) for rid, r in rels.items()}

# (mode, badge, relation id or None for walking, origin, destination)
LEGS = [
    ("metro", "E",  2777287, "meijersplein",  "denhaag_cs"),
    ("tram",  "9",  153659,  "denhaag_cs",    "bierkade"),
    ("walk",  None, None,    "bierkade",      "kerkplein"),
    ("tram",  "9",  153659,  "kerkplein",     "ov_museum"),
    ("tram",  "9",  1923134, "ov_museum",     "kurhaus"),
    ("tram",  "9",  153659,  "kurhaus",       "malieveld"),
    ("walk",  None, None,    "malieveld",     "grote_markt"),
    ("tram",  "1",  1862707, "grote_markt",   "prinsenhof"),
    ("walk",  None, None,    "prinsenhof",    "hanno"),
    ("walk",  None, None,    "hanno",         "lakila"),
    ("walk",  None, None,    "lakila",        "delft_station"),
    ("train", "NS", 325507,  "delft_station", "rotterdam_cs"),
    ("tram",  "8",  3009652, "rotterdam_cs",  "wilgenlei"),
]

MODE_COLOR = {"metro": METRO, "tram": TRAM, "train": TRAIN, "walk": WALK}

def leg_points(leg):
    """Real track geometry for a transit leg; a straight hop for a walk."""
    mode, badge, rid, a, b = leg
    if rid is None:
        return [STOPS[a], STOPS[b]]
    seg, _, _ = slice_line(LINES[rid], STOPS[a], STOPS[b])
    # Anchor the drawn segment to the actual stop locations at both ends
    return [STOPS[a]] + seg + [STOPS[b]]

# ------------------------------------------------------------------ stops ----
ORDER = [
    ("meijersplein",  "Meijersplein"),
    ("denhaag_cs",    "Den Haag Centraal"),
    ("bierkade",      "Bierkade"),
    ("kerkplein",     "Kerkplein"),
    ("ov_museum",     "HTM transport museum"),
    ("kurhaus",       "Kurhaus"),
    ("malieveld",     "Malieveld"),
    ("grote_markt",   "Grote Markt"),
    ("prinsenhof",    "Prinsenhof, Delft"),
    ("hanno",         "Hanno"),
    ("lakila",        "Lakila"),
    ("delft_station", "Delft station"),
    ("rotterdam_cs",  "Rotterdam Centraal"),
    ("wilgenlei",     "Wilgenlei"),
]
PY_MODE = {  # which mode's color rings each numbered stop (mode of arrival)
    "meijersplein": "metro", "denhaag_cs": "metro", "bierkade": "tram",
    "kerkplein": "walk", "ov_museum": "tram", "kurhaus": "tram",
    "malieveld": "tram", "grote_markt": "walk", "prinsenhof": "tram",
    "hanno": "walk", "lakila": "walk", "delft_station": "walk",
    "rotterdam_cs": "train", "wilgenlei": "tram",
}

def dashed(draw, pts, color, width, dash=34, gap=26):
    """Draw a polyline as dashes, carrying leftover length across vertices."""
    carry, on = 0.0, True
    for i in range(len(pts) - 1):
        (x1, y1), (x2, y2) = pts[i], pts[i + 1]
        seg = math.hypot(x2 - x1, y2 - y1)
        if seg == 0:
            continue
        t = 0.0
        while t < seg:
            step = (dash if on else gap) - carry
            end = min(t + step, seg)
            if on:
                draw.line([(x1 + (x2 - x1) * t / seg, y1 + (y2 - y1) * t / seg),
                           (x1 + (x2 - x1) * end / seg, y1 + (y2 - y1) * end / seg)],
                          fill=color, width=width)
            if end - t >= step:
                on, carry = not on, 0.0
            else:
                carry += end - t
            t = end

# ------------------------------------------------------------------ draw -----
base = Image.open("basemap.png").convert("RGB")
# Fade the basemap so the route reads as the figure and the map as ground
base = Image.blend(base, Image.new("RGB", base.size, "#ffffff"), 0.38)
overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
d = ImageDraw.Draw(overlay)

CASING, STROKE, WALK_W = 26, 15, 11

# Pass 1: white casing under every leg so crossings stay legible
for leg in LEGS:
    pts = [project(*p) for p in leg_points(leg)]
    if leg[0] == "walk":
        dashed(d, pts, (255, 255, 255, 235), WALK_W + 10)
    else:
        d.line(pts, fill=(255, 255, 255, 235), width=CASING, joint="curve")

# Pass 2: the colored route itself
for leg in LEGS:
    pts = [project(*p) for p in leg_points(leg)]
    c = MODE_COLOR[leg[0]]
    if leg[0] == "walk":
        dashed(d, pts, c, WALK_W)
    else:
        d.line(pts, fill=c, width=STROKE, joint="curve")

base = Image.alpha_composite(base.convert("RGBA"), overlay)
base.save("route_stage1.png")
print("stage 1 written", base.size)
