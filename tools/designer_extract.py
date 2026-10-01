import sys
import re
import json
from pathlib import Path
import xml.etree.ElementTree as ET

def parse_resx(filepath):
    """Parse a .resx file and return a dict of name->value for plain strings."""
    data = {}
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        for elem in root.findall('.//data'):
            name = elem.get('name')
            # Check for type or mimetype attributes to skip non-plain strings
            if 'type' in elem.attrib or 'mimetype' in elem.attrib:
                continue
            value_elem = elem.find('value')
            if value_elem is not None:
                val = value_elem.text if value_elem.text is not None else ""
                # Replace actual newlines with literal \n characters as requested
                val = val.replace('\n', '\\n').replace('\r', '')
                data[name] = val
    except Exception:
        pass
    return data

def parse_shortcut(value_str):
    """Convert Keys.Ctrl | Keys.Shift | Keys.N to readable string."""
    if 'Keys.' not in value_str:
        return value_str.strip()
    
    tokens = re.findall(r'Keys\.(\w+)', value_str)
    modifiers = []
    key = None
    
    mod_map = {'Control': 'Ctrl', 'Shift': 'Shift', 'Alt': 'Alt'}
    digit_map = {f'D{i}': str(i) for i in range(10)}
    
    # Order: Ctrl, Shift, Alt, Key
    found_mods = {'Ctrl': False, 'Shift': False, 'Alt': False}
    
    for token in tokens:
        if token in mod_map:
            found_mods[mod_map[token]] = True
        elif token in digit_map:
            key = digit_map[token]
        else:
            # Assume it's the main key if not a modifier or digit
            # If multiple non-modifier tokens, usually the last one is the key in WinForms combos
            key = token
            
    parts = []
    if found_mods['Ctrl']:
        parts.append('Ctrl')
    if found_mods['Shift']:
        parts.append('Shift')
    if found_mods['Alt']:
        parts.append('Alt')
        
    if key:
        parts.append(key)
        
    return '+'.join(parts)

