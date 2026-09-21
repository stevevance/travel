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
| `bruges/` | `bruges-map.html`, and the photographs on it |
| `alphen-leiden-amsterdam/` | `alphen-leiden-amsterdam-map.html` |

Each city directory holds a `template.html` with `__LINES__`/`__STOPS__`
placeholders and a build script (`build.py`, or `build_html.py` where the
geometry is cached in a committed geojson) that fills them in and writes the page
to the repo root. The shared `map-common.js` and `map-common.css` at the root carry
everything the maps have in common - palette, panel, markers, the numbered key,
click-to-fly, and now the photo layer - so a page's own file is just its copy and
its stop icons.

Bruges is the odd one out twice over. It is the only map with no routed geometry
at all - three Strava recordings and nothing else - and the only one that carries
photographs, so its template takes a third placeholder, `__PHOTOS__`.

The day out to Alphen, Leiden and Amsterdam is the odd one out a third way: it is
the only page that mixes all three sources on one map, the only one with a mode
the others do not have (`ferry`), and the only one where a single Strava file
holds more than one mode. Its two walks were never recorded at all and are
reconstructed from the day's photographs; see below.

## Data sources

Everything comes from public APIs, with no keys required:

- **OpenStreetMap Overpass** for transit route relations and street geometry.
  Use `overpass-api.de` first and `overpass.kumi.systems` as the fallback; both
  rate-limit, so the scripts sleep between calls.
- **Valhalla** (`valhalla1.openstreetmap.de`) for pedestrian and bicycle routing.
- **Nominatim** for geocoding. Their policy requires a contact in the
  User-Agent and a maximum of one request per second; the scripts comply.
- **Strava GPX exports** for the legs that were measured rather than routed: the
  Utrecht bakfiets ride in `data/utrecht/`, all three Bruges rides in
  `data/bruges/`, and the three rides of 20 September in
  `data/alphen-leiden-amsterdam/`. Every leg carries a `source` property —
  `osm`, `routed` or `gps` — and both the Utrecht page and the Alphen day draw
  their routed reconstructions dashed so they cannot pass for a recording.
- **The macOS Photos library**, read through `osxphotos` - for the Bruges
  pictures, and on 20 September for the *shape* of two walks that were never
  recorded. That is the one source not on the public internet, which is why it
  always lives in its own script; see below.

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
- **The key is built by walking the leg list, so legs must be in the order the
  day happened.** It is far cheaper to compute them grouped by source - all the
  rail, then the walks, then the recordings - and doing that reads out as Gouda,
  Amsterdam, then back to a bridge in Alphen, with the first stop of the day
  missing entirely, because the opening row comes from the first leg's origin.
  Give every leg a numeric `seq` property: `map-common.js` sorts the key by it
  whenever all of them have one, so the ordering no longer depends on the build
  script emitting them in the right order. Pages without `seq` are unaffected.
- **A photograph's fix is where the camera stood, not where the walk went.**
  Three of the Leiden stills were taken a street away from the route - one from
  a quay 60 m off it. As a Valhalla waypoint that is an order rather than a
  hint, so each one dragged the leg onto the wrong street and made it double
  back to obey. `photo_walks.py` has a `DROP` table naming them and why; dropping
  a picture as a *waypoint* does not drop it as evidence.
- **Valhalla's public instance takes ten locations and refuses the eleventh**
  with a bare `400 Bad Request`. Its error body says which limit was hit, so
  surface it - a leg that has grown past ten waypoints needs one removed, not
  another added, which is usually the right answer anyway.
- **A routed leg is drawn dashed.** `map-common.js` gives any leg whose `source`
  is `routed` its own dashed layer in its mode's colour, so a reconstruction
  cannot pass for a recording. Walking was always dotted; this covers the ridden
  legs no recording reaches - the opening of the Utrecht ride, and the run out
  of Sloterdijk before Strava was started.
- **A page can ask for imperial units.** Pass `units: 'imperial'` to
  `MapKit.render` and the scale bar and every distance in the key switch
  together; `kit.fmtDist` is there so a page's own copy uses the same units.
  Distances stay in kilometres in the data either way.
- **A GPS trace through a tunnel is a guess, not a route.** Both Rotterdam rides
  cross under the station in the Provenierstunnel, and the receiver filled the
  half-minute with a zigzag across the platforms, teleporting at 136 and
  194 km/h. Look for the speed spike: it is the reliable tell, and it brackets
  exactly the stretch worth replacing. Anchor on the tunnel's portals, swap the
  blacked-out fixes for the OSM way, and say in the copy that you did - a `gps`
  leg that is quietly part OSM is the kind of thing this repo should not ship
  silently.
