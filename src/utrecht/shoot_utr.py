from playwright.sync_api import sync_playwright
import pathlib, sys
src = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "utrecht-itinerary.html").resolve().as_uri()
out = sys.argv[2] if len(sys.argv) > 2 else "shot.png"
with sync_playwright() as pw:
    b = pw.chromium.launch(channel="chrome", args=["--enable-unsafe-swiftshader"])
    pg = b.new_page(viewport={"width":1000,"height":1200}, device_scale_factor=2)
    errs=[]
    pg.on("console", lambda m: errs.append(m.text) if m.type=="error" else None)
    pg.on("pageerror", lambda e: errs.append("PAGEERROR: %s"%e))
    pg.goto(src, wait_until="networkidle", timeout=60000)
    pg.wait_for_timeout(4000)
    pg.screenshot(path=out, full_page=True)
    b.close()
    print("errors:", errs if errs else "none")
print("saved", out)
