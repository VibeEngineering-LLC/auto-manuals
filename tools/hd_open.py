"""Run ON the hidden desktop (own BecqMoni copy only): open menu path, PrintWindow every new top-level window.
Usage: hd_open.py <out_prefix> <Menu> [<Sub> ...]   e.g. hd_open.py fig-dev Инструменты "Конфигурация устройства..." """
import sys, time, ctypes as C
sys.stdout.reconfigure(encoding="utf-8")
from pywinauto import Desktop
from PIL import Image
import win32gui, win32ui
def shot(hw, out):
    l, t, r, b = win32gui.GetWindowRect(hw); mdc = win32ui.CreateDCFromHandle(win32gui.GetWindowDC(hw))
    sdc = mdc.CreateCompatibleDC(); bm = win32ui.CreateBitmap(); bm.CreateCompatibleBitmap(mdc, r - l, b - t); sdc.SelectObject(bm)
    C.windll.user32.PrintWindow(hw, sdc.GetSafeHdc(), 2); i = bm.GetInfo()
    Image.frombuffer("RGB", (i["bmWidth"], i["bmHeight"]), bm.GetBitmapBits(True), "raw", "BGRX", 0, 1).save(out); print("saved", out, r - l, b - t)
d = Desktop(backend="uia"); main = next(w for w in d.windows() if "BecqMoni" in w.window_text())
before = {w.handle for w in d.windows()}
item = next(m for m in main.descendants(control_type="MenuItem") if m.window_text().replace("&", "") == sys.argv[2])
for name in sys.argv[3:]:
    item.expand(); time.sleep(0.5)
    item = next(m for w in d.windows() for m in w.descendants(control_type="MenuItem") if m.window_text().replace("&", "") == name)
item.invoke(); time.sleep(3)
new = [w for w in d.windows() if w.handle not in before and w.window_text()]
for k, w in enumerate(new): print("NEW", repr(w.window_text())); shot(w.handle, f"{sys.argv[1]}-{k}.png")
shot(main.handle, f"{sys.argv[1]}-main.png")
