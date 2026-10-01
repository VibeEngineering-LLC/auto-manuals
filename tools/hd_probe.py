"""Run ON the hidden desktop: list top-level UIA windows, save PrintWindow PNG of the BecqMoni main window.
Usage: hd_probe.py <out.png>"""
import sys, time, ctypes as C
sys.stdout.reconfigure(encoding="utf-8")
from pywinauto import Desktop
from PIL import Image
import win32gui, win32ui
out, ws = sys.argv[1], []
for _ in range(40):
    ws = [w for w in Desktop(backend="uia").windows() if "BecqMoni" in (w.window_text() or "")]
    if ws: break
    time.sleep(1)
for w in Desktop(backend="uia").windows(): print("WIN", repr(w.window_text()), w.rectangle())
if not ws: sys.exit("BecqMoni window not found")
hw = ws[0].handle; l, t, r, b = win32gui.GetWindowRect(hw); wd, ht = r - l, b - t
mdc = win32ui.CreateDCFromHandle(win32gui.GetWindowDC(hw)); sdc = mdc.CreateCompatibleDC()
bm = win32ui.CreateBitmap(); bm.CreateCompatibleBitmap(mdc, wd, ht); sdc.SelectObject(bm)
ok = C.windll.user32.PrintWindow(hw, sdc.GetSafeHdc(), 2)
i = bm.GetInfo(); Image.frombuffer("RGB", (i["bmWidth"], i["bmHeight"]), bm.GetBitmapBits(True), "raw", "BGRX", 0, 1).save(out)
print("PrintWindow", ok, "saved", out, wd, ht)
