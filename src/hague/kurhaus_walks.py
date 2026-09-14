"""
The Scheveningen out-and-back: Kurhaus tram stop -> through the hotel ->
Summertime on the beach, returning by the covered stairs northeast of the hotel.

Both halves are routed with an intermediate waypoint, because the shortest path
would otherwise skirt the hotel and skip the stairs entirely -- the two things
that make this walk what it actually was.
"""
import json, urllib.parse, urllib.request
from walkroute import decode_polyline6

ENDPOINT = "https://valhalla1.openstreetmap.de/route"

KURHAUS_TRAM = (52.113270, 4.283670)   # mean of the two tram_stop platforms
HOTEL        = (52.113210, 4.281630)   # Kurhaus hotel centroid
SUMMERTIME   = (52.113440, 4.280050)   # restaurant on the boulevard
STAIRS_TOP   = (52.114719, 4.283199)   # covered steps NE of the hotel
STAIRS_BOT   = (52.114502, 4.283216)

def route(points):
    """points = list of (lat, lon); middle ones are pass-through waypoints."""
    locs = []
    for i, p in enumerate(points):
        loc = {"lat": p[0], "lon": p[1]}
        loc["type"] = "break" if i in (0, len(points) - 1) else "through"
        locs.append(loc)
    body = {"locations": locs, "costing": "pedestrian",
            "costing_options": {"pedestrian": {"use_ferry": 0, "step_penalty": 0}},
            "directions_options": {"units": "kilometers"}}
    req = urllib.request.Request(
        ENDPOINT + "?json=" + urllib.parse.quote(json.dumps(body)),
        headers={"User-Agent": "steven-personal-itinerary-map/1.0"})
    d = json.load(urllib.request.urlopen(req, timeout=45))
    pts = []
    for lg in d["trip"]["legs"]:
        pts.extend(decode_polyline6(lg["shape"]))
    return pts, d["trip"]["summary"]["length"] * 1000

out, out_m = route([KURHAUS_TRAM, HOTEL, SUMMERTIME])
print(f"out  tram -> hotel -> Summertime : {len(out):3d} pts  {out_m:4.0f} m")

back, back_m = route([SUMMERTIME, STAIRS_BOT, STAIRS_TOP, KURHAUS_TRAM])
print(f"back Summertime -> stairs -> tram: {len(back):3d} pts  {back_m:4.0f} m")

json.dump({"kurhaus|summertime": [[round(p[0], 6), round(p[1], 6)] for p in out],
           "summertime|kurhaus": [[round(p[0], 6), round(p[1], 6)] for p in back]},
          open("kurhaus_walks.json", "w"))
print("saved kurhaus_walks.json")
