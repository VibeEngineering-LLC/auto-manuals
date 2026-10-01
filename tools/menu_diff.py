"""Diff live UIA menu (menu_walk.py JSON) vs source map (designer_extract.py JSON) by RU label paths.
Usage: menu_diff.py <live-menu.json> <designer.json> <form_file_rel>"""
import sys, json
sys.stdout.reconfigure(encoding="utf-8")
live, des = json.load(open(sys.argv[1], encoding="utf-8")), json.load(open(sys.argv[2], encoding="utf-8"))
clean = lambda s: (s or "").replace("&", "").strip()
lp, sp, kids = set(), {}, {}
def wl(nodes, path):
    for n in nodes:
        if n.get("name"): p = path + (clean(n["name"]),); lp.add(p); wl(n.get("children", []), p)
f = next(x for x in des["files"] if x["file"] == sys.argv[3])
for c in f["components"]:
    if c["type"] == "ToolStripMenuItem" and c.get("parent"): kids.setdefault(c["parent"], []).append(c)
def ws(name, path):
    for c in kids.get(name, []): p = path + (clean(c.get("text_ru") or c.get("text_en")),); sp[p] = c; ws(c["name"], p)
wl(live["menus"], ())
for m in [c for c in f["components"] if c["type"].startswith("MenuStrip")]: ws(m["name"], ())
print(f"live {len(lp)} | source {len(sp)} | common {len(lp & set(sp))}")
for p in sorted(set(sp) - lp): print("ТОЛЬКО В ИСХОДНИКАХ:", " => ".join(p), f'(`{sp[p]["name"]}` :{sp[p]["line"]})')
for p in sorted(lp - set(sp)): print("ТОЛЬКО В ЖИВОЙ:", " => ".join(p))
