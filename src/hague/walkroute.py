"""Route the walking legs over the real pedestrian network via public Valhalla."""
import json, time, urllib.request
from routes import STOPS

ENDPOINT = "https://valhalla1.openstreetmap.de/route"

def decode_polyline6(s):
    """Valhalla returns a polyline with 6-digit precision."""
    coords, lat, lon, i = [], 0, 0, 0
    while i < len(s):
        for who in range(2):
            shift, result = 0, 0
            while True:
                b = ord(s[i]) - 63
                i += 1
                result |= (b & 0x1f) << shift
                shift += 5
                if b < 0x20:
                    break
            d = ~(result >> 1) if result & 1 else (result >> 1)
            if who == 0:
                lat += d
            else:
                lon += d
        coords.append((lat / 1e6, lon / 1e6))
    return coords

def walk(a, b):
    body = {
        "locations": [
            {"lat": STOPS[a][0], "lon": STOPS[a][1]},
            {"lat": STOPS[b][0], "lon": STOPS[b][1]},
        ],
        "costing": "pedestrian",
        "directions_options": {"units": "kilometers"},
    }
    req = urllib.request.Request(
        ENDPOINT + "?json=" + urllib.parse.quote(json.dumps(body)),
        headers={"User-Agent": "steven-personal-itinerary-map/1.0"},
    )
    d = json.load(urllib.request.urlopen(req, timeout=45))
    legs = d["trip"]["legs"]
    pts = []
    for lg in legs:
        pts.extend(decode_polyline6(lg["shape"]))
    return pts, d["trip"]["summary"]["length"], d["trip"]["summary"]["time"]

import urllib.parse

if __name__ == "__main__":
    WALKS = [("bierkade", "kerkplein"),
             ("malieveld", "koekamp"), ("koekamp", "binnenhof"),
             ("binnenhof", "grote_markt"),
             ("prinsenhof", "lakila"), ("lakila", "delft_station")]

    out = {}
    for a, b in WALKS:
        try:
            pts, km, secs = walk(a, b)
            out[f"{a}|{b}"] = pts
            print(f"{a:14s} -> {b:14s} {len(pts):4d} pts  {km*1000:5.0f} m  {secs/60:4.1f} min")
        except Exception as e:
            print(f"{a} -> {b} FAILED: {e}")
        time.sleep(1.0)

    json.dump({k: [[round(p[0], 6), round(p[1], 6)] for p in v] for k, v in out.items()},
              open("walks.json", "w"))
    print("saved", len(out), "walk geometries")
