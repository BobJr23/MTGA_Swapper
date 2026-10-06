"""Windows for role browsing, frame bindings, and serialized color palettes."""
import json
from pathlib import Path
from copy import deepcopy
from src.asset_catalog import AssetCatalog, load_object, object_image
from src.crop_preview import png_bytes
from src.theme_editor import ThemeDocument, THEME_TREES, Binding, at, color_fields, recolor, refresh_color_schemes

def catalog_for_database(database_file):
    return AssetCatalog.load(Path(database_file).parent.parent)

def image_preview(image, size=(440, 290), alpha=False):
    from PIL import Image, ImageDraw
    image = image.convert("RGBA")
    image.thumbnail(size, Image.Resampling.LANCZOS)
    if alpha:
        image = image.getchannel("A").convert("RGBA")
    canvas = Image.new("RGBA", image.size, "#333333")
    draw = ImageDraw.Draw(canvas)
    for y in range(0, image.height, 12):
        for x in range(0, image.width, 12):
            if (x // 12 + y // 12) % 2:
                draw.rectangle((x, y, x + 11, y + 11), fill="#555555")
    canvas.alpha_composite(image)
    return png_bytes(canvas)

def create_asset_browser(database_file, catalog=None, choose=False, allowed_paths=None):
    import FreeSimpleGUI as sg
    catalog = catalog or catalog_for_database(database_file)
    roles = ["All"] + sorted({r.role for r in catalog.records})
    layout = [
        [sg.Text("Role"), sg.Combo(roles, default_value="All", readonly=True, key="role", enable_events=True),
         sg.Input(key="query", size=(45, 1)), sg.Button("Search"),
         sg.Checkbox("Downloaded only", key="downloaded", enable_events=True)],
        [sg.Table([], headings=["Role", "Indexed path", "Bundle"], col_widths=[16, 75, 40],
                  auto_size_columns=False, num_rows=16, key="assets", enable_events=True,
                  select_mode=sg.TABLE_SELECT_MODE_BROWSE)],
        [sg.Text("", key="count", size=(100, 1))],
        [sg.Multiline("", key="details", size=(76, 15), disabled=True), sg.Image(key="preview")],
        [sg.Checkbox("Show alpha channel", key="alpha", enable_events=True),
         sg.Button("Inspect object"), sg.Button("Export image"),
         sg.Button("Replace texture"), sg.Button("Edit palette"),
         sg.Button("Use selected asset", visible=choose), sg.Button("Close")],
        [sg.Text("", key="status", size=(120, 2))]]
    window = sg.Window("Asset browser by role", layout, modal=True, finalize=True, resizable=True)
    shown = []
    selected = None
    reader = None
    environment = None
    image = None
    def search(values):
        nonlocal shown, selected, reader, environment, image
        result = catalog.search(values.get("role", "All"), values.get("query", ""), values.get("downloaded", False))
        if allowed_paths is not None:
            result = [r for r in result if r.path in allowed_paths]
        # Limit Tk table population, but never silently hide the truncation.
        shown = result[:2000]
        window["assets"].update(values=[[r.role, r.path, r.bundle] for r in shown], select_rows=[])
        window["count"].update(f"{len(result)} matches; showing {len(shown)}. Narrow the search if needed.")
        window["details"].update("")
        window["preview"].update(data=png_bytes_blank())
        selected = reader = environment = image = None
    search({})
    try:
        while True:
            event, values = window.read()
            if event in (sg.WIN_CLOSED, "Close"):
                return None
            try:
                if event in ("Search", "role", "downloaded"):
                    search(values)
                elif event == "assets" and values["assets"]:
                    selected = shown[values["assets"][0]]
                    reader = environment = image = None
                    consumer_text = "\n".join(
                        f"{c.tree} | node {c.node_id}\n  slot {c.property or '(no shader slot)'} | field {c.field}"
                        for c in selected.consumers)
                    window["details"].update(
                        f"{selected.path}\nRole: {selected.role}\nBundle: {selected.file}\n"
                        f"Downloaded: {selected.available}\n\nALT consumers:\n{consumer_text or 'No direct ALT reference; role inferred from path.'}")
                    window["preview"].update(data=png_bytes_blank())
                elif event in ("Inspect object", "Export image", "Replace texture", "Edit palette", "alpha"):
                    if selected is None:
                        continue
                    if reader is None:
                        original = selected.file.read_bytes()
                        environment, reader = load_object(selected)
                    if reader.type.name in ("Texture2D", "Sprite"):
                        image = object_image(reader)
                        window["preview"].update(data=image_preview(image, alpha=values["alpha"]))
                    if event == "Inspect object":
                        metadata = reader.read_typetree()
                        text = json.dumps(metadata, indent=2, default=str)
                        # Binary texture payload can dominate a type tree: dimensions,
                        # format, mip count, and object identity remain visible.
                        if reader.type.name == "Texture2D":
                            metadata = {k: v for k, v in metadata.items() if k not in ("image data", "image_data")}
                            text = json.dumps(metadata, indent=2, default=lambda _: "<binary>")
                        existing = window["details"].get()
                        window["details"].update(existing + f"\n\nObject: {reader.type.name}, PathID {reader.path_id}\n" + text[:24000])
                    elif event == "Export image":
                        if image is None:
                            raise ValueError("Only Texture2D and Sprite assets can be exported as images.")
                        file = sg.popup_get_file("Export PNG", save_as=True, default_extension=".png", file_types=(("PNG", "*.png"),))
                        if file:
                            image.save(file, format="PNG")
                            window["status"].update("Image exported with alpha preserved.")
                    elif event == "Replace texture":
                        if reader.type.name != "Texture2D":
                            raise ValueError("Select a Texture2D. Atlas sprites require editing their atlas texture separately.")
                        file = sg.popup_get_file("Replacement image", file_types=(("Images", "*.png;*.jpg;*.jpeg;*.tga"),))
                        if file:
                            from PIL import Image
                            from src.theme_bundle import save_edited_bundle
                            texture = reader.read()
                            with Image.open(file) as loaded:
                                texture.set_image(loaded.convert("RGBA"), mipmap_count=max(1, getattr(texture, "m_MipCount", 1) or 1))
                            texture.save()
                            backup = save_edited_bundle(environment, selected.file, original)
                            window["status"].update(f"Saved texture. Backup: {backup.name}. Restart Arena to load the file.")
                            reader = None
                            image = None
                    elif event == "Edit palette":
                        if selected.role != "Color table":
                            raise ValueError("Select a frame or text color table.")
                        create_palette_editor(selected, catalog)
                        reader = None
                        image = None
                elif event == "Use selected asset":
                    if selected is None or not selected.available:
                        raise ValueError("Select a downloaded asset.")
                    return selected
            except Exception as error:
                # Release partially edited in-memory objects after a failed save.
                reader = environment = image = None
                window["status"].update(str(error))
    finally:
        window.close()

def png_bytes_blank():
    from PIL import Image
    return png_bytes(Image.new("RGBA", (1, 1)))

def graph_context(document, binding):
    tree = document[binding.tree]
    nodes = {n["NodeId"]: n for n in tree.get("Nodes", [])}
    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, list):
            for child in value:
                yield from strings(child)
        elif isinstance(value, dict):
            for child in value.values():
                yield from strings(child)
    parents = {}
    for connection in tree.get("Connections", []):
        for child in strings(connection.get("Child")):
            parents.setdefault(child, []).append(connection["Parent"])
    seen = set()
    pending = [binding.node_id]
    result = []
    while pending:
        node_id = pending.pop()
        if node_id in seen:
            continue
        seen.add(node_id)
        node = nodes.get(node_id, {})
        if "Evaluator" in node or "ExtractorType" in node:
            result.append(node)
        pending.extend(parents.get(node_id, []))
    return result

