"""Build prague-map.html: three nights in Prague, 27 to 30 September 2026.

In off the EC from Dresden late on the Sunday; Petřín, the castle by tram and
the National Museum on the Monday; Letná, the National Technical Museum and
the Old Town on the Tuesday; the Airport Express out on the Wednesday morning.

Where each line comes from:

  gps      the six Strava walks of 28 and 29 September, in data/prague/
  gtfs     every tram, metro and bus leg, cut from PID's own GTFS feed by
           gtfs_lines.py into data/prague/transit.geojson. Not OSM, as on the
           other maps: OSM's AE relation is the bus's old route, 670 m from
           where the photographs put it
  routed   the walks nobody recorded, through where the day's photographs
           were taken; drawn dotted like every walk

    python3 src/prague/gtfs_lines.py    # once, or when a transit leg changes
    python3 src/prague/build.py         # -> prague-map.html
"""
import json, math, os, sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from osm import HERE, ROOT, dist, length_m, valhalla

sys.setrecursionlimit(10000)          # rdp recurses once per retained point

DATADIR = os.path.join(ROOT, "data", "prague")
OUT     = os.path.join(ROOT, "prague-map.html")
CEST    = timezone(timedelta(hours=2))    # Strava stamps UTC; Prague was CEST
RDP_M   = 1.5

TRANSIT = {f["properties"]["key"]: f for f in
           json.load(open(os.path.join(DATADIR, "transit.geojson")))["features"]}
def stop_of(key, end):
    lon, lat = TRANSIT[key]["properties"][end + "_pt"]
    return (lat, lon)

# ------------------------------------------------------------------ stops ---
# All public places. The hotel is a business but is not named, and its stop is
# Masarykovo nádraží round the corner, where every day started and ended.
STOPS = {
    "hln":         (50.083300, 14.435300),
    "masaryk":     (50.087900, 14.435200),
    "powder":      (50.087400, 14.427800),   # the Powder Tower
    "lazarska":    stop_of("mon_tram_out", "from"),
    "ujezd":       stop_of("mon_tram_out", "to"),
    "petrin":      (50.083420, 14.394900),
    "pohorelec":   stop_of("mon_tram_castle", "from"),
    "malostranska":stop_of("mon_tram_castle", "to"),
    "palach":      (50.088900, 14.415500),   # náměstí Jana Palacha, the Rudolfinum
    "m_malostr":   stop_of("mon_metro_a", "from"),
    "muzeum":      stop_of("mon_metro_a", "to"),
    "natmuseum":   (50.079000, 14.430700),   # the historic building
    "melantrich":  (50.085830, 14.419760),   # where the evening walk starts
    "pravnicka":   stop_of("mon_tram_river", "from"),
    "jiraskovo":   stop_of("mon_tram_river", "to"),
    "karlovo":     stop_of("mon_metro_b", "from"),
    "republiky":   stop_of("mon_metro_b", "to"),
    "lokal":       (50.090670, 14.425760),   # Lokál Dlouhááá
    "metronom":    (50.094070, 14.416380),
    "ntm":         (50.097240, 14.424960),   # National Technical Museum
    "agri":        (50.096860, 14.423280),   # National Museum of Agriculture
    "oldsq":       (50.087320, 14.421020),
    "charles":     (50.086480, 14.411580),
    "karlovo_sq":  (50.077560, 14.421170),   # the park, by the Hálek statue
    "churchill":   (50.084870, 14.440440),   # where the grocery walk starts
    "hln_ae":      stop_of("wed_ae", "from"),
    "t2":          stop_of("wed_ae", "to"),
}

