Write ONE complete Python 3 script. Output ONLY the code, no prose, no markdown fences.

Purpose: walk the menu bar of a running WinForms application through UI Automation (pywinauto, backend "uia") and dump the full menu tree to JSON WITHOUT ever activating (invoking/clicking) any menu command. Only expand/collapse is allowed.

Usage: python menu_walk.py <WINDOW_TITLE_SUBSTRING> <OUT_JSON>
At start: `sys.stdout.reconfigure(encoding='utf-8')`. Write JSON with `ensure_ascii=False, indent=1`, encoding utf-8.
Imports allowed: sys, json, time, pywinauto (`from pywinauto import Desktop`).

Steps:
1. Find the top-level window: `Desktop(backend="uia").windows()` whose `window_text()` contains the substring; retry up to 30 times with 1 s sleep. If not found: print error to stderr, exit code 2.
2. Find the first descendant with control_type "MenuBar" whose name is NOT "System" / "Системное" (WinForms windows also expose a system menu bar named "System"; skip any MenuBar whose children are named like "System"). Its children with control_type "MenuItem" are top-level menus.
3. For each top-level menu item, call a recursive function `walk(item, depth, path)`:
   - Record: `name` = item.window_text(), `automation_id` = item.element_info.automation_id, `enabled` = item.is_enabled(), `rect` = [l,t,r,b] of item.rectangle(), `accelerator` = item.element_info.element.CurrentAcceleratorKey (wrap in try/except -> ""), `path` = list of names from top.
   - Determine whether it has a submenu: try `item.iface_expand_collapse` (wrap in try/except). If the pattern exists and `CurrentExpandCollapseState` != 3 (LeafNode): it is a submenu. Call `item.expand()` (NEVER `invoke()`, NEVER `click_input()`, NEVER `select()`), sleep 0.4 s.
   - After expanding, the drop-down appears as a separate top-level window or as a child "Menu" control. Collect child menu items as: all elements with control_type "MenuItem" found in `Desktop(backend="uia").windows()` of control_type "Menu" (the drop-down windows) PLUS `item.children()` of control_type "MenuItem"; keep only those NOT already recorded at an ancestor level (dedupe by (name, rect)); choose the drop-down that appeared most recently: compare the set of Menu windows before and after expand, take the new one(s); fallback: the Menu window whose rectangle top >= item rect bottom - 5 and left within 400 px of item rect left.
   - Separators: elements with control_type "Separator" in the same drop-down: record as {"separator": true} in order.
   - Recurse into each child with depth+1 (max depth 6).
   - After children are processed, collapse: `item.collapse()` in try/except, sleep 0.3 s. If collapse fails, send nothing else (no keystrokes, no clicks) — just continue.
   - Disabled items: record, do not expand.
4. Hard safety rule: the script must contain NO calls to `invoke`, `click`, `click_input`, `select`, `type_keys`, `send_keys`, `press`, `set_focus` on menu items. A comment at the top must state this.
5. Output JSON: {"window": title, "menus": [ {name, automation_id, enabled, accelerator, rect, children:[...] or [] , "separator": bool} ... ], "count_items": N, "count_submenus": M, "errors": [strings]}.
6. Wrap each item processing in try/except; on exception append f"{path}: {exc}" to errors and continue.
7. At the end print to stdout: number of top menus, total items, submenus, errors count.
