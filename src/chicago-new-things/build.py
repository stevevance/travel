"""Build the Chicago "new things" ride: twelve stops, north and west of downtown.

The odd one out in this repo in three ways, and all three are worth saying out
loud rather than discovering from the diff:

  - It is at home, not on the trip. Every other page here is a day somewhere in
    Europe in September 2026; this is Chicago.
  - Nothing has happened yet. There is no recording and no day to trace: it is a
    route planned around twelve places that are in the news or hold a new
    construction permit. Every leg is therefore `source: "routed"`, which
    map-common.js draws dashed, so the line cannot pass for a measurement.
  - Its stops are not places to see so much as things being built. The two stop
    glyphs - a building and a newspaper - say which kind each one is, because
    the whole ride is one mode and so colour has nothing left to distinguish.

Distances print in miles: `units: 'imperial'` in the template, which switches the
scale bar and every number in the key together.

    python3 src/chicago-new-things/build.py   # -> chicago-new-things-map.html

Valhalla responses are cached next to this file and gitignored, so deleting them
only costs a re-fetch.
"""
import json, math, os, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
VALHALLA = "https://valhalla1.openstreetmap.de/route"
UA = {"User-Agent": "steven-personal-itinerary-map/1.0 (personal travel notes)"}

# ------------------------------------------------------------------ stops ---
# Twelve places, in the order the ride visits them: West Loop and West Town,
# out to Humboldt Park, north through Ukrainian Village to Logan Square and
# Lakeview, then back down through Lincoln Park.
#
# `kind` is "permit" for a site with an issued new construction permit and
# "news" for somewhere a story has been written about. A permit's coordinate is
# the address on the permit; a news story's is approximate, because a story is
# about a project or a block rather than a point, and the ones that say "~" in
# their address line are the loosest of all.
STOPS = [
 dict(key="geothermal", kind="news",
      lat=41.889211, lng=-87.659674,
      name="Geothermal apartment tower, West Loop",
      where="~Halsted & Monroe, West Loop",
      detail="Chicago's first all-electric geothermal apartment tower. "
             "Developers broke ground in July 2026.",
      source="Chicago Sun-Times",
      link="https://chicago.suntimes.com/real-estate/2026/07/28/developers-break-ground-on-chicagos-first-all-electric-geothermal-apartment-tower"),
 dict(key="grand1334", kind="permit",
      lat=41.891157, lng=-87.660465,
      name="1334 W Grand Ave, nine units and retail",
      where="1334 W Grand Ave, West Town",
      detail="Four storeys, nine dwelling units over ground floor retail, a "
             "nine-car garage and a rooftop deck. Fully sprinklered.",
      source="Permit issued 22 September 2026",
      link="https://www.chicagocityscape.com/permits.php?pid=3454373"),
 dict(key="christiana1033", kind="permit",
      lat=41.900214, lng=-87.710391,
      name="1033 N Christiana Ave, 40 units",
      where="1033 N Christiana Ave, Humboldt Park",
      detail="Five storeys and 40 dwelling units over a basement, with a "
             "21-car garage, decks, balconies, a lift and 40 bicycle spaces.",
      source="Permit issued 7 August 2026",
      link="https://www.chicagocityscape.com/permits.php?pid=3444527"),
 dict(key="vonhumboldt", kind="news",
      lat=41.907131, lng=-87.692690,
      name="Von Humboldt School, becoming housing",
      where="Von Humboldt School, Humboldt Park",
      detail="The long-awaited conversion of the closed school into "
             "affordable housing, after the project secured city funding.",
      source="Block Club Chicago",
      link="https://blockclubchicago.org/2026/09/29/von-humboldt-school-to-finally-become-affordable-housing-after-project-secures-city-funding/"),
 dict(key="belloakley", kind="permit",
      lat=41.909660, lng=-87.684150,
      name="Bell and Oakley, 28 units on one block face",
      where="1532-1541 N Bell and N Oakley, Ukrainian Village",
      detail="Four seven-unit buildings on a single block face - 1532 and "
             "1540 N Bell, 1535 and 1541 N Oakley - all permitted on the same "
             "day. Rooftop decks, pergolas and detached garages.",
      source="Permits issued 1 September 2026",
      link="https://www.chicagocityscape.com/permits.php?pid=3446889"),
 dict(key="trailhead606", kind="news",
      lat=41.913647, lng=-87.687814,
      name="Trailhead apartments on The 606",
      where="~The 606, Wicker Park",
      detail="The trailhead apartments change hands, in a test of the "
             "anti-deconversion and anti-gentrification ordinance written for "
             "the blocks either side of the trail.",
      source="Crain's Chicago Business",
      link="https://www.chicagobusiness.com/real-estate/commercial/ccb-lg-development-sells-trailhead-apartments-20260803/"),
 dict(key="california1817", kind="permit",
      lat=41.914465, lng=-87.696963,
      name="1817 N California Ave, 24 units",
      where="1817 N California Ave, Logan Square",
      detail="Five storeys and 24 dwelling units with a 24-car garage, a lift, "
             "and decks or balconies front and rear on every floor.",
      source="Permit issued 15 September 2026",
      link="https://www.chicagocityscape.com/permits.php?pid=3432017"),
 dict(key="hoyne2740", kind="permit",
      lat=41.931499, lng=-87.678984,
      name="2740 N Hoyne Ave, 59 units",
      where="2740 N Hoyne Ave, Logan Square",
      detail="Five storeys, 59 dwelling units and ten outdoor parking spaces - "
             "one of the larger mid-rises permitted around here this year.",
      source="Permit issued 4 August 2026",
      link="https://www.chicagocityscape.com/permits.php?pid=3385125"),
 dict(key="belmont917", kind="permit",
      lat=41.939829, lng=-87.652243,
      name="917 W Belmont Ave, 46 units and retail",
      where="917 W Belmont Ave, Lakeview",
      detail="Five storeys of mixed use: retail at the pavement, then 36 "
             "efficiencies and ten dwelling units on floors two to five, with "
             "six parking spaces.",
      source="Permit issued 25 August 2026",
      link="https://www.chicagocityscape.com/permits.php?pid=3449108"),
 dict(key="comed", kind="news",
      lat=41.932245, lng=-87.656508,
      name="The proposed ComEd substation",
      where="~Diversey & Clark, Lincoln Park",
      detail="Neighbours are planning a rally after ComEd rejected the "
             "alternative sites they put forward for the substation.",
      source="Chicago Sun-Times",
      link="https://chicago.suntimes.com/real-estate/2026/09/24/lincoln-park-residents-rally-comed-substation"),
 dict(key="parker", kind="news",
      lat=41.923305, lng=-87.638179,
      name="Francis W. Parker School expansion",
      where="Francis W. Parker School, Lincoln Park",
      detail="The school's expansion won its first city approval over "
             "objections from neighbours.",
      source="Chicago Sun-Times",
      link="https://chicago.suntimes.com/real-estate/2026/09/17/francis-w-parker-school-expansion-plan-commission-ire-neighbors"),
 dict(key="clybourn1720", kind="news",
      lat=41.912139, lng=-87.651663,
      name="1720 N Clybourn Ave",
      where="1720 N Clybourn Ave, Lincoln Park",
      detail="A residential development revealed for the corner, and the last "
             "thing on the ride before turning for home.",
      source="Chicago YIMBY",
      link="https://chicagoyimby.com/2026/07/residential-development-revealed-at-1720-north-clybourn-avenue-in-lincoln-park.html"),
]
# The number on a stop is where it falls in the ride, not something typed next
# to it: a stop dropped from the middle used to mean renumbering every one after
# it by hand, which is a diff no one can check.
for i, s_ in enumerate(STOPS):
    s_["n"] = i + 1
