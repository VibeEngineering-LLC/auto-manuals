"""Start a process on a hidden Win32 desktop in the same session (user's visible desktop untouched).
Usage: hdesk.py <desktop_name> <cwd> <cmdline...>   -> prints PID, waits for child exit (run in background)."""
import sys, ctypes as C, ctypes.wintypes as W
sys.stdout.reconfigure(encoding="utf-8")
k, u = C.windll.kernel32, C.windll.user32
name, cwd, cmd = sys.argv[1], sys.argv[2], " ".join(sys.argv[3:])
u.CreateDesktopW.restype = W.HANDLE
h = u.CreateDesktopW(name, None, None, 0, 0x10000000, None)  # GENERIC_ALL; opens existing if present
if not h: sys.exit("CreateDesktop failed %d" % k.GetLastError())
class SI(C.Structure):
    _fields_ = [("cb", W.DWORD), ("res", W.LPWSTR), ("desk", W.LPWSTR), ("title", W.LPWSTR)] + \
               [("d%d" % i, W.DWORD) for i in range(8)] + \
               [("show", W.WORD), ("cbr2", W.WORD), ("r2", C.c_void_p), ("i", W.HANDLE), ("o", W.HANDLE), ("e", W.HANDLE)]
class PI(C.Structure):
    _fields_ = [("hp", W.HANDLE), ("ht", W.HANDLE), ("pid", W.DWORD), ("tid", W.DWORD)]
si, pi = SI(), PI(); si.cb = C.sizeof(SI); si.desk = "WinSta0\\" + name
if not k.CreateProcessW(None, C.create_unicode_buffer(cmd), None, None, False, 0, None, cwd, C.byref(si), C.byref(pi)):
    sys.exit("CreateProcess failed %d" % k.GetLastError())
print(pi.pid, flush=True)
k.WaitForSingleObject(pi.hp, 0xFFFFFFFF)  # hold the desktop handle until the child exits (else desktop is destroyed)
