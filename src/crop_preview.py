"""UV previews for the crop editor; image dependencies are loaded on demand."""
import math

def pixel_box(size, crop):
    width, height = size
    x, y, z, w = map(float, crop)
    if not all(math.isfinite(v) for v in (x, y, z, w)) or x <= 0 or y <= 0:
        raise ValueError("Crop scales must be positive and all values finite.")
    return (z * width, (1 - w - y) * height, (z + x) * width, (1 - w) * height)

def resolve_crop(rows, path, context):
    table = {(r[0], r[1]): tuple(r[2:6]) for r in rows}
    if (path, context) in table:
        return table[path, context]
    position = path.casefold().find("_aif")
    if position >= 0 and position + 4 < len(path):
        return table.get((path[:position + 4], context), (1, 1, 0, 0))
    return (1, 1, 0, 0)

def render_crop(image, crop, dimensions, max_size=(210, 180)):
    from PIL import Image
    box = pixel_box(image.size, crop)
    width, height = map(int, dimensions)
    if width <= 0 or height <= 0:
        raise ValueError("Format dimensions must be positive.")
    factor = min(max_size[0] / width, max_size[1] / height)
    size = (max(1, round(width * factor)), max(1, round(height * factor)))
    return image.convert("RGBA").transform(size, Image.Transform.EXTENT, box,
                                          resample=Image.Resampling.BICUBIC)

def png_bytes(image):
    import io
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()

def load_formats(connection):
    return {name: (width, height) for name, width, height in
            connection.execute("SELECT Name, Width, Height FROM Formats")}

def stage_crops(connection, path, pending):
    """Write into the parent's transaction without implicitly committing it."""
    for crop in pending.values():
        pixel_box((1, 1), crop)
    if not connection.in_transaction:
        connection.execute("BEGIN")
    connection.execute("SAVEPOINT crop_preview")
    try:
        for context, crop in pending.items():
            connection.execute(
                "INSERT INTO Crops (Path,Format,X,Y,Z,W,Generated) VALUES (?,?,?,?,?,?,0) "
                "ON CONFLICT(Path,Format) DO UPDATE SET X=excluded.X,Y=excluded.Y,Z=excluded.Z,W=excluded.W,Generated=0",
                (path, context, *crop))
        connection.execute("RELEASE crop_preview")
    except Exception:
        connection.execute("ROLLBACK TO crop_preview")
        connection.execute("RELEASE crop_preview")
        raise

