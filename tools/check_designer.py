"""Independent recount for designer.json: per-file component and menu counts by plain regex, diff against JSON.
Usage: check_designer.py <ROOT_DIR> <designer.json>   -> prints mismatching files and totals."""
import sys, json, re, pathlib
sys.stdout.reconfigure(encoding="utf-8")
root, js = pathlib.Path(sys.argv[1]), json.load(open(sys.argv[2], encoding="utf-8"))
decl = re.compile(r"^\s*this\.(\w+) = new ([\w.]+)(?:<[^>]*>)?\(", re.M)
g = {}
for p in root.rglob("*.Designer.cs"):
    rel = p.relative_to(root).as_posix()
    if p.name in ("Resources.Designer.cs", "Settings.Designer.cs") or "/XPTable/" in "/" + rel: continue
    names = {}
    for n, t in decl.findall(p.read_text(encoding="utf-8-sig", errors="replace")):
        if n not in ("components", "resources"): names.setdefault(n, t.split(".")[-1])
    g[rel] = (len(names), sum(1 for t in names.values() if t == "ToolStripMenuItem"))
j = {f["file"]: (len(f["components"]), sum(1 for c in f["components"] if c["type"] == "ToolStripMenuItem")) for f in js["files"]}
for f in sorted(set(g) | set(j)):
    if g.get(f) != j.get(f): print("DIFF", f, "regex", g.get(f), "json", j.get(f))
print("files regex/json", len(g), len(j), "| comps", sum(v[0] for v in g.values()), sum(v[0] for v in j.values()),
      "| menu", sum(v[1] for v in g.values()), sum(v[1] for v in j.values()))
