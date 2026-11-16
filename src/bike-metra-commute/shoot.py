"""Render the built page and screenshot it, so layout and JS errors surface.

Three shots: the whole route, the Aurora end - where all the colour changes
are, and which the opening frame is far too wide to show - and a phone.

    .venv/bin/python src/bike-metra-commute/shoot.py
"""
import os, sys, time
from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PAGE = "file://" + os.path.join(ROOT, "bike-metra-commute-map.html")
OUT  = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "bmc_check.png")
STEM = os.path.splitext(OUT)[0]

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="chrome", args=["--enable-unsafe-swiftshader"])
    p = b.new_page(viewport={"width": 1200, "height": 950}, device_scale_factor=2)
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.on("requestfailed", lambda r: errs.append("failed " + r.url.split("/")[-1]))
    p.goto(PAGE, wait_until="load")
    try:
        p.wait_for_function("window.__mapReady === true", timeout=180000)
    except Exception:
        # A throw inside the map's load handler never sets the flag; the
        # error it threw is the useful part, not the timeout.
        raise SystemExit(f"map never became ready; errors: {errs}")
    time.sleep(1.5)
    p.screenshot(path=OUT)

    stray = p.evaluate("""(() => {
        const r = document.getElementById('map').getBoundingClientRect();
        return [...document.querySelectorAll('.stopdot')].filter(el => {
          const b = el.getBoundingClientRect();
          return b.top < r.top - 5 || b.bottom > r.bottom + 5;
        }).length; })()""")
    dots = p.evaluate("document.querySelectorAll('.stopdot').length")
    rows = p.evaluate("document.querySelectorAll('#key li').length")
    bars = p.evaluate("document.querySelectorAll('#strip div').length")
    print(f"{dots} markers ({stray} outside the canvas), {rows} key rows, "
          f"{bars} strip segments")

    for i, name in ((0, "chicago"), (1, "aurora")):
        p.evaluate(f"document.querySelectorAll('#parts .day')[{i}].click()")
        # The flight crosses 30 miles of tiles nobody asked for; a fixed sleep
        # caught the canvas blank. Wait for the camera to stop and the tiles
        # under it to arrive.
        time.sleep(1)
        p.wait_for_function("!map.isMoving() && map.areTilesLoaded()",
                            timeout=120000)
        time.sleep(2)
        p.screenshot(path=f"{STEM}_{name}.png")

    p.set_viewport_size({"width": 390, "height": 800})
    p.reload(wait_until="load")
    p.wait_for_function("window.__mapReady === true", timeout=180000)
    time.sleep(1.5)
    p.screenshot(path=f"{STEM}_phone.png")
    print("errors:", errs)
    b.close()
