"""Generate the interactive MapLibre page (also the source for the static shots)."""
import json

lines = json.load(open("route_lines.geojson"))
stops = json.load(open("route_stops.geojson"))

TPL = open("template.html").read()
TPL = TPL.replace("__LINES__", json.dumps(lines, separators=(",", ":")))
TPL = TPL.replace("__STOPS__", json.dumps(stops, separators=(",", ":")))
open("hague-map.html", "w").write(TPL)
print("wrote hague-map.html", len(TPL), "bytes")
