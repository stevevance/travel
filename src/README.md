# Map sources

The HTML maps at the root of this repo are generated, not hand-written. This
directory holds the scripts that build them, so a route correction means editing
a waypoint and re-running rather than hand-editing a 90 KB file.

## Layout

| Directory | Builds |
|---|---|
| `hague/` | `hague-map.html` |
| `rotterdam/` | `rotterdam-map.html` |
| `utrecht/` | research scripts behind `utrecht-itinerary.html` |

## Data sources

Everything comes from public APIs, with no keys required:

- **OpenStreetMap Overpass** for transit route relations and street geometry.
  Use `overpass-api.de` first and `overpass.kumi.systems` as the fallback; both
  rate-limit, so the scripts sleep between calls.
- **Valhalla** (`valhalla1.openstreetmap.de`) for pedestrian and bicycle routing.
- **Nominatim** for geocoding. Their policy requires a contact in the
  User-Agent and a maximum of one request per second; the scripts comply.

Cached API responses are gitignored. Deleting them just means the next run
re-fetches, which takes a few minutes.

## Gotchas worth knowing before you edit

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

## Privacy

These maps trace real days. Route lines are deliberately drawn to public street
junctions and transit stops, never to a residence. Keep it that way when adding
legs: end a route at the corner, not at a door.
