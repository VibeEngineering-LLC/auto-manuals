"""Run ON the hidden desktop: list visible top-level windows (EnumWindows) with owner; optional PrintWindow by title.
Usage: hd_list.py [<title_substring> <out.png>]"""
import sys, ctypes as C
sys.stdout.reconfigure(encoding="utf-8")
import win32gui, win32ui
from PIL import Image
found = []
def cb(h, _):
    if win32gui.IsWindowVisible(h) and win32gui.GetWindowText(h):
        found.append(h); print(h, repr(win32gui.GetWindowText(h)), win32gui.GetClassName(h)[:40], "owner", C.windll.user32.GetWindow(h, 4), win32gui.GetWindowRect(h))
win32gui.EnumWindows(cb, None)
if len(sys.argv) > 2:
    h = next(x for x in found if sys.argv[1] in win32gui.GetWindowText(x)); l, t, r, b = win32gui.GetWindowRect(h)
    mdc = win32ui.CreateDCFromHandle(win32gui.GetWindowDC(h)); sdc = mdc.CreateCompatibleDC(); bm = win32ui.CreateBitmap()
    bm.CreateCompatibleBitmap(mdc, r - l, b - t); sdc.SelectObject(bm); C.windll.user32.PrintWindow(h, sdc.GetSafeHdc(), 2); i = bm.GetInfo()
    Image.frombuffer("RGB", (i["bmWidth"], i["bmHeight"]), bm.GetBitmapBits(True), "raw", "BGRX", 0, 1).save(sys.argv[2]); print("saved", sys.argv[2])
