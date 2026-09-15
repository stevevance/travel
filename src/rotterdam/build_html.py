"""Generate the interactive MapLibre page from build.py's GeoJSON."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

lines = json.load(open(os.path.join(HERE, "rtd_lines.geojson")))
stops = json.load(open(os.path.join(HERE, "rtd_stops.geojson")))

tpl = open(os.path.join(HERE, "template.html")).read()
tpl = tpl.replace("__LINES__", json.dumps(lines, separators=(",", ":")))
tpl = tpl.replace("__STOPS__", json.dumps(stops, separators=(",", ":")))
out = os.path.join(ROOT, "rotterdam-map.html")
open(out, "w").write(tpl)
print("wrote", out, len(tpl), "bytes")