ORDER = [
    ("hln",          "Praha hlavní nádraží"),
    ("masaryk",      "Masarykovo nádraží, by the hotel"),
    ("powder",       "The Powder Tower"),
    ("lazarska",     "Lazarská"),
    ("ujezd",        "Újezd"),
    ("petrin",       "Petřín Lookout Tower"),
    ("pohorelec",    "Pohořelec"),
    ("malostranska", "Malostranská"),
    ("palach",       "Náměstí Jana Palacha"),
    ("m_malostr",    "Malostranská metro"),
    ("muzeum",       "Muzeum metro"),
    ("natmuseum",    "National Museum"),
    ("melantrich",   "Melantrichova"),
    ("pravnicka",    "Právnická fakulta"),
    ("jiraskovo",    "Jiráskovo náměstí"),
    ("karlovo",      "Karlovo náměstí metro"),
    ("republiky",    "Náměstí Republiky metro"),
    ("lokal",        "Lokál Dlouhááá"),
    ("metronom",     "The Metronome, Letná"),
    ("ntm",          "National Technical Museum"),
    ("agri",         "National Museum of Agriculture"),
    ("oldsq",        "Old Town Square"),
    ("charles",      "Charles Bridge"),
    ("karlovo_sq",   "Karlovo náměstí"),
    ("churchill",    "Churchill Square"),
    ("hln_ae",       "Hlavní nádraží, the AE stop"),
    ("t2",           "Letiště, Terminál 2"),
]
NUM  = {k: i + 1 for i, (k, _) in enumerate(ORDER)}
NAME = dict(ORDER)
NOTES = {
    "hln":         "In off the EC from Dresden at about 22:05 on Sunday",
    "masaryk":     "The hotel was round the corner; every day starts and ends "
                   "here",
    "powder":      "Monday, 12:58",
    "lazarska":    "Onto the tram, about 13:13",
    "ujezd":       "Off at 13:19, at the foot of Petřín",
    "petrin":      "Up the tower, 13:50 to 14:15",
    "pohorelec":   "Onto the 22 at about 14:46",
    "malostranska":"Off the tram by 14:55",
    "palach":      "Over the Mánesův most to the Rudolfinum, 15:03, and back",
    "m_malostr":   "Down into line A after 15:21",
    "muzeum":      "Up at 15:55",
    "natmuseum":   "Both buildings and the dome, about 15:55 to 17:53",
    "melantrich":  "A McFlurry on the way here; the walk starts 18:20",
    "pravnicka":   "Onto the 17 at about 18:53",
    "jiraskovo":   "By the river, 18:59",
    "karlovo":     "Line B from Palackého náměstí, after 19:31",
    "republiky":   "Up the escalator at 19:43",
    "lokal":       "Dinner, 20:04 to about 21:15",
    "metronom":    "Tuesday, 11:48",
    "ntm":         "12:16 to 14:14",
    "agri":        "Next door, to about 14:49; down the hill at 15:14",
    "oldsq":       "16:07",
    "charles":     "16:22 to 16:30",
    "karlovo_sq":  "17:20 to 17:51",
    "churchill":   "Tuesday evening's grocery walk starts here, 20:46",
    "hln_ae":      "Wednesday, about 07:15",
    "t2":          "In by about 07:50, for the flight to Munich",
}
ARRIVE = {
    "hln": "train", "masaryk": "walk", "powder": "walk", "lazarska": "walk",
    "ujezd": "tram", "petrin": "walk", "pohorelec": "walk",
    "malostranska": "tram", "palach": "walk", "m_malostr": "walk",
    "muzeum": "metro", "natmuseum": "walk", "melantrich": "walk",
    "pravnicka": "walk", "jiraskovo": "tram", "karlovo": "walk",
    "republiky": "metro", "lokal": "walk", "metronom": "walk", "ntm": "walk",
    "agri": "walk", "oldsq": "walk", "charles": "walk", "karlovo_sq": "walk",
    "churchill": "walk", "hln_ae": "walk", "t2": "bus",
}

