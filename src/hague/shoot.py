"""Screenshot the map page, waiting for MapLibre to actually finish drawing."""
import os, sys, time
from playwright.sync_api import sync_playwright

PAGE = "file://" + os.path.abspath("hague-map.html")
SHOTS = [
    ("?nohead=1&nochrome=1",                          1400, 1638, "shot_overview.png"),
    ("?view=denhaag&nopanel=1&labels=1&nochrome=1",    620,  660, "shot_denhaag.png"),
    ("?view=scheveningen&nopanel=1&labels=1&nochrome=1", 620, 440, "shot_scheveningen.png"),
    ("?view=delft&nopanel=1&labels=1&nochrome=1",      620,  440, "shot_delft.png"),
]

with sync_playwright() as pw:
    browser = pw.chromium.launch(channel="chrome", args=["--enable-unsafe-swiftshader"])
    for query, w, h, out in SHOTS:
        page = browser.new_page(viewport={"width": w, "height": h},
                                device_scale_factor=2)
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.goto(PAGE + query, wait_until="load")
        # __mapReady is set on MapLibre's 'idle' event: style parsed, all
        # tiles for the current view fetched, and the frame painted.
        page.wait_for_function("window.__mapReady === true", timeout=180000)
        time.sleep(1.5)   # let label collision-resolution settle
        page.screenshot(path=out)
        size = os.path.getsize(out)
        print(f"{out:22s} {w}x{h}  {size/1024:7.0f} KB"
              + (f"  ERRORS: {errs}" if errs else ""))
        page.close()
    browser.close()