def process_file(filepath, root_dir):
    """Process a single Designer.cs file."""
    rel_path = str(filepath.relative_to(root_dir)).replace('\\', '/')
    
    # Read file content
    try:
        with open(filepath, 'r', encoding='utf-8-sig', errors='replace') as f:
            content = f.read()
    except Exception as e:
        raise IOError(f"Could not read {filepath}: {e}")

    lines = content.splitlines()
    
    # 1. Resource files
    base_name = filepath.stem.replace('.Designer', '')
    dir_path = filepath.parent
    
    neutral_resx = dir_path / f"{base_name}.resx"
    ru_resx = dir_path / f"{base_name}.ru.resx"
    
    neutral_exists = neutral_resx.exists()
    ru_exists = ru_resx.exists()
    
    neutral_data = parse_resx(neutral_resx) if neutral_exists else {}
    ru_data = parse_resx(ru_resx) if ru_exists else {}
    
    # 2. Class info
    class_match = re.search(r'partial\s+class\s+(\w+)\s*:\s*([\w\.]+)', content)
    class_name = class_match.group(1) if class_match else "Unknown"
    base_class = class_match.group(2) if class_match else "Unknown"
    
    # 3. Components
    components = {} # name -> info dict
    
    # Regex for component declaration: this.Name = new Type(
    # We need to find the first occurrence for each name
    comp_decl_re = re.compile(r'^\s*this\.(\w+)\s*=\s*new\s+([\w\.]+)\(', re.MULTILINE)
    
    for match in comp_decl_re.finditer(content):
        name = match.group(1)
        full_type = match.group(2)
        type_name = full_type.split('.')[-1]
        
        # Skip internal components/resources
        if name in ('components', 'resources'):
            continue
            
        line_num = content[:match.start()].count('\n') + 1
        
        if name not in components:
            components[name] = {
                'name': name,
                'type': type_name,
                'full_type': full_type,
                'line': line_num,
                'parent': None,
                'order': None,
                'parent_line': None,
                'props': {},
                'prop_lines': {},
                'shortcut': None,
                'events': [],
                'text_ru': None,
                'text_en': None,
                'tooltip_ru': None,
                'tooltip_en': None,
                'items_ru': [],
                'items_en': [],
                'header_ru': None,
                'header_en': None,
                'text_src': 'none'
            }

    # 4. Container relations (Parent/Child)
    # We need to handle AddRange and Add statements.
    # Strategy: Find all Add/AddRange calls, extract parent and children.
    
    # Regex for AddRange with multi-line support
    # this.Parent.Add(new Type[] { ... }); or this.Parent.AddRange(new Type[] { ... });
    add_range_re = re.compile(
        r'this\.(\w+)\.(?:Controls|DropDownItems|Items|TabPages)\.Add(?:Range)?\s*\(\s*new\s+[\w\.\[\]]+\s*\{([^}]*)\}\s*\)',
        re.DOTALL
    )
    
    # Regex for single Add: this.Parent.Controls.Add(this.Child);
    add_single_re = re.compile(
        r'this\.(\w+)\.(?:Controls|DropDownItems|Items|TabPages)\.Add\s*\(\s*this\.(\w+)\s*\)',
        re.DOTALL
    )
    
    # Helper to get line number for a match
    def get_line(match_obj):
        return content[:match_obj.start()].count('\n') + 1

    # Process AddRange
    for match in add_range_re.finditer(content):
        parent_name = match.group(1)
        inner_content = match.group(2)
        line_num = get_line(match)
        
        # Extract children names from the array initializer
        # Look for this.Name patterns
        children = re.findall(r'this\.(\w+)', inner_content)
        
        if parent_name == 'Controls':
            # This is tricky. Usually it's this.Controls.Add... meaning the form itself.
            # But the regex captures 'Controls' as parent_name if the line starts with this.Controls...
            # Wait, the regex is this.(\w+).Controls... so parent_name is the container name.
            # If the code is `this.Controls.Add(...)`, then parent_name would be empty? 
            # No, `this` is not captured by \w+. 
            # Let's re-examine: `this.P.Controls.Add`. P is captured.
            # What about `this.Controls.Add`? The regex requires this.(\w+).Controls.
            # So `this.Controls.Add` won't match because there's no word between this and Controls.
            pass
            
        if parent_name == '':
             continue

        # Determine actual parent component name
        # If the code is `this.MainMenu.DropDownItems`, parent is MainMenu.
        # If the code is `this.Panel1.Controls`, parent is Panel1.
        
        actual_parent = parent_name
        
        # Special case: if the line starts with `this.Controls.Add`, it means the form itself.
        # Our regex requires a word before Controls/DropDownItems/Items.
        # So `this.Controls` won't match `this.(\w+).Controls`.
        # We need to handle `this.Controls.Add` separately or adjust regex.
        
        for idx, child_name in enumerate(children):
            if child_name in components:
                components[child_name]['parent'] = actual_parent
                components[child_name]['order'] = idx
                components[child_name]['parent_line'] = line_num

    # Process Single Add
    for match in add_single_re.finditer(content):
        parent_name = match.group(1)
        child_name = match.group(2)
        line_num = get_line(match)
        
        if child_name in components:
            components[child_name]['parent'] = parent_name
            # Order is harder to determine with single adds scattered around.
            # We can try to find existing children of this parent and append, 
            # but the prompt asks for order index based on appearance in AddRange.
            # For single adds, we might leave order as None or try to infer.
            # Prompt says: "Record for each child: parent name, order index (0-based, in order of appearance)... For AddRange...".
            # It doesn't explicitly specify order for single Add. We'll leave it as is or update if needed.
            # Let's assume single adds don't define a strict array order like AddRange does.
            components[child_name]['parent_line'] = line_num

    # Handle `this.Controls.Add` specifically (Form level)
    form_controls_add_re = re.compile(
        r'this\.Controls\.Add\s*\(\s*this\.(\w+)\s*\)',
        re.DOTALL
    )
    for match in form_controls_add_re.finditer(content):
        child_name = match.group(1)
        line_num = get_line(match)
        if child_name in components:
            components[child_name]['parent'] = '$form'
            components[child_name]['parent_line'] = line_num

    # Handle `this.Controls.AddRange` specifically (Form level)
    form_controls_addrange_re = re.compile(
        r'this\.Controls\.AddRange\s*\(\s*new\s+[\w\.\[\]]+\s*\{([^}]*)\}\s*\)',
        re.DOTALL
    )
    for match in form_controls_addrange_re.finditer(content):
        inner_content = match.group(1)
        line_num = get_line(match)
        children = re.findall(r'this\.(\w+)', inner_content)
        for idx, child_name in enumerate(children):
            if child_name in components:
                components[child_name]['parent'] = '$form'
                components[child_name]['order'] = idx
                components[child_name]['parent_line'] = line_num

    # 5. Properties
    prop_re = re.compile(r'this\.(\w+)\.(\w+)\s*=\s*(.*?);', re.MULTILINE)
    
    for match in prop_re.finditer(content):
        comp_name = match.group(1)
        prop_name = match.group(2)
        value_str = match.group(3).strip()
        line_num = get_line(match)
        
        if comp_name not in components:
            continue
            
        # Only record specific properties
        allowed_props = {
            'ShortcutKeys', 'ShortcutKeyDisplayString', 'Checked', 'CheckOnClick', 
            'CheckState', 'Enabled', 'Visible', 'Text', 'ToolTipText', 'Dock', 
            'Location', 'Size', 'TabIndex', 'ReadOnly', 'Minimum', 'Maximum', 
            'Value', 'DecimalPlaces', 'Increment', 'DropDownStyle', 'Multiline', 
            'UseVisualStyleBackColor', 'Image'
        }
        
        if prop_name in allowed_props:
            # Trim value to 200 chars
            if len(value_str) > 200:
                value_str = value_str[:200]
                
            components[comp_name]['props'][prop_name] = value_str
            components[comp_name]['prop_lines'][prop_name] = line_num
            
            # Handle ShortcutKeys conversion
            if prop_name == 'ShortcutKeys':
                components[comp_name]['shortcut'] = parse_shortcut(value_str)
                
            # Handle Text source tracking
            if prop_name == 'Text':
                # Check if it's a literal string
                if value_str.startswith('"') and value_str.endswith('"'):
                    components[comp_name]['text_src'] = 'literal'

    # 6. Events
    event_re = re.compile(
        r'this\.(\w+)\.(\w+)\s*\+=\s*new\s+[\w\.<>]+\s*\(\s*this\.(\w+)\s*\)',
        re.DOTALL
    )
    
    for match in event_re.finditer(content):
        comp_name = match.group(1)
        event_name = match.group(2)
        handler_name = match.group(3)
        line_num = get_line(match)
        
        # If comp_name is the form class itself, map to $form? 
        # The prompt says: "catch lines ... where X is the form itself (store under component name "$form")"
        # But our components dict doesn't have an entry for the form class usually.
        # We should probably add a dummy component for $form if needed, or just store events in a separate structure?
        # The output structure expects components list. Let's ensure $form is in components if it has events/props.
        
        target_name = comp_name
        if comp_name == class_name:
            target_name = '$form'
            
        if target_name not in components:
             # Create a minimal entry for the form if it has events
             components[target_name] = {
                'name': target_name,
                'type': base_class.split('.')[-1],
                'full_type': base_class,
                'line': 1, # Approximate
                'parent': None,
                'order': None,
                'parent_line': None,
                'props': {},
                'prop_lines': {},
                'shortcut': None,
                'events': [],
                'text_ru': None,
                'text_en': None,
                'tooltip_ru': None,
                'tooltip_en': None,
                'items_ru': [],
                'items_en': [],
                'header_ru': None,
                'header_en': None,
                'text_src': 'none'
             }
             
        components[target_name]['events'].append({
            'event': event_name,
            'handler': handler_name,
            'line': line_num
        })

    # 7. Resource texts
    # Form title
    form_title_ru = ru_data.get('$this.Text')
    form_title_en = neutral_data.get('$this.Text')
    
    for comp_name, comp_info in components.items():
        # Text
        text_ru = ru_data.get(f"{comp_name}.Text")
        text_en = neutral_data.get(f"{comp_name}.Text")
        
        comp_info['text_ru'] = text_ru
        comp_info['text_en'] = text_en
        
        # Tooltip
        tooltip_ru = ru_data.get(f"{comp_name}.ToolTipText") or ru_data.get(f"{comp_name}.ToolTip")
        tooltip_en = neutral_data.get(f"{comp_name}.ToolTipText") or neutral_data.get(f"{comp_name}.ToolTip")
        
        comp_info['tooltip_ru'] = tooltip_ru
        comp_info['tooltip_en'] = tooltip_en
        
        # Header
        header_ru = ru_data.get(f"{comp_name}.HeaderText")
        header_en = neutral_data.get(f"{comp_name}.HeaderText")
        
        comp_info['header_ru'] = header_ru
        comp_info['header_en'] = header_en
        
        # Items (for ComboBox, ToolStripDropDownButton, etc.)
        items_ru = []
        items_en = []
        
        # Find all keys starting with CompName.Items
        for key in ru_data:
            if key.startswith(f"{comp_name}.Items"):
                items_ru.append(ru_data[key])
        for key in neutral_data:
            if key.startswith(f"{comp_name}.Items"):
                items_en.append(neutral_data[key])
                
        # Sort by key? The prompt says "sorted by key". 
        # We need to sort the values based on their keys.
        # Let's re-fetch and sort properly.
        
        ru_items_dict = {k: v for k, v in ru_data.items() if k.startswith(f"{comp_name}.Items")}
        en_items_dict = {k: v for k, v in neutral_data.items() if k.startswith(f"{comp_name}.Items")}
        
        comp_info['items_ru'] = [v for k, v in sorted(ru_items_dict.items())]
        comp_info['items_en'] = [v for k, v in sorted(en_items_dict.items())]
        
        # Determine text_src
        has_ru_text = f"{comp_name}.Text" in ru_data
        has_neutral_text = f"{comp_name}.Text" in neutral_data
        has_literal_text = comp_info['text_src'] == 'literal'
        
        if has_ru_text:
            comp_info['text_src'] = 'ru'
        elif has_neutral_text and not has_ru_text:
            comp_info['text_src'] = 'neutral-only'
        elif has_literal_text:
            comp_info['text_src'] = 'literal'
        else:
            comp_info['text_src'] = 'none'

    # Convert components dict to list, sorted by line number
    comp_list = sorted(components.values(), key=lambda x: x['line'])
    
    return {
        'file': rel_path,
        'class': class_name,
        'base': base_class,
        'ru_exists': ru_exists,
        'neutral_exists': neutral_exists,
        'form_title_ru': form_title_ru,
        'form_title_en': form_title_en,
        'components': comp_list
    }

