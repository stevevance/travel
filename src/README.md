# Map sources

The HTML maps at the root of this repo are generated, not hand-written. This
directory holds the scripts that build them, so a route correction means editing
a waypoint and re-running rather than hand-editing a 90 KB file.

## Layout

| Directory | Builds |
|---|---|
| `hague/` | `hague-map.html` |
| `rotterdam/` | `rotterdam-map.html` |
| `utrecht/` | `utrecht-map.html`, plus research scripts behind `utrecht-itinerary.html` |

Each city directory holds a `template.html` with `__LINES__`/`__STOPS__`
placeholders and a `build_html.py` that fills them in and writes the page to the
repo root. The shared `map-common.js` and `map-common.css` at the root carry
everything the three maps have in common - palette, panel, markers, the numbered
key, click-to-fly - so a page's own file is just its copy and its stop icons.

## Data sources

Everything comes from public APIs, with no keys required:

- **OpenStreetMap Overpass** for transit route relations and street geometry.
  Use `overpass-api.de` first and `overpass.kumi.systems` as the fallback; both
  rate-limit, so the scripts sleep between calls.
- **Valhalla** (`valhalla1.openstreetmap.de`) for pedestrian and bicycle routing.
- **Nominatim** for geocoding. Their policy requires a contact in the
  User-Agent and a maximum of one request per second; the scripts comply.
- **A Strava GPX export** for the one leg that was measured rather than routed:
  the Utrecht bakfiets ride, in `data/utrecht/`. Every leg on that map carries a
  `source` property — `osm`, `routed` or `gps` — and the page draws the routed
  reconstruction dashed so it cannot pass for the recording.

Cached API responses are gitignored. Deleting them just means the next run
re-fetches, which takes a few minutes.

## Gotchas worth knowing before you edit

- **Utrecht's tram 22 is tagged `route=light_rail`, not `route=tram`,** and is
  split into one relation per direction. A `route=tram` query for ref 22 returns
  nothing at all.
- **Never give `.stopdot` a `position`.** MapLibre positions markers with
  `.maplibregl-marker{position:absolute}` from its own stylesheet. A page rule
  of equal specificity, loaded after it, silently wins and drops every marker
  into normal document flow, stacking them one marker-height apart down the
  page - correct at the top of the list, hundreds of pixels off at the bottom.
  This shipped on both the Hague and Utrecht maps. A badge pinned to a marker
  anchors against the marker's own absolute box; it needs no extra context.
- **Do not over-constrain Valhalla.** Pinning two waypoints onto one stairway or
  a mid-block point makes the router double back. Four separate route bugs in
  these maps traced to exactly this; the fix each time was removing a waypoint,
  not adding one. After changing waypoints, check the leg distance did not jump
  and that the path does not retrace itself.
- **MapLibre uses 512px tiles, not 256.** Zoom math that assumes 256 comes out
  one power of two too tight and clips the outer stops.
- **`line-dasharray` is not data-driven in MapLibre.** A dashed leg needs its
  own filtered layer; a `case` expression on dasharray silently does nothing.
- **`walkroute.py` must stay behind `if __name__ == "__main__":`.** Without the
  guard, importing it re-runs the routing and overwrites the cached walks.
- **Key numbering comes from `data-n`, not a CSS counter.** `counter()` counts
  list items, so any revisited stop pushes the legend out of step with the
  markers.
- **Check every waypoint dictionary key against a real leg.** Renaming a leg's
  origin without renaming its `VIA` key makes the lookup miss, return an empty
  list, and silently drop the detour with no error.

## Checking a change

`src/utrecht/shoot.py` renders a built page in headless Chrome and screenshots
it; it needs `playwright` (`python3 -m venv .venv && .venv/bin/pip install
playwright`), and uses the Chrome already on the machine rather than downloading
one. Worth more than reading the diff: both marker bugs above were invisible in
the source and obvious the moment a browser laid the page out.

## Privacy

These maps trace real days. Route lines are deliberately drawn to public street
junctions and transit stops, never to a residence. Keep it that way when adding
legs: end a route at the corner, not at a door.
