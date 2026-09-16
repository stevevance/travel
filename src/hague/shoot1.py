import os, time
from playwright.sync_api import sync_playwright
PAGE = "file://" + os.path.abspath("hague-map.html")
with sync_playwright() as pw:
    b = pw.chromium.launch(channel="chrome", args=["--enable-unsafe-swiftshader"])
    p = b.new_page(viewport={"width": 620, "height": 440}, device_scale_factor=2)
    p.goto(PAGE + "?view=scheveningen&labels=1", wait_until="load")
    p.wait_for_function("window.__mapReady === true", timeout=180000)
    time.sleep(1.5)
    p.screenshot(path="shot_scheveningen.png")
    print("shot_scheveningen.png", os.path.getsize("shot_scheveningen.png") // 1024, "KB")
    b.close()