def create_theme_editor(database_file):
    import FreeSimpleGUI as sg
    catalog = catalog_for_database(database_file)
    candidates = [file for file, document in catalog.documents.items() if any(k in document for k in THEME_TREES)]
    if not candidates:
        raise FileNotFoundError("No card frame/theme lookup file found.")
    file = candidates[0]
    theme = ThemeDocument.load(file)
    shown = []
    selected = None
    choices = {}
    layout = [
        [sg.Text("Lookup file"), sg.Combo([str(p) for p in candidates], default_value=str(file),
           readonly=True, key="file", enable_events=True, size=(100, 1))],
        [sg.Text("Section"), sg.Combo(["All"] + list(THEME_TREES), default_value="All",
         readonly=True, key="tree", enable_events=True, size=(38, 1)),
         sg.Input(key="filter", size=(40, 1)), sg.Button("Search")],
        [sg.Table([], headings=["Section", "Node", "Slot", "Asset"], col_widths=[29, 36, 16, 65],
         auto_size_columns=False, num_rows=14, key="bindings", enable_events=True,
         select_mode=sg.TABLE_SELECT_MODE_BROWSE)],
        [sg.Multiline("", size=(120, 9), key="context", disabled=True)],
        [sg.Text("Replacement"), sg.Combo([], key="replacement", size=(105, 1), readonly=True)],
        [sg.Button("Stage binding"), sg.Button("Reset binding"), sg.Button("Edit selected palette"),
         sg.Button("Browse assets"), sg.Button("Export theme"), sg.Button("Import theme")],
        [sg.Multiline("", size=(120, 5), key="staged", disabled=True)],
        [sg.Button("Save theme"), sg.Button("Discard staged"), sg.Button("Close"),
         sg.Text("", size=(75, 2), key="status")],
        [sg.Text("Bindings affect every card matching the displayed rules. Pair base/art/scaffold changes for the same context; shader compatibility is not inferred.")]]
    window = sg.Window("Card frame / theme editor", layout, modal=True, finalize=True, resizable=True)
    def refresh(values=None):
        nonlocal shown, selected
        values = values or {}
        tree = values.get("tree", "All")
        query = values.get("filter", "").casefold().strip()
        shown = [b for b in theme.bindings() if (tree == "All" or b.tree == tree)
                 and query in (theme.reference(b)["RelativePath"] + " " + b.node_id + " " + b.property).casefold()]
        window["bindings"].update(values=[[b.tree, b.node_id, b.property,
            theme.changes.get(b, theme.reference(b))["RelativePath"]] for b in shown], select_rows=[])
        selected = None
        window["replacement"].update(values=[], value="")
        window["context"].update("")
        show_staged()
    def show_staged():
        window["staged"].update("\n".join(
            f"{b.tree} | {b.node_id} | {b.property}: {theme.reference(b)['RelativePath']} -> {ref['RelativePath']}"
            for b, ref in theme.changes.items()) or "No staged binding changes.")
    refresh()
    try:
        while True:
            event, values = window.read()
            if event in (sg.WIN_CLOSED, "Close"):
                if theme.changes and sg.popup_yes_no("Discard staged theme bindings?") != "Yes":
                    continue
                break
            try:
                if event in ("Search", "tree"):
                    refresh(values)
                elif event == "file":
                    if theme.changes and sg.popup_yes_no("Discard staged theme bindings?") != "Yes":
                        window["file"].update(str(theme.file))
                        continue
                    theme = ThemeDocument.load(values["file"])
                    refresh(values)
                elif event == "bindings" and values["bindings"]:
                    selected = shown[values["bindings"][0]]
                    # Replacements come from the same semantic section and shader slot.
                    # Keep the original payload's Keywords, Trigger, Layers, and rules.
                    choices = {}
                    for binding in theme.bindings():
                        if binding.tree == selected.tree and binding.property == selected.property:
                            ref = theme.reference(binding)
                            try:
                                available = catalog.resolve(ref["RelativePath"]).available
                            except ValueError:
                                available = False
                            if available:
                                choices[ref["RelativePath"]] = ref
                    ref = theme.changes.get(selected, theme.reference(selected))
                    window["replacement"].update(values=sorted(choices), value=ref["RelativePath"])
                    window["context"].update(json.dumps({
                        "Selected payload": theme.node(selected),
                        "Ancestor rules (not an evaluated card match)": graph_context(theme.document, selected)
                    }, indent=2))
                elif event == "Stage binding":
                    if selected is None or values["replacement"] not in choices:
                        raise ValueError("Select a binding and a downloaded replacement.")
                    theme.replace(selected, choices[values["replacement"]])
                    show_staged()
                elif event == "Reset binding" and selected:
                    theme.changes.pop(selected, None)
                    window["replacement"].update(theme.reference(selected)["RelativePath"])
                    show_staged()
                elif event == "Discard staged":
                    theme.changes.clear()
                    refresh(values)
                elif event == "Browse assets":
                    create_asset_browser(database_file, catalog)
                elif event == "Edit selected palette":
                    if selected is None:
                        raise ValueError("Select a color-table binding.")
                    record = catalog.resolve(theme.changes.get(selected, theme.reference(selected))["RelativePath"])
                    if record.role != "Color table":
                        raise ValueError("Select a ColorOverride or TextColor binding.")
                    create_palette_editor(record, catalog)
                elif event == "Save theme":
                    if not theme.changes:
                        continue
                    backup = theme.save()
                    window["status"].update(f"Saved; backup: {backup.name}. Restart Arena to load this theme.")
                    catalog = catalog_for_database(database_file)
                    refresh(values)
                elif event == "Export theme":
                    file = sg.popup_get_file("Export staged theme", save_as=True, default_extension=".json", file_types=(("Theme", "*.json"),))
                    if file:
                        data = {"version": 1, "bindings": [
                            {"tree": b.tree, "node_id": b.node_id, "trail": list(b.trail), "property": b.property, "reference": ref}
                            for b, ref in theme.changes.items()]}
                        Path(file).write_text(json.dumps(data, indent=2), encoding="utf-8")
                elif event == "Import theme":
                    file = sg.popup_get_file("Import theme", file_types=(("Theme", "*.json"),))
                    if file:
                        data = json.loads(Path(file).read_text(encoding="utf-8"))
                        if data.get("version") != 1:
                            raise ValueError("Unsupported theme version.")
                        staged = deepcopy(theme.changes)
                        try:
                            for item in data["bindings"]:
                                b = Binding(item["tree"], item["node_id"], tuple(item["trail"]), item.get("property", ""))
                                if b not in theme.bindings():
                                    raise ValueError("Theme node is not available in this client version.")
                                reference = item["reference"]
                                known = [theme.reference(candidate) for candidate in theme.bindings()
                                         if candidate.tree == b.tree and candidate.property == b.property]
                                if reference not in known or not catalog.resolve(reference["RelativePath"]).available:
                                    raise ValueError("Theme replacement is not a downloaded binding for this section.")
                                theme.replace(b, reference)
                        except Exception:
                            theme.changes = staged
                            raise
                        show_staged()
            except Exception as error:
                window["status"].update(str(error))
    finally:
        window.close()