# --------------------------------------------------------------- the legs ---
# (seq, day, kind, a, b, mode, label, note, extra). kind is "gtfs" (extra is
# the key in transit.geojson), "walk" (extra is a list of through-points for
# Valhalla, mostly photographs), or "gps" (extra is the recording's file name).
LEGS = [
    # Sunday 27
    (10, "sun", "walk", "hln", "masaryk", "walk", "Walk",
     "To the hotel; Masarykovo nádraží at 22:26", []),
    # Monday 28
    (110, "mon", "walk", "masaryk", "powder", "walk", "Walk",
     "Along the Hybernská", [(50.08741, 14.43247)]),
    (120, "mon", "walk", "powder", "lazarska", "walk", "Walk",
     "Down Na Příkopě, 13:06", [(50.08549, 14.42964)]),
    (130, "mon", "gtfs", "lazarska", "ujezd", "tram", "Tram 9",
     "Over the Most Legií at 13:17. Which line is not remembered; the 9 runs "
     "it, and so do others", "mon_tram_out"),
    (140, "mon", "gps", "ujezd", "petrin", "walk", "Walk",
     "Up through the Petřín gardens", "Afternoon_Walk.gpx"),
    (150, "mon", "gps", "petrin", "pohorelec", "walk", "Walk",
     "Along the hill past the Strahov Monastery", "Afternoon_Hike.gpx"),
    (160, "mon", "gtfs", "pohorelec", "malostranska", "tram", "Tram 22",
     "Past the Royal Garden at 14:51 and down the Chotkova", "mon_tram_castle"),
    (170, "mon", "walk", "malostranska", "palach", "walk", "Walk",
     "Over the Mánesův most", []),
    (180, "mon", "walk", "palach", "m_malostr", "walk", "Walk",
     "Back over the bridge", []),
    (190, "mon", "gtfs", "m_malostr", "muzeum", "metro", "Metro A",
     "Under the river and the Old Town", "mon_metro_a"),
    (200, "mon", "walk", "muzeum", "natmuseum", "walk", "Walk", "", []),
    (210, "mon", "walk", "natmuseum", "melantrich", "walk", "Walk",
     "Down Wenceslas Square to Můstek, 18:01", [(50.08311, 14.42512)]),
    (220, "mon", "gps", "melantrich", "pravnicka", "walk", "Walk",
     "Old Town Square, the Old-New Synagogue and up to the Metronome",
     "Post_McFlurry_and_Pre_Dinner_walk.gpx"),
    (230, "mon", "gtfs", "pravnicka", "jiraskovo", "tram", "Tram 17",
     "South along the embankment", "mon_tram_river"),
    (240, "mon", "walk", "jiraskovo", "karlovo", "walk", "Walk",
     "Along the river to Palackého náměstí, 19:27", [(50.07412, 14.41363)]),
    (250, "mon", "gtfs", "karlovo", "republiky", "metro", "Metro B",
     "", "mon_metro_b"),
    (260, "mon", "gps", "republiky", "lokal", "walk", "Walk",
     "To dinner", "Metro_station_to_restaurant_Lokal_.gpx"),
    (270, "mon", "walk", "lokal", "masaryk", "walk", "Walk",
     "Back by Náměstí Republiky, 21:22", [(50.08832, 14.42879)]),
    # Tuesday 29
    (310, "tue", "walk", "masaryk", "metronom", "walk", "Walk",
     "Across the Old Town and up the steps from the Čechův most",
     [(50.08979, 14.42796), (50.09180, 14.41790)]),
    (320, "tue", "gps", "metronom", "ntm", "walk", "Walk",
     "Along the top of Letná",
     "Letná_park_walk_from_Metronom_to_National_Technical_Museum.gpx"),
    (330, "tue", "walk", "ntm", "agri", "walk", "Walk", "Next door", []),
    (340, "tue", "walk", "agri", "oldsq", "walk", "Walk",
     "Down the hill and over the Štefánikův most, 15:20",
     [(50.09550, 14.42550), (50.09292, 14.42721), (50.09048, 14.42572)]),
    (350, "tue", "walk", "oldsq", "charles", "walk", "Walk",
     "By Mariánské náměstí and the Clementinum", [(50.08703, 14.41741)]),
    (360, "tue", "walk", "charles", "karlovo_sq", "walk", "Walk",
     "Down to Národní třída, 16:48, and south",
     [(50.08262, 14.41474), (50.08230, 14.41910), (50.07918, 14.41991)]),
    (370, "tue", "walk", "karlovo_sq", "masaryk", "walk", "Walk",
     "Not remembered: the next photograph is at the Powder Tower at 19:01, "
     "so this is a walk there and on", [(50.08727, 14.42854)]),
    (380, "tue", "walk", "masaryk", "churchill", "walk", "Walk", "",
     [(50.08624, 14.43798)]),
    (390, "tue", "gps", "churchill", "masaryk", "walk", "Walk",
     "The grocery store crawl", "Grocery_store_crawl.gpx"),
    # Wednesday 30
    (410, "wed", "walk", "masaryk", "hln_ae", "walk", "Walk",
     "To the main station for the bus", []),
    (420, "wed", "gtfs", "hln_ae", "t2", "bus", "Airport Express",
     "Over the Štefánikův most at 07:26, through Dejvice at 07:32 and out "
     "along the Evropská", "wed_ae"),
]
DAY = {"sun": "Sunday 27", "mon": "Monday 28", "tue": "Tuesday 29",
       "wed": "Wednesday 30"}