BY_KEY = {s["key"]: s for s in STOPS}

# Waypoints that only shape a leg; they are not stops and get no marker. The
# ride is for looking at buildings, so where there is a protected lane or a
# trail going the same way, take it.
#
# Keep these few. Over-constraining Valhalla is the single most common way the
# routes in this repo have gone wrong: pinning two points onto one street makes
# the router double back. If a leg looks wrong, try removing a via before adding
# one.
VIA = {
    # Leg 7 -> 8 is the point of coming this way at all: get onto The 606 at
    # Western rather than riding Milwaukee for three blocks.
    ("belloakley", "trailhead606"): [(41.913460, -87.687000)],
    # Leg 10 -> 11 crosses the river and the Kennedy. Pin the Belmont Ave
    # bridge, which is the crossing with a bike lane on both approaches.
    ("hoyne2740", "belmont917"):    [(41.939500, -87.664900)],
}

# ------------------------------------------------------------------ route ---
def decode6(shape):
    """Valhalla returns its geometry as a polyline6."""
    coords, i, lat, lon = [], 0, 0, 0
    while i < len(shape):
        for axis in range(2):
            sh, res, b = 0, 0, 0x20
            while b >= 0x20:
                b = ord(shape[i]) - 63; i += 1
                res |= (b & 0x1f) << sh; sh += 5
            d = ~(res >> 1) if res & 1 else res >> 1
            if axis == 0: lat += d
            else:         lon += d
        coords.append((lat / 1e6, lon / 1e6))
    return coords