def main():
    if len(sys.argv) != 3:
        print("Usage: python designer_extract.py <ROOT_DIR> <OUT_JSON>", file=sys.stderr)
        sys.exit(1)
        
    root_dir = Path(sys.argv[1])
    out_json = Path(sys.argv[2])
    
    if not root_dir.exists():
        print(f"Root directory {root_dir} does not exist.", file=sys.stderr)
        sys.exit(1)
        
    files_data = []
    
    # Find all Designer.cs files
    designer_files = list(root_dir.rglob('*.Designer.cs'))
    
    for filepath in designer_files:
        rel_path_str = str(filepath.relative_to(root_dir)).replace('\\', '/')
        
        # Skip specific files
        if filepath.name == 'Resources.Designer.cs':
            continue
        if filepath.name == 'Settings.Designer.cs':
            continue
        if '/XPTable/' in '/' + rel_path_str:  # rel path has no leading slash (fix 2026-10-01, check_designer.py)
            continue
            
        try:
            file_info = process_file(filepath, root_dir)
            files_data.append(file_info)
        except Exception as e:
            print(f"Error processing {filepath}: {e}", file=sys.stderr)
            
    # Sort files by relative path
    files_data.sort(key=lambda x: x['file'])
    
    output = {
        'root': str(root_dir),
        'files': files_data
    }
    
    # Write JSON
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=1)
        
    # Statistics
    total_files = len(files_data)
    total_components = sum(len(f['components']) for f in files_data)
    ts_menu_items = sum(1 for f in files_data for c in f['components'] if c['type'] == 'ToolStripMenuItem')
    neutral_only_texts = sum(1 for f in files_data for c in f['components'] if c.get('text_src') == 'neutral-only')
    
    print(f"Files: {total_files}")
    print(f"Components: {total_components}")
    print(f"ToolStripMenuItem components: {ts_menu_items}")
    print(f"Neutral-only text sources: {neutral_only_texts}")

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
