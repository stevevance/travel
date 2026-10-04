"""Render the built page and screenshot it, so layout and JS errors surface.

Two shots: the whole ride, and one stop popup open, because the popup is where
this page's longest piece of copy and its only outbound links live.

    .venv/bin/python src/chicago-new-things/shoot.py
"""
import os, sys, time
from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PAGE = "file://" + os.path.join(ROOT, "chicago-new-things-map.html")
OUT  = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "chi_check.png")
POP  = os.path.splitext(OUT)[0] + "_popup.png"

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="chrome", args=["--enable-unsafe-swiftshader"])
    p = b.new_page(viewport={"width": 1200, "height": 950}, device_scale_factor=2)
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.on("requestfailed", lambda r: errs.append("failed " + r.url.split("/")[-1]))
    p.goto(PAGE, wait_until="load")
    p.wait_for_function("window.__mapReady === true", timeout=180000)
    time.sleep(1.5)
    p.screenshot(path=OUT)

    # Markers stacking down the page is the bug this repo keeps re-finding, and
    # it is invisible in the source. Fourteen dots inside the canvas is the
    # check; one outside it means .stopdot got a position again.
    stray = p.evaluate("""(() => {
        const r = document.getElementById('map').getBoundingClientRect();
        return [...document.querySelectorAll('.stopdot')].filter(el => {
          const b = el.getBoundingClientRect();
          return b.top < r.top - 5 || b.bottom > r.bottom + 5;
        }).length; })()""")
    dots = p.evaluate("document.querySelectorAll('.stopdot').length")
    rows = p.evaluate("document.querySelectorAll('#key li').length")
    glyphs = p.evaluate("document.querySelectorAll('.legend .ico').length")
    print(f"{dots} markers ({stray} outside the canvas), {rows} key rows, "
          f"{glyphs} legend glyphs")

    p.evaluate("document.querySelectorAll('.stopdot')[3].click()")
    p.wait_for_selector(".maplibregl-popup", timeout=15000)
    time.sleep(0.8)
    p.screenshot(path=POP)
    print("errors:", errs)
    b.close()