def create_palette_editor(record, catalog):
    import FreeSimpleGUI as sg
    from src.theme_bundle import save_edited_bundle
    original = record.file.read_bytes()
    environment, reader = load_object(record)
    source = reader.read_typetree()
    data = deepcopy(source)
    fields = color_fields(data)
    if not fields:
        raise ValueError("This object has no readable serialized RGBA fields.")
    layout = [
        [sg.Text(record.path, size=(105, 2))],
        [sg.Text(f"Shared palette: {len(record.consumers)} ALT binding(s) reference this asset.")],
        [sg.Listbox([" / ".join(map(str, p)) for p in fields], size=(60, 14), key="fields", enable_events=True),
         sg.Column([[sg.Text("Color #RRGGBB or #RRGGBBAA")], [sg.Input(key="color", size=(20, 1))],
                    [sg.Text("       ", key="swatch", background_color="#333333", size=(15, 3))],
                    [sg.Button("Stage color"), sg.Button("Reset color")]])],
        [sg.Button("Monochrome palette"), sg.Button("Reset palette"), sg.Button("Export palette"),
         sg.Button("Import palette")],
        [sg.Multiline("", key="summary", disabled=True, size=(105, 6))],
        [sg.Button("Save palette"), sg.Button("Close"), sg.Text("", key="status", size=(65, 2))]]
    window = sg.Window("Frame / text palette", layout, modal=True, finalize=True, resizable=True)
    selected = None
    def paint():
        window["summary"].update("\n".join(
            f"{' / '.join(map(str, p))}: {at(data,p)}" for p in fields))
        if selected is not None:
            color = at(data, selected)
            channels = [max(0, min(255, round(color[c] * 255))) for c in ("r", "g", "b", "a")]
            hex_color = "#" + "".join(f"{c:02x}" for c in channels)
            window["color"].update(hex_color)
            window["swatch"].update(background_color=hex_color[:7])
    paint()
    try:
        while True:
            event, values = window.read()
            if event in (sg.WIN_CLOSED, "Close"):
                if data != source and sg.popup_yes_no("Discard unsaved palette changes?") != "Yes":
                    continue
                break
            try:
                if event == "fields" and values["fields"]:
                    selected = fields[[ " / ".join(map(str,p)) for p in fields].index(values["fields"][0])]
                elif event == "Stage color":
                    if selected is None:
                        raise ValueError("Select a color field.")
                    data = recolor(data, selected, values["color"])
                elif event == "Reset color" and selected is not None:
                    parent = at(data, selected[:-1])
                    parent[selected[-1]] = deepcopy(at(source, selected))
                elif event == "Reset palette":
                    data = deepcopy(source)
                elif event == "Monochrome palette":
                    for path in fields:
                        color = at(data, path)
                        luminance = .2126 * color["r"] + .7152 * color["g"] + .0722 * color["b"]
                        color.update(r=luminance, g=luminance, b=luminance)
                elif event == "Export palette":
                    file = sg.popup_get_file("Export palette", save_as=True, default_extension=".json", file_types=(("Palette", "*.json"),))
                    if file:
                        Path(file).write_text(json.dumps({"version":1,"colors":[
                            {"field":list(p),"color":at(data,p)} for p in fields]}, indent=2), encoding="utf-8")
                elif event == "Import palette":
                    file = sg.popup_get_file("Import palette", file_types=(("Palette", "*.json"),))
                    if file:
                        imported = json.loads(Path(file).read_text(encoding="utf-8"))
                        if imported.get("version") != 1:
                            raise ValueError("Unsupported palette version.")
                        candidate = deepcopy(data)
                        for item in imported["colors"]:
                            path = tuple(item["field"])
                            if path not in fields:
                                raise ValueError("Palette field does not exist in this table.")
                            values_rgba = item["color"]
                            import math
                            if not all(isinstance(values_rgba[c], (float,int)) and math.isfinite(values_rgba[c]) for c in ("r","g","b","a")):
                                raise ValueError("Colors must have finite RGBA channels.")
                            at(candidate,path).update({c:values_rgba[c] for c in ("r","g","b","a")})
                        data = candidate
                elif event == "Save palette":
                    if data == source:
                        continue
                    reader.save_typetree(data)
                    backup = save_edited_bundle(environment, record.file, original)
                    original = record.file.read_bytes()
                    source = deepcopy(data)
                    environment, reader = load_object(record)
                    window["status"].update(f"Saved; backup: {backup.name}. Restart Arena to load the palette.")
                refresh_color_schemes(data, source)
                paint()
            except Exception as error:
                window["status"].update(str(error))
    finally:
        window.close()
