import os, time
from playwright.sync_api import sync_playwright
PAGE = "file://" + os.path.abspath("rotterdam-map.html")
with sync_playwright() as pw:
    b = pw.chromium.launch(channel="chrome", args=["--enable-unsafe-swiftshader"])
    p = b.new_page(viewport={"width": 900, "height": 800}, device_scale_factor=2)
    p.goto(PAGE + "?nopanel=1&nochrome=1", wait_until="load")
    p.wait_for_function("window.__mapReady === true", timeout=180000)
    p.evaluate("window.map.jumpTo({center:[4.48590, 51.94095], zoom:17.0})")
    time.sleep(6)
    p.screenshot(path="peek_jog.png")
    print("peek_jog.png", os.path.getsize("peek_jog.png")//1024, "KB")
    b.close()
