"""Manifest assets, rendering roles, and exact ALT consumers."""
from dataclasses import dataclass, field
from pathlib import Path
import json

def references(value, trail=(), shader_property=""):
    if isinstance(value, dict):
        shader_property = value.get("Property", shader_property)
        if isinstance(value.get("RelativePath"), str):
            yield trail, value, shader_property
        for key, child in value.items():
            yield from references(child, trail + (key,), shader_property)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from references(child, trail + (index,), shader_property)

@dataclass(frozen=True)
class Consumer:
    tree: str
    node_id: str
    property: str = ""
    field: tuple = ()
    guid: str = ""

@dataclass
class AssetRecord:
    path: str
    bundle: str
    file: Path
    role: str
    consumers: list = field(default_factory=list)

    @property
    def available(self):
        return self.file.is_file()

def role_for(path, consumers=()):
    lower = path.lower()
    suffix = Path(lower).suffix
    trees = " ".join(c.tree for c in consumers).lower()
    if "/cardart/" in lower:
        return "Auxiliary map" if any(s in Path(lower).stem for s in ("_util", "_depth", "_dist", "_foil")) else "Card art"
    if suffix == ".mat":
        return "Material"
    if "colortable" in lower or "colorsettings" in lower:
        return "Color table"
    if suffix == ".unity":
        return "Battlefield" if "battlefield" in lower else "Scene"
    if "scaffold" in trees or "scaffold" in lower:
        return "Scaffold"
    if "parts." in trees or "/cdc/parts/" in lower:
        return "Card part"
    if "sleeve" in lower or "sleeve" in trees:
        return "Sleeve"
    if "avatar" in lower or "avatar" in trees:
        return "Avatar"
    if "textureoverride" in trees or "/cdc/images/" in lower:
        return "Frame texture"
    if "vfx" in lower or "deathpayload" in trees:
        return "VFX"
    if "font" in lower:
        return "Font"
    if suffix in (".png", ".tga", ".jpg", ".spriteatlas"):
        return "UI sprite"
    if suffix == ".prefab":
        return "Prefab"
    return "Other"

class AssetCatalog:
    def __init__(self, downloads, records, documents=None):
        self.downloads = Path(downloads)
        self.records = records
        self.documents = documents or {}
        self.by_path = {}
        for record in records:
            self.by_path.setdefault(record.path.casefold(), []).append(record)

    @classmethod
    def load(cls, downloads):
        downloads = Path(downloads)
        manifests = sorted(downloads.glob("Manifest_*.mtga"), key=lambda p: p.stat().st_mtime_ns)
        if not manifests:
            raise FileNotFoundError("No download manifest found in " + str(downloads))
        manifest = None
        for file in reversed(manifests):
            with file.open(encoding="utf-8-sig") as stream:
                candidate = json.load(stream)
            if any(a.get("IndexedAssets") for a in candidate.get("Assets", [])):
                manifest = candidate
                break
        if manifest is None:
            raise ValueError("No manifest with indexed visual assets found.")
        consumers = {}
        documents = {}
        for file in sorted((downloads / "ALT").glob("ALT_*.mtga")):
            with file.open(encoding="utf-8-sig") as stream:
                document = json.load(stream)
            documents[file] = document
            for tree, data in document.items():
                if not isinstance(data, dict):
                    continue
                for node in data.get("Nodes", []):
                    for trail, ref, prop in references(node.get("Payload", {})):
                        consumers.setdefault(ref["RelativePath"].casefold(), []).append(
                            Consumer(tree, node.get("NodeId", ""), prop, trail, ref.get("Guid", "")))
        records = []
        for asset in manifest.get("Assets", []):
            name = asset.get("Name", "")
            if not name or Path(name).name != name or "/" in name or "\\" in name:
                raise ValueError("Invalid bundle filename: " + name)
            folder = "Raw" if name.startswith("Raw_") else "ALT" if name.startswith("ALT_") else "AssetBundle"
            for path in asset.get("IndexedAssets", []):
                if not isinstance(path, str):
                    continue
                refs = consumers.get(path.casefold(), [])
                records.append(AssetRecord(path, name, downloads / folder / name, role_for(path, refs), refs))
        return cls(downloads, records, documents)

    def search(self, role="All", query="", available_only=False):
        query = query.casefold().strip()
        return [r for r in self.records if (role == "All" or r.role == role)
                and (not available_only or r.available)
                and (not query or query in (r.path + " " + r.bundle + " " +
                     " ".join(c.tree + " " + c.property + " " + c.node_id for c in r.consumers)).casefold())]

    def resolve(self, path):
        matches = self.by_path.get(path.casefold(), [])
        if len(matches) != 1:
            raise ValueError(f"Expected one manifest match for {path}; found {len(matches)}")
        return matches[0]

    def art_for_crop(self, path):
        for extension in (".tga", ".jpg", ".png"):
            matches = self.by_path.get((path + extension).casefold(), [])
            if matches:
                if len(matches) != 1:
                    raise ValueError("Ambiguous card art: " + path)
                return matches[0]
        raise FileNotFoundError("No indexed art texture for " + path)

def load_object(record):
    """Resolve the exact container entry; never infer identity from texture order."""
    from src.unity_bundle import load_unity_bundle
    if not record.available:
        raise FileNotFoundError("Bundle is not downloaded: " + str(record.file))
    environment = load_unity_bundle(record.file.read_bytes())
    return environment, resolve_object(environment, record)

def resolve_object(environment, record):
    matches = [reader for key, reader in environment.container.items()
               if key.replace("\\", "/").casefold() == record.path.casefold()]
    if len(matches) == 1:
        pointer = matches[0]
        return pointer.deref() if hasattr(pointer, "deref") else pointer
    if not matches and record.bundle.startswith("Atlas_"):
        # Arena resolves indexed atlas paths through the filename stem,
        # not through the bundle's (atlas-only) container dictionary.
        name = Path(record.path).stem
        for obj in environment.objects:
            if obj.type.name != "SpriteAtlas":
                continue
            atlas = obj.read()
            for sprite_name, pointer in zip(atlas.m_PackedSpriteNamesToIndex, atlas.m_PackedSprites):
                if sprite_name == name:
                    matches.append(pointer.deref())
        if len(matches) == 1:
            return matches[0]
    raise ValueError(f"Expected one object for {record.path}; found {len(matches)}")


def object_image(reader):
    if reader.type.name not in ("Texture2D", "Sprite"):
        raise ValueError("This asset is not an image: " + reader.type.name)
    return reader.read().image.copy()
