# HARD SAFETY RULE: This script must contain NO calls to invoke, click, click_input, select, type_keys, send_keys, press, set_focus on menu items.
import sys
import json
import time
from pywinauto import Desktop

sys.stdout.reconfigure(encoding='utf-8')

def find_window(title_substring):
    desktop = Desktop(backend="uia")
    for _ in range(30):
        windows = desktop.windows()
        for w in windows:
            try:
                if title_substring.lower() in w.window_text().lower():
                    return w
            except Exception:
                continue
        time.sleep(1)
    print(f"Window containing '{title_substring}' not found.", file=sys.stderr)
    sys.exit(2)

def get_menu_bar(window):
    try:
        menu_bars = window.descendants(control_type="MenuBar")
        for mb in menu_bars:
            name = mb.window_text()
            if name.lower() in ["system", "системное"]:
                continue
            # Check children to ensure it's not the system menu bar disguised
            try:
                children = mb.children(control_type="MenuItem")
                if children:
                    return mb
            except Exception:
                pass
        # Fallback: take first non-system MenuBar
        for mb in menu_bars:
            name = mb.window_text()
            if name.lower() not in ["system", "системное"]:
                return mb
    except Exception as e:
        print(f"Error finding menu bar: {e}", file=sys.stderr)
    return None

def walk(item, depth, path, errors, seen_rects):
    result = {}
    try:
        name = item.window_text()
        automation_id = ""
        try:
            automation_id = item.element_info.automation_id
        except Exception:
            pass
        
        enabled = False
        try:
            enabled = item.is_enabled()
        except Exception:
            pass
            
        rect = [0, 0, 0, 0]
        try:
            r = item.rectangle()
            rect = [r.left, r.top, r.right, r.bottom]
        except Exception:
            pass
            
        accelerator = ""
        try:
            accelerator = item.element_info.element.CurrentAcceleratorKey
            if not accelerator:
                accelerator = ""
        except Exception:
            accelerator = ""
            
        current_path = path + [name]
        
        result["name"] = name
        result["automation_id"] = automation_id
        result["enabled"] = enabled
        result["rect"] = rect
        result["accelerator"] = accelerator
        result["path"] = current_path
        result["children"] = []
        result["separator"] = False
        
        # Track this item to avoid duplicates in children collection
        seen_rects.add((name, tuple(rect)))
        
        # Check for submenu capability
        has_submenu = False
        try:
            iface = item.iface_expand_collapse
            if iface:
                state = iface.CurrentExpandCollapseState
                # 3 is LeafNode. If not leaf, it might have children.
                if state != 3:
                    has_submenu = True
        except Exception:
            pass
            
        if has_submenu and enabled:
            try:
                item.expand()
                time.sleep(0.4)
                
                # Find the dropdown window
                desktop = Desktop(backend="uia")
                all_menus_before = set(id(w) for w in desktop.windows(control_type="Menu"))
                
                # Small delay to allow UI update
                time.sleep(0.1)
                
                all_menus_after = set(id(w) for w in desktop.windows(control_type="Menu"))
                new_menu_ids = all_menus_after - all_menus_before
                
                child_items = []
                separators = []
                
                if new_menu_ids:
                    # Get the new menu windows
                    current_windows = desktop.windows(control_type="Menu")
                    target_windows = [w for w in current_windows if id(w) in new_menu_ids]
                    
                    # If multiple, try to pick the one closest to the item
                    if len(target_windows) > 1:
                        best_w = None
                        min_dist = float('inf')
                        item_rect = rect
                        for w in target_windows:
                            try:
                                wr = w.rectangle()
                                # Distance from item bottom to menu top
                                dist = abs(wr.top - (item_rect[1] + (item_rect[3]-item_rect[1])))
                                if dist < min_dist:
                                    min_dist = dist
                                    best_w = w
                            except Exception:
                                pass
                        if best_w:
                            target_windows = [best_w]
                    
                    for mw in target_windows:
                        try:
                            # Get menu items from the dropdown window
                            mi_children = mw.children(control_type="MenuItem")
                            sep_children = mw.children(control_type="Separator")
                            
                            for c in mi_children:
                                cname = c.window_text()
                                crect = [0,0,0,0]
                                try:
                                    cr = c.rectangle()
                                    crect = [cr.left, cr.top, cr.right, cr.bottom]
                                except Exception:
                                    pass
                                
                                key = (cname, tuple(crect))
                                if key not in seen_rects:
                                    child_items.append(c)
                                    
                            for s in sep_children:
                                separators.append(s)
                        except Exception as e:
                            errors.append(f"{current_path}: {e}")
                else:
                    # Fallback: try item.children()
                    try:
                        mi_children = item.children(control_type="MenuItem")
                        sep_children = item.children(control_type="Separator")
                        
                        for c in mi_children:
                            cname = c.window_text()
                            crect = [0,0,0,0]
                            try:
                                cr = c.rectangle()
                                crect = [cr.left, cr.top, cr.right, cr.bottom]
                            except Exception:
                                pass
                            
                            key = (cname, tuple(crect))
                            if key not in seen_rects:
                                child_items.append(c)
                                
                        for s in sep_children:
                            separators.append(s)
                    except Exception as e:
                        errors.append(f"{current_path}: {e}")
                
                # Process separators and children
                # We need to interleave separators and items based on position if possible, 
                # but for simplicity, we'll add separators as distinct entries.
                # A more robust approach would sort by Y coordinate.
                
                all_elements = []
                for c in child_items:
                    try:
                        cr = c.rectangle()
                        all_elements.append(('item', c, cr.top))
                    except Exception:
                        pass
                        
                for s in separators:
                    try:
                        sr = s.rectangle()
                        all_elements.append(('sep', s, sr.top))
                    except Exception:
                        pass
                
                # Sort by Y position
                all_elements.sort(key=lambda x: x[2])
                
                for etype, elem, _ in all_elements:
                    if etype == 'sep':
                        result["children"].append({"separator": True})
                    else:
                        if depth < 6:
                            child_result = walk(elem, depth + 1, current_path, errors, seen_rects)
                            if child_result:
                                result["children"].append(child_result)
                        else:
                            # Max depth reached, just record basic info
                            cname = elem.window_text()
                            cautomation_id = ""
                            try:
                                cautomation_id = elem.element_info.automation_id
                            except Exception:
                                pass
                            cenabled = False
                            try:
                                cenabled = elem.is_enabled()
                            except Exception:
                                pass
                            crect = [0,0,0,0]
                            try:
                                cr = elem.rectangle()
                                crect = [cr.left, cr.top, cr.right, cr.bottom]
                            except Exception:
                                pass
                            
                            result["children"].append({
                                "name": cname,
                                "automation_id": cautomation_id,
                                "enabled": cenabled,
                                "rect": crect,
                                "accelerator": "",
                                "path": current_path + [cname],
                                "children": [],
                                "separator": False
                            })
                            
            except Exception as e:
                errors.append(f"{current_path}: {e}")
                
            # Collapse
            try:
                item.collapse()
                time.sleep(0.3)
            except Exception:
                pass
                
    except Exception as e:
        errors.append(f"{path}: {e}")
        
    return result

