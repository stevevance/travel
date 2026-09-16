"""Render the built page and screenshot it, so layout and JS errors surface.

Two shots, because this page has two things worth looking at: the whole day, and
one photo popup open - the picture is only fetched when its popup opens, so a
broken image path shows up nowhere else.

    .venv/bin/python src/bruges/shoot.py
"""
import os, sys, time
from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PAGE = "file://" + os.path.join(ROOT, "bruges-map.html")
OUT  = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "bru_check.png")
POP  = os.path.splitext(OUT)[0] + "_photo.png"

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="chrome", args=["--enable-unsafe-swiftshader"])
    p = b.new_page(viewport={"width": 1200, "height": 950}, device_scale_factor=2)
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    # A picture that 404s is a console failure, not a page error, so watch both.
    p.on("requestfailed", lambda r: errs.append("failed " + r.url.split("/")[-1]))
    p.goto(PAGE, wait_until="load")
    p.wait_for_function("window.__mapReady === true", timeout=180000)
    time.sleep(1.5)
    p.screenshot(path=OUT)
    print("whole day:", os.path.getsize(OUT)//1024, "KB")

    # Open the middle picture and wait for the JPEG itself to decode.
    n = p.evaluate("document.querySelectorAll('.photodot').length")
    p.evaluate("document.querySelectorAll('.photodot')"
               "[Math.floor(document.querySelectorAll('.photodot').length/2)].click()")
    p.wait_for_selector("figure.photo img", timeout=15000)
    p.wait_for_function(
        "(() => {const i = document.querySelector('figure.photo img');"
        " return i && i.complete && i.naturalWidth > 0;})()", timeout=30000)
    time.sleep(1.0)
    p.screenshot(path=POP)
    print(f"{n} photo dots; popup:", os.path.getsize(POP)//1024, "KB")
    print("errors:", errs)
    b.close()