- **A sick Overpass mirror accepts the connection and then says nothing.**
  `kumi.systems` hung for minutes at a stretch while `overpass-api.de` answered
  the same query in two seconds, and a 300 s read timeout turned that into a
  nine-minute build. 90 s is plenty: the point of the fallback is to ask the
  other mirror, not to wait out the first one.

## Photographs

Two different jobs here, and they are worth keeping apart. Bruges *publishes*
pictures. The Alphen day does not publish any: it uses their GPS fixes only to
work out where two unrecorded walks went, and ships the routed line. Nothing
from the camera roll reaches that page.

### Walks reconstructed from where pictures were taken

`alphen-leiden-amsterdam/photo_walks.py` takes each still inside a bounding box
in time order, treats its fix as a waypoint, and asks Valhalla for the
pedestrian route between them. It writes the committed `walks.geojson`, so a
clone with no Photos library and no network can still rebuild the page, and the
lines are drawn dotted like every other walk so they cannot pass for
measurements. It found the Alphen walk's turn 40 m from the Koningin Julianabrug
and the Leiden walk's 1 m from the cafe door.

Its one trap is *not* the Bruges trap. This library holds two rows for several
pictures: one with a real `+02:00` offset and one written in UTC with no offset
at all. They are the same instant - but printed with `strftime` the UTC rows
read as pictures taken two hours before the frame before them, which is exactly
what the Bruges fault looks like. Parse timezone-aware, convert to CEST before
comparing or showing, and collapse duplicate rows preferring the one that states
its offset. Do not "correct" them.

### Pictures published on a page

`bruges/pick_photos.py` is deliberately a separate run from `bruges/build.py`.
It needs a Mac, `osxphotos` and the actual Photos library; `build.py` needs only
the committed `photos.geojson`, so a clone can still rebuild the page. Run the
picker once, then the build:

    python3 src/bruges/pick_photos.py     # Photos -> photos/bruges/*.jpg + photos.geojson
    python3 src/bruges/build.py           # -> bruges-map.html

Pictures are matched to a ride by timestamp, snapped to the nearest fix on that
ride's track, then thinned to an even spacing *by distance along the track* -
one every two miles, never fewer than one per three, and never fewer than one
per ride. A ride can only fall short of that floor because the pictures do not
exist; when that is so and has been looked at, the ride goes in `SHORT_OK` with
the reason, and any ride falling short *without* being named there is shouted
about instead. The evening meander is the one entry: two stills seven seconds
apart at the same canal, one of them excluded as a near-duplicate. Spacing by distance rather than by clock is the whole point: seven
minutes standing at Blankenberge pier produced five frames that would otherwise
have taken the entire quota for that ride.

Three traps, all of which fail silently:

- **Photos reports local time and the GPX is UTC.** Belgium was on CEST, so two
  hours come off every photo timestamp before anything is compared. Skip it and
  every picture lands on the wrong ride, or on none.
- **A library can hold the same picture more than once.** `IMG_0229.HEIC` is in
  there three times, one copy stamped exactly two hours early, which placed it
  2.2 km off the ride out. Duplicate original filenames are dropped, and so is
  anything more than 200 m from its track.
- **Most of the originals are in iCloud, not on the disk.** The local
  derivatives are 480×360 thumbnails, far too small to show. The export passes
  `--download-missing --use-photokit` to pull the full versions down, which is
  slow the first time. It also passes `--skip-original-if-edited`, and that flag
  is sharper than it reads: an edited picture then comes out *only* as
  `IMG_0235_edited.jpeg`, with no plain-named file at all, so the lookup has to
  try both names or the run dies on a picture that exported perfectly well.

A re-run is not guaranteed to pick the same set. These choices come out of
whatever the library holds at the time, and iCloud keeps syncing: the first run
saw 142 items for the day and the second saw 161, which moved five of the picks
on the ride out. Each picture's original filename is recorded in
`photos.geojson`, which is what the captions are keyed on, so a re-pick shows up
as captions going missing rather than as captions quietly attached to the wrong
picture.

Captions are the one hand-written table in the build, in `CAPTIONS` in
`build.py` - not in the picker, so that writing one costs a one-second rebuild
rather than another pass over the Photos library. A script can place a
photograph; it cannot say what is in it.

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

The same goes for the pictures. Every photograph on the Bruges map is of a
public place - a canal path, a beach, a street - and every one was looked at
before it shipped. `pick_photos.py` chooses *where* a picture goes; it does not
decide whether a picture should be published, and it should not be pointed at a
new day and run unattended. Nothing here is served from the phone's camera roll
at full resolution either: the exports are resized to a 1400 px long edge.
