"""designer.json -> markdown tree of one form's menus (RU label, EN label, shortcut, Click handler file:line).
Usage: menu_tree_md.py <designer.json> <form_file_rel> <out.md>"""
import sys, json
sys.stdout.reconfigure(encoding="utf-8")
d = json.load(open(sys.argv[1], encoding="utf-8"))
f = next(x for x in d["files"] if x["file"] == sys.argv[2])
comps = {c["name"]: c for c in f["components"]}
kids = {}
for c in f["components"]:
    if c.get("parent"): kids.setdefault(c["parent"], []).append(c)
out = ["# Меню: " + f["file"], "", "Источник: `" + d["root"] + "`. Подпись RU / EN | клавиши | обработчик Click (строка Designer).", ""]
def walk(name, depth):
    for c in sorted(kids.get(name, []), key=lambda c: c.get("order") or 0):
        if c["type"] == "ToolStripSeparator": out.append("  " * depth + "- ———"); continue
        if c["type"] != "ToolStripMenuItem" and not c["type"].startswith("MenuStrip"): continue
        ev = ", ".join(f'{e["handler"]} (:{e["line"]})' for e in c.get("events", []) if e["event"] == "Click")
        ru = c.get("text_ru") or "⚠ нет RU"
        out.append("  " * depth + f'- **{ru}** / {c.get("text_en") or ""} | {c.get("shortcut") or ""} | {ev} | `{c["name"]}` :{c["line"]}')
        walk(c["name"], depth + 1)
for m in [c for c in f["components"] if c["type"].startswith(("MenuStrip", "ContextMenuStrip"))]:  # incl. MenuStripEx
    out.append(f'## {m["name"]}'); walk(m["name"], 0); out.append("")
open(sys.argv[3], "w", encoding="utf-8").write("\n".join(out) + "\n")
print("lines", len(out))
