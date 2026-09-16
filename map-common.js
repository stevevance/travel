/* Shared behaviour for the route maps (Rotterdam, The Hague, Utrecht, Bruges).
 *
 * Each page supplies its own LINES and STOPS GeoJSON, its own palette of stop
 * icons, and its own copy; everything else - how a map is built, how markers
 * are placed, how the numbered key is assembled and how a click flies to a
 * stop - lives here, so a fix lands on all four pages at once.
 *
 * Usage, from the page's inline script:
 *     MapKit.render({lines: LINES, stops: STOPS, stopIcon: {...}, quiet: [...],
 *                    photos: PHOTOS, categoryBy: 'ride', palette: {...}});
 *
 * `photos` is optional: a FeatureCollection of points carrying `img`, `time`
 * and `caption`, drawn as camera dots that open the picture in a popup.
 *
 * `categoryBy` and `palette` are optional too, and go together: they say which
 * leg property the colour keys off and what colours to use. The default is
 * mode, which is right for every map whose legs differ by mode. Bruges is three
 * bicycle rides, so mode would paint the whole day one colour; it keys off the
 * `ride` property instead. Whatever the category is, it drives the line, the
 * ring on each numbered stop and the number in the key together, so the three
 * cannot disagree.
 *
 * Non-obvious rules this file exists to hold:
 *
 *  - The marker element must NOT carry `position: relative`. MapLibre places
 *    markers with `.maplibregl-marker{position:absolute}` from its own
 *    stylesheet; a page rule of equal specificity, loaded later, silently
 *    overrides it, drops every marker into normal document flow and stacks
 *    them one marker-height apart. That bug shipped on two of these pages.
 *    A badge pinned to a marker can position against the marker's own absolute
 *    box, so no extra positioning context is needed.
 *  - `line-dasharray` is not a data-driven paint property, so dashed legs need
 *    their own filtered layer rather than a `case` expression.
 *  - MapLibre opens the compact attribution on load; these maps collapse it
 *    back to the "i" button, and it still opens on click.
 */