def main():
    if len(sys.argv) < 3:
        print("Usage: python menu_walk.py <WINDOW_TITLE_SUBSTRING> <OUT_JSON>", file=sys.stderr)
        sys.exit(1)
        
    title_substring = sys.argv[1]
    out_json = sys.argv[2]
    
    window = find_window(title_substring)
    menu_bar = get_menu_bar(window)
    
    if not menu_bar:
        print("No suitable MenuBar found.", file=sys.stderr)
        sys.exit(2)
        
    errors = []
    seen_rects = set()
    menus = []
    
    try:
        top_items = menu_bar.children(control_type="MenuItem")
        for item in top_items:
            result = walk(item, 0, [], errors, seen_rects)
            if result:
                menus.append(result)
    except Exception as e:
        errors.append(f"Top level error: {e}")
        
    # Count items and submenus
    count_items = len(menus)
    count_submenus = 0
    
    def count_recursive(items):
        nonlocal count_submenus
        for item in items:
            if "children" in item and item["children"]:
                count_submenus += 1
                count_recursive(item["children"])
                
    count_recursive(menus)
    
    output = {
        "window": window.window_text(),
        "menus": menus,
        "count_items": count_items,
        "count_submenus": count_submenus,
        "errors": errors
    }
    
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=1)
        
    print(f"Top menus: {len(menus)}")
    print(f"Total items: {count_items}")
    print(f"Submenus: {count_submenus}")
    print(f"Errors: {len(errors)}")

if __name__ == "__main__":
    main()
