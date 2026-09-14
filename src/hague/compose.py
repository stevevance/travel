"""Compose the overview and the three detail insets into one static sheet."""
from PIL import Image, ImageDraw, ImageFont

S = 2  # laid out in logical px, drawn at 2x
PAPER, INK, SOFT, LINE = "#f6f3ec", "#14201c", "#5a5346", "#c9c1ae"
G  = "/System/Library/Fonts/Supplemental/Georgia.ttf"
GB = "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"
GI = "/System/Library/Fonts/Supplemental/Georgia Italic.ttf"
f = lambda p, s: ImageFont.truetype(p, int(s * S))

ov = Image.open("shot_overview.png")
INSETS = [
    ("shot_denhaag.png",      "Den Haag centrum",  "stops 2–11"),
    ("shot_scheveningen.png", "Scheveningen",      "stops 6–7"),
    ("shot_delft.png",        "Delft centrum",     "stops 12–14"),
]

M, GAP, HEAD, CAP, FOOT = 34, 24, 92, 30, 46
ov_w, ov_h = ov.width // S, ov.height // S
imgs = [(Image.open(p), t, sub) for p, t, sub in INSETS]
right_w = max(i.width // S for i, _, _ in imgs)
right_h = sum(CAP + i.height // S for i, _, _ in imgs) + GAP * (len(imgs) - 1)

W = M + ov_w + GAP + right_w + M
content_h = max(ov_h, right_h)
H = M + HEAD + content_h + FOOT + M

canvas = Image.new("RGB", (W * S, H * S), PAPER)
d = ImageDraw.Draw(canvas)
def text(x, y, s, font, fill=INK, anchor="la"):
    d.text((x * S, y * S), s, font=font, fill=fill, anchor=anchor)

text(M, M - 4, "A day out from Rotterdam", f(GI, 15), "#2f5d5a")
text(M, M + 18, "The Hague and Delft, by metro, tram and train", f(GB, 30))

y0 = M + HEAD
def framed(img, x, y):
    w, h = img.width // S, img.height // S
    canvas.paste(img, (x * S, y * S))
    d.rectangle([x * S, y * S, (x + w) * S - 1, (y + h) * S - 1], outline=LINE, width=S)
    return h

framed(ov, M, y0)

rx, ry = M + ov_w + GAP, y0
for img, title, sub in imgs:
    text(rx, ry + 2, title, f(GB, 16))
    text(rx + right_w, ry + 4, sub, f(G, 13), SOFT, anchor="ra")
    ry += CAP + framed(img, rx, ry + CAP) + GAP

fy = M + HEAD + content_h + 16
d.line([M * S, (fy - 9) * S, (W - M) * S, (fy - 9) * S], fill=LINE, width=S)
text(M, fy, "Rail and tram alignments are the actual OpenStreetMap route relations for HTM tram 1 and 9, RET tram 8 "
            "and metro E, and the NS Intercity; every walking leg is routed on the pedestrian network.", f(G, 12), SOFT)
text(M, fy + 18, "Stop 6 is the Kurhaus tram stop: the walk out to Summertime goes through the hotel, the walk back "
                 "climbs the covered stairs northeast of it. Dotted spurs elsewhere are the short walk from a stop to "
                 "its platform.", f(G, 12), SOFT)
text(M, fy + 36, "Basemap: OpenFreeMap · OpenMapTiles · OpenStreetMap.", f(G, 12), SOFT)

canvas.save("hague-transport-map.png")
print("wrote hague-transport-map.png", canvas.size)
