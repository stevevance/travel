"""Shared pieces for rendering the itinerary route onto tiled basemaps."""
import math
from PIL import Image, ImageDraw, ImageFont
from routes import load, stitch, slice_line, STOPS
from tiles import fetch, deg2num, TILE_PX

# Categorical by MODE: 3 slots, validated all-pairs (light) with the dataviz
# validator. Line identity rides on direct-labeled badges, never on hue alone.
METRO, TRAM, TRAIN, WALK = "#2a78d6", "#eb6834", "#1baf7a", "#5f5b54"
INK, INK_SOFT, PAPER = "#14201c", "#5a5346", "#f6f3ec"
MODE_COLOR = {"metro": METRO, "tram": TRAM, "train": TRAIN, "walk": WALK}

F_SERIF  = "/System/Library/Fonts/Supplemental/Georgia.ttf"
F_SERIFB = "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"
F_SANS   = "/System/Library/Fonts/HelveticaNeue.ttc"

def font(path, size, index=0):
    return ImageFont.truetype(path, size, index=index) if path.endswith(".ttc") \
        else ImageFont.truetype(path, size)

SANS   = lambda s: font(F_SANS, s, 0)
SANSB  = lambda s: font(F_SANS, s, 1)   # HelveticaNeue Bold face in the .ttc
SERIF  = lambda s: font(F_SERIF, s)
SERIFB = lambda s: font(F_SERIFB, s)

rels = load("routes_geom.json"); rels.update(load("train_geom.json"))
rels.update(load("ic_geom.json"))
LINES = {rid: stitch(r) for rid, r in rels.items()}

# (mode, badge, relation id or None for a walk, origin key, destination key)
LEGS = [
    ("metro", "E",  2777287, "meijersplein",  "denhaag_cs"),
    ("tram",  "9",  153659,  "denhaag_cs",    "bierkade"),
    ("walk",  None, None,    "bierkade",      "kerkplein"),
    ("tram",  "9",  153659,  "kerkplein",     "ov_museum"),
    ("tram",  "9",  1923134, "ov_museum",     "kurhaus"),
    ("walk",  None, None,    "kurhaus",       "summertime"),
    ("walk",  None, None,    "summertime",    "kurhaus"),
    ("tram",  "9",  153659,  "kurhaus",       "malieveld"),
    ("walk",  None, None,    "malieveld",     "koekamp"),
    ("walk",  None, None,    "koekamp",       "binnenhof"),
    ("walk",  None, None,    "binnenhof",     "grote_markt"),
    ("tram",  "1",  1862707, "grote_markt",   "prinsenhof"),
    ("walk",  None, None,    "prinsenhof",    "lakila"),
    ("walk",  None, None,    "lakila",        "delft_station"),
    ("train", "IC", 1323511, "delft_station", "rotterdam_cs"),
    ("tram",  "8",  3009652, "rotterdam_cs",  "wilgenlei"),
]

ORDER = [
    ("meijersplein",  "Meijersplein"),
    ("denhaag_cs",    "Den Haag Centraal"),
    ("bierkade",      "Bierkade"),
    ("kerkplein",     "Kerkplein"),
    ("ov_museum",     "HTM transport museum"),
    ("kurhaus",       "Kurhaus"),
    ("summertime",    "Summertime"),
    ("malieveld",     "Malieveld"),
    ("koekamp",       "Koekamp deer park"),
    ("binnenhof",     "Binnenhof"),
    ("grote_markt",   "Grote Markt"),
    ("prinsenhof",    "Prinsenhof"),
    ("lakila",        "Lakila"),
    ("delft_station", "Delft station"),
    ("rotterdam_cs",  "Rotterdam Centraal"),
    ("wilgenlei",     "Wilgenlei"),
]
# Short notes shown under a stop in the key. The origin has no arriving leg to
# describe it, so without one it reads as a bare place name.
NOTES = {
    "meijersplein": "Metro E station (RandstadRail), Rotterdam Schiebroek",
}

NUM = {k: i + 1 for i, (k, _) in enumerate(ORDER)}
NAME = dict(ORDER)

import json as _json
try:
    WALKS = {k: [tuple(p) for p in v] for k, v in _json.load(open("walks.json")).items()}
except FileNotFoundError:
    WALKS = {}

def leg_points(leg):
    """
    Real track geometry for a transit leg; routed footpaths for a walk.

    Transit legs return the track ALONE -- deliberately not anchored to the
    stop coordinates. Anchoring would draw a straight spur from, say, Kerkplein
    to the nearest rail, rendering tram line across streets that have none. The
    gap between a marker and its track is real (it is the walk to the platform)
    and access_connectors() draws it as a dashed walk instead.
    """
    _, _, rid, a, b = leg
    if rid is None:
        w = WALKS.get(f"{a}|{b}")
        return [STOPS[a]] + w + [STOPS[b]] if w else [STOPS[a], STOPS[b]]
    seg, _, _ = slice_line(LINES[rid], STOPS[a], STOPS[b])
    return seg

def access_connectors(min_m=90):
    """
    For each transit leg, the short hop between the stop marker and the point
    where its track actually starts or ends. Anything under min_m is close
    enough that drawing it would be clutter rather than information.
    """
    from routes import dist, nearest_index
    out = []
    for mode, badge, rid, a, b in LEGS:
        if rid is None:
            continue
        seg, _, _ = slice_line(LINES[rid], STOPS[a], STOPS[b])
        if not seg:
            continue
        for key, track_pt in ((a, seg[0]), (b, seg[-1])):
            d = dist(STOPS[key], track_pt)
            if d >= min_m:
                out.append({"stop": key, "m": round(d), "pts": [STOPS[key], track_pt]})
    return out

