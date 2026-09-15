"""Render the built page and screenshot it, so layout and JS errors surface."""
import os, sys, time
from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PAGE = "file://" + os.path.join(ROOT, "utrecht-map.html")
OUT  = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "utr_check.png")
with sync_playwright() as pw:
    b = pw.chromium.launch(channel="chrome", args=["--enable-unsafe-swiftshader"])
    p = b.new_page(viewport={"width": 1200, "height": 950}, device_scale_factor=2)
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto(PAGE, wait_until="load")
    p.wait_for_function("window.__mapReady === true", timeout=180000)
    time.sleep(1.5)
    p.screenshot(path=OUT)
    print("ok", os.path.getsize(OUT)//1024, "KB", "| errors:", errs)
    b.close()
