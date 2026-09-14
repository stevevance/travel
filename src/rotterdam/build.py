"""Build today's Rotterdam route: tram 8, three bike legs, four walks."""
import json, math, time, urllib.parse, urllib.request

UA = {"User-Agent": "steven-personal-itinerary-map/1.0"}
VALHALLA = "https://valhalla1.openstreetmap.de/route"

# ---------------------------------------------------------------- stops -----
# Tram stop positions come from today's RET GTFS, not OSM: RET renamed the stop
# OSM still calls "Schiekade" to Provenierssingel, and tram 8 is on a Hofplein
# diversion that terminates at Blijdorp instead of Spangen.
STOPS = {
    "teldersweg":      (51.952657, 4.469193),
    "provenierssingel":(51.928108, 4.472558),
    "oasis":           (51.930050, 4.480540),
    "round_round":     (51.922770, 4.493050),
    # The bikes were 25 m north of Koestraat x Haringvliet, not at the cafe
    "bikes":           (51.920138, 4.493547),
    "fenixplein":      (51.902040, 4.485469),  # bike parked and collected here
    "fenix":           (51.902080, 4.484320),
    "kaapse":          (51.902070, 4.486650),
    "mobrigado":       (51.926540, 4.486480),
    "noahs":           (51.931560, 4.482630),
    # Second bike, collected across the road from the Wolly cafe
    "bikes2":          (51.930779, 4.485700),
    # The route is drawn to the Wilgenlei/Ringdijk corner, a public street junction.
    "wilgenlei":       (51.953410, 4.476890),
}
ORDER = [
    ("teldersweg",       "Teldersweg"),
    ("provenierssingel", "Provenierssingel"),
    ("oasis",            "Oasis"),
    ("round_round",      "Round & Round"),
    ("bikes",            "Bikes"),
    ("fenixplein",       "Fenix Plein"),
    ("fenix",            "Fenix museum"),
    ("kaapse",           "Kaapse Brouwers"),
    ("mobrigado",        "Mobrigado"),
    ("noahs",            "Noah's Bakery"),
    ("bikes2",           "Bikes again"),
    ("wilgenlei",        "Wilgenlei"),
]
NUM  = {k: i + 1 for i, (k, _) in enumerate(ORDER)}
NAME = dict(ORDER)
NOTES = {
    "teldersweg":       "Tram 8 stop, Schiebroek",
    "provenierssingel": "Tram 8 stop behind Rotterdam Centraal",
    "oasis":            "Restaurant, formerly Mecca",
    "kaapse":           "At the Fenix Food Factory, Katendrecht",
    "fenixplein":       "Parked the bikes here, and picked them up again",
    "bikes":            "Picked up the bikes, 25 m north of Koestraat",
    "wilgenlei":        "Home stretch, at Ringdijk",
    "bikes2":           "Second bikes, across the road from Wolly",
}

# Waypoints that force a leg onto the bridges and streets actually used
VIA = {
    ("bikes", "fenixplein"):    [(51.919145, 4.486481),   # Blaak
                                 (51.914978, 4.481743),   # Schiedamsedijk
                                 (51.905901, 4.487399),   # Wilhelminakade
                                 (51.903160, 4.485930)],  # Rijnhavenbrug
    ("fenixplein", "mobrigado"):[(51.913070, 4.497590),   # Koninginnebrug
                                 (51.916820, 4.496180)],  # Willemsbrug
    ("mobrigado", "noahs"):     [(51.930040, 4.485970)],  # Noorderbrug
    ("bikes2", "wilgenlei"):    [(51.938461, 4.485444),   # Zwaanshals x Soetendaalsekade
                                 (51.944470, 4.478680),   # Juliana van Stolberglaan
                                 (51.952380, 4.476540)],  # Ringdijk
}

# (mode, from, to)
LEGS = [
    ("tram", "teldersweg",       "provenierssingel"),
    ("walk", "provenierssingel", "oasis"),
    ("walk", "oasis",            "round_round"),
    ("walk", "round_round",      "bikes"),
    ("bike", "bikes",            "fenixplein"),
    ("walk", "fenixplein",       "fenix"),
    ("walk", "fenix",            "kaapse"),
    ("walk", "kaapse",           "fenixplein"),
    ("bike", "fenixplein",       "mobrigado"),
    ("walk", "mobrigado",        "noahs"),
    ("walk", "noahs",            "bikes2"),
    ("bike", "bikes2",           "wilgenlei"),
]
ARRIVE = {"teldersweg": "tram", "provenierssingel": "tram", "oasis": "walk",
          "round_round": "walk", "bikes": "walk", "fenixplein": "bike", "fenix": "walk", "kaapse": "walk",
          "mobrigado": "bike", "noahs": "walk", "bikes2": "walk", "wilgenlei": "bike"}