(function (global) {
  'use strict';

  /* Categorical by MODE, shared across the set so a mode keeps the same colour
     from one page to the next. Validated all-pairs on a light surface; line
     identity rides on the numbered badges, not on hue.

     This is the default palette, not the only one. A page whose legs are all the
     same mode - Bruges, three bicycle rides - passes its own `categoryBy` and
     `palette` so the colour can key off something that actually varies there. */
  var COLOR = {
    metro: '#2a78d6',
    tram:  '#eb6834',
    train: '#1baf7a',
    bike:  '#7d4bc2',
    walk:  '#5f5b54'
  };

  /* 24x24, stroked in currentColor so one definition serves both the key and
     the badge clipped to a marker. */
  var ICON_PATHS = {
    museum:  '<path d="M3 9.5 12 4l9 5.5"/><path d="M5.5 10v8M9.5 10v8M14.5 10v8M18.5 10v8"/><path d="M2.5 18.5h19"/>',
    church:  '<path d="M12 2v4M10.2 3.7h3.6"/><path d="M6 21V10l6-4 6 4v11"/><path d="M10 21v-4a2 2 0 0 1 4 0v4"/>',
    ship:    '<path d="M5.5 13.5V7.5h6.5l3.2 6"/><path d="M9 7.5V4"/><path d="M2.5 14.5h19L19 20H5z"/>',
    landmark:'<path d="M12 2.5c2.6 1.7 4 3.7 4 5.5H8c0-1.8 1.4-3.8 4-5.5z"/><path d="M6.5 8.5h11v9.5h-11z"/><path d="M4 18.5h16v2.5H4z"/><path d="M10.2 18.5v-4.3a1.8 1.8 0 0 1 3.6 0v4.3"/>',
    drinks:  '<path d="M3.5 4.5h17L12 13z"/><path d="M12 13v7"/><path d="M8 20.5h8"/>',
    park:    '<path d="M12 3 5.8 12.5h12.4z"/><path d="M12 8 7.6 16.5h8.8z"/><path d="M12 16.5V21"/>',
    deer:    '<path d="M12 10.2c1.9 0 3.3 1.5 3.3 3.4 0 2.7-1.5 6.2-3.3 6.2s-3.3-3.5-3.3-6.2c0-1.9 1.4-3.4 3.3-3.4z"/><path d="M9.7 10.4 8 7.3 5.4 7.6M8 7.3l-.4-2.6"/><path d="M14.3 10.4 16 7.3l2.6.3M16 7.3l.4-2.6"/>',
    castle:  '<path d="M4.5 21V10L7 7l2.5 3v11"/><path d="M14.5 21V10L17 7l2.5 3v11"/><path d="M9.5 21v-8L12 10.2 14.5 13v8"/><path d="M2.5 21h19"/>',
    shops:   '<path d="M5 8h14l-1.1 12.5H6.1z"/><path d="M9 8V5.8a3 3 0 0 1 6 0V8"/>',
    food:    '<path d="M6.5 3v5.5a2.4 2.4 0 0 0 4.8 0V3"/><path d="M8.9 9v12"/><path d="M17.3 3c1.5 1.6 2 4.2 1.6 7.8h-3.2C15.3 7.2 15.8 4.6 17.3 3z"/><path d="M17.3 10.8V21"/>',
    train:   '<rect x="6" y="3" width="12" height="13" rx="3.2"/><path d="M6 11h12"/><path d="M9.4 13.6h.01M14.6 13.6h.01"/><path d="M8.2 16 6 21M15.8 16 18 21"/>',
    tram:    '<rect x="6" y="4" width="12" height="12.5" rx="2.6"/><path d="M6 11h12"/><path d="M12 4V1.8"/><path d="M9.4 13.8h.01M14.6 13.8h.01"/><path d="M8.2 16.5 6 21M15.8 16.5 18 21"/>',
    garden:  '<path d="M12 21v-8.5"/><path d="M12 12.5C12 9.2 9.3 6.5 6 6.5c0 3.3 2.7 6 6 6z"/><path d="M12 14.5c0-2.8 2.2-5 5-5 0 2.8-2.2 5-5 5z"/><path d="M6.5 21h11"/>',
    bastion: '<path d="M3 21v-7l4.5-4h9L21 14v7"/><path d="M2 21h20"/><path d="M7.5 10V6.5h9V10"/><path d="M10.2 21v-4.6h3.6V21"/>',
    tower:   '<path d="M9 21V6.6L12 2.5l3 4.1V21"/><path d="M7 21h10"/><path d="M11 21v-4.2a1 1 0 0 1 2 0V21"/><path d="M10.6 9.6h2.8M10.6 13.1h2.8"/>',
    bakfiets:'<circle cx="5.5" cy="16.8" r="3.4"/><circle cx="18.5" cy="16.8" r="3.4"/><path d="M2.6 13.2h5.8V9.1H2.6z"/><path d="M8.4 11 15 16.8"/><path d="M14.2 11.2h3.1l1.2 5.6"/><path d="M12.6 8.4h3.4"/>',
    bike:    '<circle cx="5.6" cy="16.4" r="3.9"/><circle cx="18.4" cy="16.4" r="3.9"/><path d="M5.6 16.4 9.4 8.2h5.1l3.9 8.2"/><path d="M8.2 8.2h3.4"/><path d="M14.5 8.2 12 16.4"/><path d="M15.2 6.1h2.6"/>',
    camera:  '<path d="M2.8 7.9h4l1.5-2.4h7.4l1.5 2.4h4v10.6h-18.4z"/><circle cx="12" cy="13.1" r="3.5"/>',
    sea:     '<circle cx="17.2" cy="6.2" r="2.8"/><path d="M2.5 13.2c1.6 0 1.6 1.7 3.2 1.7s1.6-1.7 3.2-1.7 1.6 1.7 3.2 1.7 1.6-1.7 3.2-1.7 1.6 1.7 3.2 1.7"/><path d="M2.5 18c1.6 0 1.6 1.7 3.2 1.7S7.3 18 8.9 18s1.6 1.7 3.2 1.7S13.7 18 15.3 18s1.6 1.7 3.2 1.7"/>'
  };
  var ICON_LABEL = {
    museum:'Museum', church:'Church', ship:'Museum ship', landmark:'Landmark',
    drinks:'Drinks', park:'Park', deer:'Deer park', castle:'Historic site',
    shops:'Shops and cafes', food:'Meal', train:'Rail station', tram:'Tram stop',
    garden:'Botanic gardens', bastion:'Bulwark', tower:'Tower',
    bakfiets:'Cargo bike', bike:'Bicycle', camera:'Photograph', sea:'The sea'
  };

  function iconHTML(name, quiet) {
    if (!name || !ICON_PATHS[name]) return '';
    return '<svg class="ico' + (quiet ? ' quiet' : '') + '" viewBox="0 0 24 24" '
         + 'role="img" aria-label="' + ICON_LABEL[name] + '">'
         + ICON_PATHS[name] + '</svg>';
  }

  function render(cfg) {
    var LINES = cfg.lines, STOPS = cfg.stops;
    var STOP_ICON = cfg.stopIcon || {};
    var QUIET = new Set(cfg.quiet || []);
    var VIEWS = cfg.views || {};
    /* Optional: a FeatureCollection of points, each with an `img` (a path
       relative to the page), a `time` and an optional `caption`. Drawn as small
       camera dots that open the picture in a popup. */
    var PHOTOS = cfg.photos || null;
    /* Which leg property the colour, the key's numbers and the stop rings all
       key off, and the colours to use for it. Defaults to mode, which is what
       every map but Bruges wants. */
    var CATEGORY = cfg.categoryBy || 'mode';
    var PALETTE  = cfg.palette || COLOR;
    var q = new URLSearchParams(location.search);

    /* null, not a fallback colour, so a caller can tell "no colour for this"
       from "grey" and leave the element's own stylesheet rule alone. */
    function colorFor(v) {
      return Object.prototype.hasOwnProperty.call(PALETTE, v) ? PALETTE[v] : null;
    }

    /* The panel is always shown. nohead drops just its title, for the composed
       sheet where the title already sits in the page header. */
    if (q.get('nohead')) {
      document.querySelectorAll('.panel .kicker, .panel h1')
              .forEach(function (el) { el.style.display = 'none'; });
    }

    var map = new maplibregl.Map({
      container: 'map',
      style: 'https://tiles.openfreemap.org/styles/liberty',
      attributionControl: false,
      hash: false
    });
    global.map = map;   // exposed for debugging and scripted views

    if (!q.get('nochrome')) {
      map.addControl(new maplibregl.NavigationControl({showCompass: false}), 'top-right');
      map.addControl(new maplibregl.AttributionControl({compact: true}), 'bottom-right');
      /* Compact attribution renders expanded on load. Collapse it to the "i"
         button so every page in the set starts the same way; a click still
         opens it. */
      map.once('load', function () {
        document.querySelectorAll('.maplibregl-ctrl-attrib.maplibregl-compact-show')
                .forEach(function (el) { el.classList.remove('maplibregl-compact-show'); });
      });
    }
    map.addControl(new maplibregl.ScaleControl({maxWidth: 110, unit: 'metric'}), 'bottom-left');

    /* Fit to the whole chain of legs so nothing is cropped. */
    var bounds = new maplibregl.LngLatBounds();
    LINES.features.forEach(function (f) {
      f.geometry.coordinates.forEach(function (c) { bounds.extend(c); });
    });

    /* The panel covers part of the canvas - the left third on a wide screen,
       the bottom on a narrow one - so framing and fly-to both have to aim at
       the middle of what is visible, not the middle of the container. */
    function narrowView() { return window.matchMedia('(max-width: 700px)').matches; }
    function padFor() {
      return narrowView()
        ? {top: 50, bottom: Math.round(window.innerHeight * 0.45), left: 30, right: 30}
        : {top: 70, bottom: 70, left: 360, right: 70};
    }
    function panelOffset() {
      return narrowView() ? [0, -Math.round(window.innerHeight * 0.21)] : [165, 0];
    }

    var MARKERS = {};
    var PHOTO_MARKERS = [];
    function stopByN(n) {
      return STOPS.features.find(function (s) { return s.properties.n === n; });
    }
    function flyToStop(n) {
      var f = stopByN(n);
      if (!f) return;
      map.flyTo({center: f.geometry.coordinates, zoom: 16, speed: 1.3,
                 offset: panelOffset()});
      var m = MARKERS[n];
      if (m && !m.getPopup().isOpen()) m.togglePopup();
    }
    function flyToPhoto(i) {
      var m = PHOTO_MARKERS[i];
      if (!m) return;
      map.flyTo({center: m.getLngLat(), zoom: 15, speed: 1.3,
                 offset: panelOffset()});
      if (!m.getPopup().isOpen()) m.togglePopup();
    }
    function flyToFeatures(pred) {
      var b = new maplibregl.LngLatBounds();
      LINES.features.filter(pred).forEach(function (f) {
        f.geometry.coordinates.forEach(function (c) { b.extend(c); });
      });
      map.fitBounds(b, {padding: padFor(), speed: 1.3});
    }

    map.on('load', function () {
      map.addSource('legs', {type: 'geojson', data: LINES});

      /* White casing under every line keeps dense crossings legible. */
      map.addLayer({
        id: 'legs-casing', type: 'line', source: 'legs',
        layout: {'line-cap': 'round', 'line-join': 'round'},
        paint: {
          'line-color': '#ffffff',
          'line-opacity': 0.95,
          'line-width': ['interpolate', ['linear'], ['zoom'], 9, 5, 12, 8, 15, 13, 17, 18]
        }
      });
      /* Two line layers, not one: line-dasharray is not data-driven, so the
         dotted walking legs need their own filtered layer. */
      /* Built from the palette rather than written out, so a page that supplies
         its own set of categories does not also have to be listed here. */
      var lineColor = ['match', ['get', CATEGORY]];
      Object.keys(PALETTE).forEach(function (k) { lineColor.push(k, PALETTE[k]); });
      lineColor.push(COLOR.walk);          // anything uncategorised
      map.addLayer({
        id: 'legs-line', type: 'line', source: 'legs',
        filter: ['!=', ['get', 'mode'], 'walk'],
        layout: {'line-cap': 'round', 'line-join': 'round'},
        paint: {
          'line-color': lineColor,
          'line-width': ['interpolate', ['linear'], ['zoom'], 9, 2.4, 12, 4, 15, 7, 17, 10]
        }
      });
      map.addLayer({
        id: 'legs-walk', type: 'line', source: 'legs',
        filter: ['==', ['get', 'mode'], 'walk'],
        layout: {'line-cap': 'butt', 'line-join': 'round'},
        paint: {
          'line-color': COLOR.walk,
          'line-width': ['interpolate', ['linear'], ['zoom'], 9, 2, 12, 3.2, 15, 5.5, 17, 8],
          'line-dasharray': [0.4, 1.1]
        }
      });

      /* Pictures, if the page has any. They sit under the numbered stops in the
         DOM order MapLibre gives markers, so a photo taken at a stop never
         covers the stop's own dot. The image is only fetched when its popup
         opens - twenty full-width JPEGs on load would cost more than the map. */
      if (PHOTOS) {
        PHOTOS.features.forEach(function (f) {
          var p = f.properties;
          var el = document.createElement('div');
          el.className = 'photodot';
          el.innerHTML = iconHTML('camera', false);
          el.title = p.time + (p.caption ? ' - ' + p.caption : '');
          var popup = new maplibregl.Popup({offset: 14, closeButton: false,
                                            maxWidth: '300px'});
          popup.on('open', function () {
            var img = popup.getElement().querySelector('img[data-src]');
            if (img) { img.src = img.dataset.src; img.removeAttribute('data-src'); }
          });
          popup.setHTML(
            '<figure class="photo">'
            + '<img data-src="' + p.img + '" alt="'
            + (p.caption || 'Photograph taken at ' + p.time) + '">'
            + '<figcaption><b>' + p.time + '</b>'
            + (p.caption ? '<span>' + p.caption + '</span>' : '')
            + '</figcaption></figure>');
          PHOTO_MARKERS.push(new maplibregl.Marker({element: el})
            .setLngLat(f.geometry.coordinates).setPopup(popup).addTo(map));
        });
      }

      /* One numbered marker per stop, ringed in the colour of how you arrived.
         Do not give .stopdot a position of its own - see the note at the top. */
      STOPS.features.forEach(function (f) {
        var p = f.properties;
        var icon = STOP_ICON[p.key];
        var quiet = QUIET.has(p.key);
        var el = document.createElement('div');
        el.className = 'stopdot ' + p.arrive;
        el.textContent = p.n;
        /* A page with its own palette rings the dot from it; without one the
           .stopdot.<mode> rule in map-common.css still does the work. */
        var ring = colorFor(p.arrive);
        if (ring) el.style.borderColor = ring;
        /* Only the places we stopped get a glyph on the map; transit platforms
           would just crowd the dense clusters. */
        if (icon && !quiet) {
          var badge = document.createElement('div');
          badge.className = 'pin-ico';
          badge.innerHTML = iconHTML(icon, false);
          el.appendChild(badge);
        }
        MARKERS[p.n] = new maplibregl.Marker({element: el})
          .setLngLat(f.geometry.coordinates)
          .setPopup(new maplibregl.Popup({offset: 16, closeButton: false})
            .setHTML('<b>' + iconHTML(icon, quiet) + p.n + '. ' + p.name + '</b>'
                     + (p.note ? '<span>' + p.note + '</span>' : '')))
          .addTo(map);
      });

      /* ?view=<name> frames a detail inset; default fits the whole day. */
      var v = VIEWS[q.get('view')];
      if (v) map.jumpTo(v);
      else map.fitBounds(bounds, {padding: padFor(), duration: 0});

      /* Stop names drawn in-canvas, for insets with no side panel. MapLibre's
         own collision handling drops any that cannot fit. */
      if (q.get('labels')) {
        map.addSource('stops', {type: 'geojson', data: STOPS});
        map.addLayer({
          id: 'stop-labels', type: 'symbol', source: 'stops',
          layout: {
            'text-field': ['get', 'name'],
            'text-font': ['Noto Sans Bold'],
            'text-size': 13,
            'text-anchor': 'left',
            'text-offset': [1.3, 0],
            'text-allow-overlap': false,
            'text-padding': 3
          },
          paint: {
            'text-color': '#14201c',
            'text-halo-color': '#ffffff',
            'text-halo-width': 2.2
          }
        });
      }

      /* Screenshot readiness. 'idle' is the clean signal, but on a big viewport
         it can keep being deferred by trickling tile requests, so fall back to
         a quiet period: style loaded and no data events for 3.5s. */
      global.__mapReady = false;
      var lastData = Date.now();
      map.on('data', function () { lastData = Date.now(); });
      var readyPoll = setInterval(function () {
        if (map.loaded() && Date.now() - lastData > 3500) ready();
      }, 500);
      function ready() { global.__mapReady = true; clearInterval(readyPoll); }
      map.once('idle', ready);
    });

    /* Build the numbered key from the legs, so the list and the map cannot
       drift. Access legs (getting to the platform) and self-loops (a ride that
       returns to where it started) are not steps in the chain. */
    var key = document.getElementById('key');
    var rows = [];
    var chain = LINES.features.filter(function (f) {
      return !f.properties.access && f.properties.from_n !== f.properties.to_n;
    });
    chain.forEach(function (f, i) {
      var p = f.properties;
      if (i === 0) {
        var origin = stopByN(p.from_n);
        rows.push({n: p.from_n, cat: p[CATEGORY], name: p.from,
                   via: (origin && origin.properties.note) || null});
      }
      var seen = rows.some(function (r) { return r.n === p.to_n; });
      rows.push({n: p.to_n, cat: p[CATEGORY],
                 name: (seen ? 'back to ' + p.to : p.to),
                 via: (p.mode === 'walk' ? 'walk ' : p.line + ' · ') + p.km + ' km'});
    });
    rows.forEach(function (r) {
      var f = stopByN(r.n);
      var ikey = f && STOP_ICON[f.properties.key];
      var quiet = !!(f && QUIET.has(f.properties.key));
      var li = document.createElement('li');
      li.className = r.cat;
      li.dataset.n = r.n;
      /* The number's ring is drawn by ::before, which cannot be styled inline,
         so the colour goes in as a custom property the stylesheet reads. */
      var num = colorFor(r.cat);
      if (num) li.style.setProperty('--cat', num);
      li.tabIndex = 0;
      li.setAttribute('role', 'button');
      li.innerHTML = iconHTML(ikey, quiet) + r.name
                   + (r.via ? '<span class="via">' + r.via + '</span>' : '');
      /* The list is the index to the map: a row flies to its stop and opens the
         same popup the marker would. */
      li.addEventListener('click', function () { flyToStop(r.n); });
      li.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); flyToStop(r.n); }
      });
      key.appendChild(li);
    });

    return {map: map, markers: MARKERS, photoMarkers: PHOTO_MARKERS,
            bounds: bounds, flyToStop: flyToStop, flyToPhoto: flyToPhoto,
            flyToFeatures: flyToFeatures, iconHTML: iconHTML};
  }

  global.MapKit = {COLOR: COLOR, ICON_PATHS: ICON_PATHS, ICON_LABEL: ICON_LABEL,
                   iconHTML: iconHTML, render: render};
})(window);