def valhalla(points, cache):
    """Route a bicycle through every point, ends as breaks. Cached like the
    other city directories: fetch once, reuse, and deleting the cache only
    costs a re-fetch."""
    path = os.path.join(HERE, cache)
    if os.path.exists(path):
        d = json.load(open(path))
    else:
        if len(points) > 10:
            raise SystemExit(
                f"{cache}: {len(points)} locations. The public Valhalla takes "
                "ten and refuses the eleventh; a leg this long needs a via "
                "removed, not another added.")
        locs = [{"lat": p[0], "lon": p[1],
                 "type": "break" if i in (0, len(points) - 1) else "through"}
                for i, p in enumerate(points)]
        body = {"locations": locs, "costing": "bicycle",
                "costing_options": {"bicycle": {"bicycle_type": "hybrid",
                                                "use_roads": 0.3,
                                                "use_hills": 0.5}},
                "directions_options": {"units": "kilometers"}}
        req = urllib.request.Request(
            VALHALLA + "?json=" + urllib.parse.quote(json.dumps(body)),
            headers=UA)
        d = json.load(urllib.request.urlopen(req, timeout=60))
        json.dump(d, open(path, "w"))
        time.sleep(1.1)          # their policy; a dozen legs is not a hurry
    out = []
    for lg in d["trip"]["legs"]:
        out.extend(decode6(lg["shape"]))
    return out, d["trip"]["summary"]["length"]        # km


def haversine(a, b):
    R = 6371000.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(h))


features = []
print("legs")
for i in range(len(STOPS) - 1):
    a, b = STOPS[i], STOPS[i + 1]
    pts = [(a["lat"], a["lng"])] \
        + VIA.get((a["key"], b["key"]), []) \
        + [(b["lat"], b["lng"])]
    shape, km = valhalla(pts, f"leg_{a['key']}_{b['key']}.json")

    # Valhalla snaps each end to the nearest routable way. A big snap means the
    # coordinate is not where a bicycle can get to, which on this page would
    # most likely be a bad geocode rather than a genuinely unreachable site.
    for end, stop in ((shape[0], a), (shape[-1], b)):
        off = haversine(end, (stop["lat"], stop["lng"]))
        if off > 120:
            print(f"  ! {stop['key']} snapped {off:.0f} m to the nearest way")

    # Draw to the snapped ends rather than to the stop coordinate: pulling the
    # line onto a point the router did not use puts a spur across a building.
    features.append({
        "type": "Feature",
        "properties": {
            "mode": "bike", "seq": i + 1, "line": "by bike",
            "from": a["name"], "to": b["name"],
            "from_n": a["n"], "to_n": b["n"],
            "km": round(km, 2),
            # Nothing here was ridden yet. `routed` is what makes map-common
            # draw the leg dashed, and that is the whole point.
            "source": "routed",
        },
        "geometry": {"type": "LineString",
                     "coordinates": [[round(p[1], 6), round(p[0], 6)]
                                     for p in shape]},
    })
    print(f"  {a['n']:2d} -> {b['n']:2d}  {km:5.2f} km / {km/1.609344:4.1f} mi"
          f"  {len(shape):4d} pts  {a['key']} -> {b['key']}")

# ------------------------------------------------------------------ write ---
def note(s):
    """What the popup says. The key row shows the name and the distance; this
    is everything else, including the link out to where the claim came from."""
    return (s["detail"]
            + '<br>' + s["where"] + ' &middot; ' + s["source"]
            + '<br><a href="' + s["link"] + '" target="_blank" '
              'rel="noopener noreferrer">Read more &rarr;</a>')

stops_fc = {"type": "FeatureCollection", "features": [
    {"type": "Feature",
     "properties": {"n": s["n"], "name": s["name"], "key": s["key"],
                    # One mode, so every ring is the bicycle purple; what tells
                    # the two sorts of stop apart is the glyph, not the colour.
                    "arrive": "bike", "note": note(s)},
     "geometry": {"type": "Point",
                  "coordinates": [round(s["lng"], 6), round(s["lat"], 6)]}}
    for s in STOPS]}
lines_fc = {"type": "FeatureCollection", "features": features}
icons = {s["key"]: ("building" if s["kind"] == "permit" else "news")
         for s in STOPS}

tpl = open(os.path.join(HERE, "template.html")).read()
tpl = tpl.replace("__LINES__", json.dumps(lines_fc, separators=(",", ":")))
tpl = tpl.replace("__STOPS__", json.dumps(stops_fc, separators=(",", ":")))
tpl = tpl.replace("__ICONS__", json.dumps(icons, separators=(",", ":")))
# The page's own copy quotes the length, so take it from the legs rather than
# letting a hand-typed number drift away from the route after a via is moved.
miles = sum(f["properties"]["km"] for f in features) / 1.609344
tpl = tpl.replace("__MILES__", f"{miles:.0f}")
WORDS = {11: "Eleven", 12: "Twelve", 13: "Thirteen", 14: "Fourteen",
         15: "Fifteen", 16: "Sixteen", 17: "Seventeen", 18: "Eighteen"}
tpl = tpl.replace("__COUNT__", WORDS.get(len(STOPS), str(len(STOPS))))
out = os.path.join(ROOT, "chicago-new-things-map.html")
open(out, "w").write(tpl)

km = sum(f["properties"]["km"] for f in features)
permits = sum(1 for s in STOPS if s["kind"] == "permit")
print(f"\n{len(STOPS)} stops: {permits} permits, {len(STOPS)-permits} news")
print(f"total {km:.2f} km / {km/1.609344:.2f} mi over {len(features)} legs")
print(f"wrote {out}, {len(tpl)} bytes")