def dist(a, b):
    dy = (a[0]-b[0])*111320.0
    dx = (a[1]-b[1])*111320.0*math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)

def length_m(pts):
    return sum(dist(pts[i], pts[i+1]) for i in range(len(pts)-1))

def decode6(s):
    coords, lat, lon, i = [], 0, 0, 0
    while i < len(s):
        for who in range(2):
            shift = result = 0
            while True:
                b = ord(s[i]) - 63; i += 1
                result |= (b & 0x1f) << shift; shift += 5
                if b < 0x20: break
            d = ~(result >> 1) if result & 1 else (result >> 1)
            if who == 0: lat += d
            else: lon += d
        coords.append((lat/1e6, lon/1e6))
    return coords

def route(pts, costing):
    locs = [{"lat": p[0], "lon": p[1],
             "type": "break" if i in (0, len(pts)-1) else "through"}
            for i, p in enumerate(pts)]
    body = {"locations": locs, "costing": costing,
            "directions_options": {"units": "kilometers"}}
    req = urllib.request.Request(
        VALHALLA + "?json=" + urllib.parse.quote(json.dumps(body)), headers=UA)
    d = json.load(urllib.request.urlopen(req, timeout=45))
    out = []
    for lg in d["trip"]["legs"]:
        out.extend(decode6(lg["shape"]))
    return out, d["trip"]["summary"]["length"] * 1000

# ------------------------------------------------- tram 8 track geometry ----
def stitch(rel):
    ways = [m["geometry"] for m in rel["members"]
            if m["type"] == "way" and m.get("role", "") == "" and "geometry" in m]
    line = [(p["lat"], p["lon"]) for p in ways[0]]
    for w in ways[1:]:
        pts = [(p["lat"], p["lon"]) for p in w]
        if dist(line[-1], pts[-1]) < dist(line[-1], pts[0]):
            pts.reverse()
        line.extend(pts)
    return line

rel = json.load(open("tram8.json"))["elements"][0]
tram_line = stitch(rel)
def nearest(line, pt):
    best, bi = 1e18, 0
    for i, p in enumerate(line):
        d = dist(p, pt)
        if d < best: best, bi = d, i
    return bi, best

i, di = nearest(tram_line, STOPS["teldersweg"])
j, dj = nearest(tram_line, STOPS["provenierssingel"])
tram_seg = tram_line[i:j+1] if i <= j else list(reversed(tram_line[j:i+1]))
print(f"tram 8 slice: {len(tram_seg)} pts, snaps {di:.0f} m / {dj:.0f} m, "
      f"{length_m(tram_seg)/1000:.2f} km")

# ------------------------------------------------------------ build legs ----
features = []
for mode, a, b in LEGS:
    if mode == "tram":
        pts = tram_seg
        km = length_m(pts) / 1000
    else:
        costing = "bicycle" if mode == "bike" else "pedestrian"
        via = VIA.get((a, b), [])
        pts, m = route([STOPS[a]] + via + [STOPS[b]], costing)
        km = m / 1000
        time.sleep(0.8)
    features.append({
        "type": "Feature",
        "properties": {"mode": mode, "from": NAME[a], "to": NAME[b],
                       "from_n": NUM[a], "to_n": NUM[b],
                       "line": {"tram": "Tram 8", "bike": "Bike", "walk": "Walk"}[mode],
                       "km": round(km, 2)},
        "geometry": {"type": "LineString",
                     "coordinates": [[round(p[1], 6), round(p[0], 6)] for p in pts]},
    })
    print(f"  {mode:5s} {NAME[a]:20s} -> {NAME[b]:20s} {km:5.2f} km  {len(pts):4d} pts")

stops_fc = {"type": "FeatureCollection", "features": [
    {"type": "Feature",
     "properties": {"n": NUM[k], "name": n, "arrive": ARRIVE[k],
                    "key": k, "note": NOTES.get(k, "")},
     "geometry": {"type": "Point",
                  "coordinates": [round(STOPS[k][1], 6), round(STOPS[k][0], 6)]}}
    for k, n in ORDER]}

json.dump({"type": "FeatureCollection", "features": features},
          open("rtd_lines.geojson", "w"))
json.dump(stops_fc, open("rtd_stops.geojson", "w"))

tot = {}
for f in features:
    p = f["properties"]; tot[p["mode"]] = tot.get(p["mode"], 0) + p["km"]
print("\ntotals:", ", ".join(f"{k} {v:.2f} km" for k, v in sorted(tot.items())))
print(f"total distance {sum(tot.values()):.2f} km")