# --------------------------------------------------------------- geometry ---
def read_gpx(path):
    if not os.path.exists(path):
        raise SystemExit(
            f"missing {path}\n"
            "The Strava exports are deliberately not in git. Drop the six "
            "2026-09-28 and 2026-09-29 .gpx files back into data/prague/ to "
            "rebuild.")
    NS = "{http://www.topografix.com/GPX/1/1}"
    root = ET.parse(path).getroot()
    return [(float(p.get("lat")), float(p.get("lon")),
             datetime.strptime(p.findtext(NS + "time"), "%Y-%m-%dT%H:%M:%SZ")
             .replace(tzinfo=timezone.utc).astimezone(CEST))
            for p in root.iter(NS + "trkpt")]

def trim_loitering(pts, R=20.0):
    """Drop the standing-around at each end of a recording; see Alphen."""
    i = max(k for k in range(len(pts)) if dist(pts[0][:2], pts[k][:2]) < R
            and all(dist(pts[0][:2], q[:2]) < R for q in pts[:k + 1]))
    j = min(k for k in range(len(pts)) if dist(pts[-1][:2], pts[k][:2]) < R
            and all(dist(pts[-1][:2], q[:2]) < R for q in pts[k:]))
    return pts[i:j + 1]

def rdp(pts, eps):
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

# ---------------------------------------------------------------- collect ---
features = []
def add(seq, day, mode, a, b, pts, source, line, note, ride=None, km=None):
    features.append({
        "type": "Feature",
        "properties": {
            "seq": seq, "day": day, "mode": mode,
            "from": NAME[a], "to": NAME[b], "from_n": NUM[a], "to_n": NUM[b],
            "line": line,
            "km": round((km if km is not None else length_m([p[:2] for p in pts])) / 1000, 2),
            "source": source, "note": note,
            **({"ride": ride} if ride else {}),
        },
        "geometry": {"type": "LineString",
                     "coordinates": [[round(p[1], 6), round(p[0], 6)] for p in pts]},
    })
    p = features[-1]["properties"]
    print(f"  {seq:4d} {mode:6s} {NAME[a][:24]:26s}-> {NAME[b][:24]:26s}"
          f"{p['km']:7.2f} km {len(pts):5d} pts [{source}]")

for seq, day, kind, a, b, mode, line, note, extra in LEGS:
    if kind == "gtfs":
        pts = [(lat, lon) for lon, lat in TRANSIT[extra]["geometry"]["coordinates"]]
        add(seq, day, mode, a, b, pts, "gtfs", line, note)
    elif kind == "walk":
        pts = [STOPS[a]] + list(extra) + [STOPS[b]]
        shape, m = valhalla(pts, "pedestrian", f"walk_{seq}.json")
        add(seq, day, mode, a, b, shape, "routed", line, note, km=m)
    elif kind == "gps":
        raw = read_gpx(os.path.join(DATADIR, extra))
        pts = trim_loitering(raw)
        print(f"       {extra}: {len(raw)} fixes, {pts[0][2]:%H:%M}-"
              f"{pts[-1][2]:%H:%M}, {length_m([p[:2] for p in raw])/1000:.2f} km")
        add(seq, day, mode, a, b, rdp(pts, RDP_M), "gps", line,
            f"{pts[0][2]:%H:%M} to {pts[-1][2]:%H:%M}. {note}",
            ride=f"ride{seq}")

# ----------------------------------------------------------------- output ---
stops_fc = {"type": "FeatureCollection", "features": [
    {"type": "Feature",
     "properties": {"n": NUM[k], "name": n, "arrive": ARRIVE[k], "key": k,
                    "note": NOTES.get(k, "")},
     "geometry": {"type": "Point",
                  "coordinates": [round(STOPS[k][1], 6), round(STOPS[k][0], 6)]}}
    for k, n in ORDER]}
features.sort(key=lambda f: f["properties"]["seq"])
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
print(f"wrote {OUT}, {len(tpl)} bytes")