def dashed(draw, pts, color, width, dash, gap):
    """Polyline drawn as dashes, carrying leftover run length across vertices."""
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

class Panel:
    """One tiled map panel: basemap + projection + route drawing."""

    def __init__(self, bbox, zoom, name, ss=2):
        """ss = supersample factor; everything is drawn big then downscaled."""
        self.bbox, self.zoom, self.ss = bbox, zoom, ss
        self.meta = fetch(bbox, zoom, f"base_{name}.png")
        img = Image.open(f"base_{name}.png").convert("RGB")
        self.w, self.h = img.size[0] * ss, img.size[1] * ss
        img = img.resize((self.w, self.h), Image.LANCZOS)
        # Desaturate and fade so the route reads as figure, the map as ground
        img = Image.blend(img.convert("L").convert("RGB"), img, 0.45)
        self.img = Image.blend(img, Image.new("RGB", img.size, "#ffffff"), 0.42)
        self.overlay = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.overlay)

    def project(self, lat, lon):
        m, ss = self.meta, self.ss
        n = 2.0 ** m["zoom"]
        x = (lon + 180.0) / 360.0 * n
        y = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n
        return (((x - m["x0"]) * TILE_PX - m["crop"][0]) * ss,
                ((y - m["y0"]) * TILE_PX - m["crop"][1]) * ss)

    def draw_routes(self, stroke=9, casing=17, walk_w=7):
        """Two passes: a white casing under everything, then the colored line,
        so the many crossings in Den Haag centrum stay readable."""
        s = self.ss
        stroke, casing, walk_w = stroke * s, casing * s, walk_w * s
        for leg in LEGS:
            pts = [self.project(*p) for p in leg_points(leg)]
            if leg[0] == "walk":
                dashed(self.d, pts, (255, 255, 255, 240), walk_w + 7 * s, 13 * s, 9 * s)
            else:
                self.d.line(pts, fill=(255, 255, 255, 240), width=casing, joint="curve")
        for leg in LEGS:
            pts = [self.project(*p) for p in leg_points(leg)]
            c = MODE_COLOR[leg[0]]
            if leg[0] == "walk":
                dashed(self.d, pts, c, walk_w, 13 * s, 9 * s)
            else:
                self.d.line(pts, fill=c, width=stroke, joint="curve")

    def marker(self, key, r=15):
        """Numbered dot: white disc, mode-colored ring, number inside."""
        s = self.ss
        x, y = self.project(*STOPS[key])
        r = r * s
        mode = ARRIVE[key]
        self.d.ellipse([x - r, y - r, x + r, y + r], fill="#ffffff",
                       outline=MODE_COLOR[mode], width=max(3, int(3.2 * s)))
        n = str(NUM[key])
        f = SANSB(int(r * 1.15))
        bb = self.d.textbbox((0, 0), n, font=f)
        self.d.text((x - (bb[2] - bb[0]) / 2 - bb[0], y - (bb[3] - bb[1]) / 2 - bb[1]),
                    n, font=f, fill=INK)
        return x, y

    def label(self, key, dx, dy, size=17, anchor="lm"):
        """Stop name in a soft white pill so it survives a busy basemap."""
        s = self.ss
        x, y = self.project(*STOPS[key])
        tx, ty = x + dx * s, y + dy * s
        f = SANSB(int(size * s))
        txt = NAME[key]
        bb = self.d.textbbox((tx, ty), txt, font=f, anchor=anchor)
        pad = 5 * s
        self.d.rounded_rectangle([bb[0] - pad, bb[1] - pad * 0.7, bb[2] + pad, bb[3] + pad * 0.7],
                                 radius=5 * s, fill=(255, 255, 255, 228))
        self.d.text((tx, ty), txt, font=f, fill=INK, anchor=anchor)

    def badge(self, latlon, text, mode, size=16):
        """Line-number chip placed on the route: the secondary encoding that
        carries identity, since three hues can't stand for five lines."""
        s = self.ss
        x, y = self.project(*latlon)
        f = SANSB(int(size * s))
        bb = self.d.textbbox((0, 0), text, font=f)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        pad = 7 * s
        box = [x - tw / 2 - pad, y - th / 2 - pad * 0.85,
               x + tw / 2 + pad, y + th / 2 + pad * 0.85]
        self.d.rounded_rectangle(box, radius=5 * s, fill=MODE_COLOR[mode],
                                 outline="#ffffff", width=max(2, int(2.2 * s)))
        self.d.text((x - tw / 2 - bb[0], y - th / 2 - bb[1]), text, font=f, fill="#ffffff")

    def finish(self, target_w=None):
        out = Image.alpha_composite(self.img.convert("RGBA"), self.overlay).convert("RGB")
        if target_w:
            out = out.resize((target_w, int(out.height * target_w / out.width)), Image.LANCZOS)
        return out

# Mode of ARRIVAL at each stop, which sets its ring color
ARRIVE = {
    "summertime": "walk",
    "meijersplein": "metro", "denhaag_cs": "metro", "bierkade": "tram",
    "kerkplein": "walk", "ov_museum": "tram", "kurhaus": "tram",
    "malieveld": "tram", "koekamp": "walk", "binnenhof": "walk", "grote_markt": "walk", "prinsenhof": "tram",
    "lakila": "walk", "delft_station": "walk",
    "rotterdam_cs": "train", "wilgenlei": "tram",
}