def create_preview_window(crop_connection, path, catalog):
    import FreeSimpleGUI as sg
    from src.asset_catalog import load_object, object_image
    from PIL import Image
    formats = load_formats(crop_connection)
    contexts = [n for n in ("Normal", "Borderless", "Borderless Battlefield",
                "Frameless Battlefield", "Split (Hand)", "RoomLeft", "RoomRight") if n in formats]
    if not contexts:
        raise ValueError("No preview formats available.")
    rows = list(crop_connection.execute("SELECT Path, Format, X, Y, Z, W, Generated FROM Crops"))
    _, reader = load_object(catalog.art_for_crop(path))
    image = object_image(reader)
    entries = [r for r in rows if r[0] == path]
    choices = sorted(formats)
    active = entries[0][1] if entries and entries[0][1] in formats else contexts[0]
    staged = {r[1]: tuple(r[2:6]) for r in entries}
    layout = [
        [sg.Text(path, size=(105, 2))],
        [sg.Text("UV previews at format aspect ratios; no 3D frames or shader effects. Out-of-image UVs appear transparent.")],
        [sg.Column([[sg.Text(name)], [sg.Image(key=("preview", name))],
                    [sg.Text("", key=("values", name), size=(28, 2))]]) for name in contexts[:4]],
        [sg.Column([[sg.Text(name)], [sg.Image(key=("preview", name))],
                    [sg.Text("", key=("values", name), size=(28, 2))]]) for name in contexts[4:]],
        [sg.Text("Edit context"), sg.Combo(choices, default_value=active, readonly=True, key="context", enable_events=True),
         sg.Text("X scale"), sg.Input(key="x", size=(8, 1), enable_events=True),
         sg.Text("Y scale"), sg.Input(key="y", size=(8, 1), enable_events=True),
         sg.Text("Z offset"), sg.Input(key="z", size=(8, 1), enable_events=True),
         sg.Text("W offset"), sg.Input(key="w", size=(8, 1), enable_events=True)],
        [sg.Image(key="active-preview"), sg.Text("", key="active-caption", size=(55, 2))],
        [sg.Button("Use local image", key="image"), sg.Button("Reset context", key="reset"),
         sg.Button("Stage context", key="stage"), sg.Button("Save staged crops", key="save"),
         sg.Button("Close"), sg.Text("", key="status", size=(55, 2))]]
    window = sg.Window("Multi-context crop preview", layout, modal=True, finalize=True, resizable=True)
    pending = {}
    changed = set()
    def populate():
        crop = staged.get(active, resolve_crop(rows, path, active))
        for key, value in zip(("x", "y", "z", "w"), crop):
            window[key].update(str(value))
    def paint(candidate=None):
        for name in contexts:
            crop = candidate if name == active and candidate is not None else staged.get(name, resolve_crop(rows, path, name))
            window[("preview", name)].update(data=png_bytes(render_crop(image, crop, formats[name])))
            window[("values", name)].update(f"{crop}\n" + ("Fallback crop" if name not in staged else "Saved/staged crop"))
        crop = candidate if candidate is not None else staged.get(active, resolve_crop(rows, path, active))
        window["active-preview"].update(data=png_bytes(render_crop(image, crop, formats[active])))
        window["active-caption"].update(f"Editing {active}: {crop}")
    populate()
    paint()
    try:
        while True:
            event, values = window.read()
            if event in (sg.WIN_CLOSED, "Close"):
                if pending and sg.popup_yes_no("Discard unstored preview changes?", title="Unsaved crops") != "Yes":
                    continue
                break
            try:
                if event == "context":
                    active = values["context"]
                    populate()
                    paint()
                elif event in ("x", "y", "z", "w", "stage"):
                    candidate = tuple(float(values[k]) for k in ("x", "y", "z", "w"))
                    pixel_box(image.size, candidate)
                    paint(candidate)
                    window["status"].update("Unsaved preview")
                    if event == "stage":
                        staged[active] = candidate
                        pending[active] = candidate
                        window["status"].update(f"{len(pending)} context(s) staged")
                elif event == "reset":
                    staged[active] = resolve_crop(rows, path, active)
                    pending.pop(active, None)
                    populate()
                    paint()
                elif event == "image":
                    file = sg.popup_get_file("Choose replacement art", file_types=(("Images", "*.png;*.jpg;*.jpeg;*.tga"),))
                    if file:
                        with Image.open(file) as loaded:
                            image = loaded.convert("RGBA")
                        paint()
                elif event == "save":
                    if not pending:
                        window["status"].update("Stage a context before saving.")
                        continue
                    stage_crops(crop_connection, path, pending)
                    changed.update(pending)
                    pending.clear()
                    rows = list(crop_connection.execute("SELECT Path, Format, X, Y, Z, W, Generated FROM Crops"))
                    window["status"].update("Stored in editor transaction. Apply Changes to Database in the parent editor.")
                window.refresh()
            except (ValueError, OSError) as error:
                window["status"].update(str(error))
    finally:
        window.close()
    return changed

def write_crop_changes(rows, file):
    """Atomically export committed preview crops without dropping existing presets."""
    from pathlib import Path
    import json
    import os
    import re
    import tempfile
    file = Path(file)
    original = file.read_bytes() if file.exists() else None
    data = json.loads(original.decode("utf-8-sig")) if original is not None else {}
    if not isinstance(data, dict):
        raise ValueError("Changes preset must be an object.")
    crops = data.setdefault("crops", {})
    if not isinstance(crops, dict):
        raise ValueError("Preset crops must be an object.")
    for path, context, x, y, z, w, generated in rows:
        art_id = Path(path).name.split("_", 1)[0]
        if not re.fullmatch(r"[0-9]+", art_id):
            raise ValueError("Cannot identify crop ArtId: " + path)
        pixel_box((1, 1), (x, y, z, w))
        art_id = str(int(art_id))
        aliases = [key for key in crops if re.fullmatch(r"[0-9]+", key)
                   and str(int(key)) == art_id]
        # Older previews used padded keys. Canonical manual edits take precedence.
        aliases.sort(key=lambda key: key == art_id)
        merged = {}
        for key in aliases:
            entries = crops[key]
            if not isinstance(entries, list) or not all(isinstance(c, dict) for c in entries):
                raise ValueError("Invalid crop entries in preset: " + key)
            for item in entries:
                merged[(item.get("path"), item.get("format"))] = item
        for key in aliases:
            del crops[key]
        changes = list(merged.values())
        crops[art_id] = changes
        entry = dict(path=path, format=context, x=x, y=y, z=z, w=w, generated=generated)
        existing = next((i for i, c in enumerate(changes)
                         if c.get("path") == path and c.get("format") == context), None)
        if existing is None:
            changes.append(entry)
        else:
            changes[existing] = entry
    encoded = json.dumps(data, ensure_ascii=False, indent=4).encode("utf-8")
    file.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=file.parent, prefix=".crops-", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        current = file.read_bytes() if file.exists() else None
        if current != original:
            raise RuntimeError("Changes preset was modified during export. Retry saving.")
        os.replace(temporary, file)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
