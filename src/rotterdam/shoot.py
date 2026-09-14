import os, time
from playwright.sync_api import sync_playwright
PAGE = "file://" + os.path.abspath("rotterdam-map.html")
with sync_playwright() as pw:
    b = pw.chromium.launch(channel="chrome", args=["--enable-unsafe-swiftshader"])
    p = b.new_page(viewport={"width": 1200, "height": 950}, device_scale_factor=2)
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto(PAGE, wait_until="load")
    p.wait_for_function("window.__mapReady === true", timeout=180000)
    time.sleep(1.5)
    p.screenshot(path="rtd_check.png")
    print("ok", os.path.getsize("rtd_check.png")//1024, "KB", "| errors:", errs)
    b.close()
