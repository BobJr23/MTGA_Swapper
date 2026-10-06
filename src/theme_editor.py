"""Stage frame/theme bindings without changing ALT graph conditions."""
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import os
import tempfile
from src.asset_catalog import references

THEME_TREES = ("ALT_Card.MaterialOverride", "ALT_Card.TextureOverride",
               "ALT_Card.ColorOverride", "ALT_Card.TextColor", "ALT_Card.Scaffold",
               "ALT_Card.Parts.CardBasePart", "ALT_Card.Parts.ArtInFramePart",
               "ALT_Card.Parts.TextBoxPart")

def at(value, trail):
    for key in trail:
        value = value[key]
    return value

@dataclass(frozen=True)
class Binding:
    tree: str
    node_id: str
    trail: tuple
    property: str

class ThemeDocument:
    def __init__(self, document, file=None, original=None):
        self.document = deepcopy(document)
        self.file = Path(file) if file else None
        self.original = original
        self.changes = {}

    @classmethod
    def load(cls, file):
        file = Path(file)
        original = file.read_bytes()
        return cls(json.loads(original.decode("utf-8-sig")), file, original)

    def bindings(self):
        result = []
        for tree in THEME_TREES:
            for node in self.document.get(tree, {}).get("Nodes", []):
                for trail, ref, prop in references(node.get("Payload", {})):
                    result.append(Binding(tree, node["NodeId"], trail, prop))
        return result

    def node(self, binding):
        matches = [n for n in self.document[binding.tree]["Nodes"] if n.get("NodeId") == binding.node_id]
        if len(matches) != 1:
            raise ValueError("Ambiguous or missing theme node.")
        return matches[0]

    def reference(self, binding):
        return at(self.node(binding)["Payload"], binding.trail)

    def replace(self, binding, reference):
        old = self.reference(binding)
        if not reference.get("RelativePath") or not reference.get("Guid"):
            raise ValueError("A replacement requires both its indexed path and GUID.")
        if Path(reference["RelativePath"]).suffix.lower() != Path(old["RelativePath"]).suffix.lower():
            raise ValueError("Replacement asset type must match the original.")
        self.changes[binding] = deepcopy(reference)

    def result(self):
        result = deepcopy(self.document)
        for binding, reference in self.changes.items():
            node = next(n for n in result[binding.tree]["Nodes"] if n.get("NodeId") == binding.node_id)
            target = at(node["Payload"], binding.trail)
            target["Guid"] = reference["Guid"]
            target["RelativePath"] = reference["RelativePath"]
        return result

    def save(self):
        if not self.file:
            raise ValueError("No ALT file selected.")
        if self.file.read_bytes() != self.original:
            raise RuntimeError("The ALT file changed outside this editor. Reload before saving.")
        encoded = json.dumps(self.result(), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        digest = hashlib.sha256(self.original).hexdigest()[:16]
        backup = self.file.with_name(self.file.name + "." + digest + ".theme-backup")
        if not backup.exists():
            backup.write_bytes(self.original)
        descriptor, name = tempfile.mkstemp(dir=self.file.parent, prefix=".theme-", suffix=".tmp")
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            if self.file.read_bytes() != self.original:
                raise RuntimeError("The ALT file changed during save.")
            os.replace(name, self.file)
        finally:
            if os.path.exists(name):
                os.unlink(name)
        self.document = self.result()
        self.original = encoded
        self.changes.clear()
        return backup

def color_fields(value, trail=()):
    result = []
    if isinstance(value, dict):
        if all(k in value and isinstance(value[k], (int, float)) for k in ("r", "g", "b", "a")):
            result.append(trail)
        else:
            for key, child in value.items():
                result.extend(color_fields(child, trail + (key,)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            result.extend(color_fields(child, trail + (index,)))
    return result

def recolor(document, trail, hex_color):
    color = hex_color.strip().lstrip("#")
    if len(color) not in (6, 8):
        raise ValueError("Use #RRGGBB or #RRGGBBAA.")
    try:
        channels = [int(color[i:i + 2], 16) / 255 for i in range(0, len(color), 2)]
    except ValueError:
        raise ValueError("Invalid hexadecimal color.") from None
    result = deepcopy(document)
    target = at(result, trail)
    if trail not in color_fields(document):
        raise ValueError("Selected field is not a serialized Unity color.")
    for key, channel in zip(("r", "g", "b", "a"), channels):
        target[key] = channel
    return result

def refresh_color_schemes(data, source):
    """Activate custom settings only for changed groups; reset their saved preset."""
    if "ColorScheme" in source and "DefaultSettings" in source:
        data["ColorScheme"] = (999 if data["DefaultSettings"] != source["DefaultSettings"]
                               else source["ColorScheme"])
    for index, saved in enumerate(source.get("FieldTypeOverrides", [])):
        if "ColorScheme" not in saved or "Settings" not in saved:
            continue
        current = data["FieldTypeOverrides"][index]
        current["ColorScheme"] = (999 if current["Settings"] != saved["Settings"]
                                  else saved["ColorScheme"])
