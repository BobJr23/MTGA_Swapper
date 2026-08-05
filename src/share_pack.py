# Share pack creation and loading for MTGA Swapper.
# A share pack is a .zip holding a user's swapped card art (one PNG per ArtId)
# alongside exported_changes.json, so a whole setup can be handed to someone else.
# Deliberately manifest-free: the zip is simple enough to assemble by hand.

import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import List, Optional, Tuple

from PIL import Image

SWAPPED_IMAGES_DIRECTORY_NAME = "swapped_images"
CHANGES_MEMBER_NAME = "exported_changes.json"
IMAGES_MEMBER_PREFIX = "images/"
CROPS_KEY = "crops"


def normalize_art_id(art_id) -> str:
    """
    Pad an ArtId to the 6-digit form used by AssetBundle filenames.

    Bundle lookup throughout this codebase is filename.startswith(art_id), so an
    unpadded "1234" would match 123456_CardArt_*.mtga. Everything that touches an
    ArtId from disk normalizes it here first.
    """
    return str(art_id).zfill(6)


def image_filename_for(art_id, texture_index: int) -> str:
    """
    Build the pack filename for a swapped texture.

    Texture 0 (the usual case) is named after the ArtId alone; anything else
    carries the index, because a card's bundle often holds several textures and
    the editor's "Next in bundle" button can land on any of them.
    """
    normalized_art_id = normalize_art_id(art_id)
    if texture_index == 0:
        return f"{normalized_art_id}.png"
    return f"{normalized_art_id}_{texture_index}.png"


def parse_image_filename(filename: str) -> Optional[Tuple[str, int]]:
    """
    Read an ArtId and texture index back out of a pack filename.

    Returns None for anything that is not a pack image, so stray files dropped
    into the folder are ignored rather than breaking an export.
    """
    stem, extension = os.path.splitext(os.path.basename(filename))
    if extension.lower() != ".png":
        return None

    art_id_part, separator, index_part = stem.partition("_")
    # isascii() matters: "²".isdigit() is True but int("²") raises, and a stray
    # file must be skipped rather than crash an export mid-way.
    if not (art_id_part.isascii() and art_id_part.isdigit()):
        return None
    if not separator:
        return normalize_art_id(art_id_part), 0
    if not (index_part.isascii() and index_part.isdigit()):
        return None
    return normalize_art_id(art_id_part), int(index_part)


def filter_changes_for_art_ids(changes_data: dict, art_ids: set) -> dict:
    """
    Keep only the changes.json entries belonging to the given ArtIds.

    Every write path into changes.json goes through save_grp_id_info, which
    stores the complete Cards row, so ArtId is present on every GrpId entry.
    The top-level "crops" key is not a GrpId entry -- it is itself keyed by
    ArtId -- so it is filtered separately and re-attached.

    art_ids is normalized here rather than trusted: an unpadded or int member
    would silently drop matching cards from the pack instead of failing loudly.
    The returned dict shares its nested values with changes_data -- callers
    serialize it, they do not mutate it.
    """
    art_ids = {normalize_art_id(art_id) for art_id in art_ids}
    filtered_changes = {}
    for grp_id, card_values in changes_data.items():
        if grp_id == CROPS_KEY:
            continue
        if not isinstance(card_values, dict):
            continue
        if normalize_art_id(card_values.get("ArtId", "")) in art_ids:
            filtered_changes[grp_id] = card_values

    crop_changes = changes_data.get(CROPS_KEY)
    if isinstance(crop_changes, dict):
        filtered_crops = {
            art_id: crop_entries
            for art_id, crop_entries in crop_changes.items()
            if normalize_art_id(art_id) in art_ids
        }
        if filtered_crops:
            filtered_changes[CROPS_KEY] = filtered_crops

    return filtered_changes


def get_swapped_images_directory(user_config_directory) -> Path:
    """Resolve (and create) the folder holding every card art the user has swapped in."""
    images_directory = Path(user_config_directory) / SWAPPED_IMAGES_DIRECTORY_NAME
    images_directory.mkdir(parents=True, exist_ok=True)
    return images_directory


def record_swapped_image(
    source_image_path, art_id, texture_index: int, images_directory
) -> Path:
    """
    Store the image a user just applied to a card, so it can be shared later.

    The source file is stored rather than the resulting texture: replace_texture_in_bundle
    does Image.open on this exact file, so keeping it reproduces the swap byte for byte.
    Re-swapping the same texture overwrites the previous entry.
    """
    destination_path = Path(images_directory) / image_filename_for(art_id, texture_index)
    if Path(source_image_path).suffix.lower() == ".png":
        shutil.copyfile(source_image_path, destination_path)
    else:
        with Image.open(source_image_path) as source_image:
            source_image.save(destination_path, format="PNG")
    return destination_path


def collect_pack_art_ids(images_directory) -> set:
    """List the ArtIds that have a stored image, ignoring any stray files."""
    images_directory = Path(images_directory)
    if not images_directory.is_dir():
        return set()

    art_ids = set()
    for entry in images_directory.iterdir():
        if not entry.is_file():
            continue
        parsed_name = parse_image_filename(entry.name)
        if parsed_name:
            art_ids.add(parsed_name[0])
    return art_ids


def find_colliding_image_names(image_paths, images_directory) -> List[str]:
    """Names in a pack that would overwrite art the user already swapped in themselves."""
    images_directory = Path(images_directory)
    return [
        image_path.name
        for image_path in image_paths
        if (images_directory / image_path.name).exists()
    ]


def export_pack(zip_path, changes_data: dict, images_directory) -> Tuple[int, int]:
    """
    Write a share pack.

    exported_changes.json is always written, even when empty, so a pack is always
    structurally complete. Returns (image_count, card_entry_count) for the summary popup.
    """
    images_directory = Path(images_directory)
    image_files = []
    if images_directory.is_dir():
        image_files = sorted(
            entry
            for entry in images_directory.iterdir()
            if entry.is_file() and parse_image_filename(entry.name)
        )

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as pack_file:
        pack_file.writestr(CHANGES_MEMBER_NAME, json.dumps(changes_data, indent=4))
        for image_file in image_files:
            pack_file.write(image_file, IMAGES_MEMBER_PREFIX + image_file.name)

    card_entry_count = len([key for key in changes_data if key != CROPS_KEY])
    return len(image_files), card_entry_count


class SharePack:
    """
    An extracted share pack.

    Call cleanup() when finished -- the contents live in a temp directory.
    """

    def __init__(
        self,
        extraction_directory: Path,
        changes_path: Optional[Path],
        image_paths: List[Path],
    ):
        self.extraction_directory = extraction_directory
        self.changes_path = changes_path
        self.image_paths = image_paths

    def cleanup(self) -> None:
        shutil.rmtree(self.extraction_directory, ignore_errors=True)


def _is_expected_member(member_name: str) -> bool:
    """
    Allowlist the two things a pack may contain.

    Packs come from strangers, so anything else -- traversal, absolute paths,
    nested folders, unexpected file types -- is simply not extracted.

    Any colon is rejected outright. On Windows a drive-relative member like
    "images/D:123456.png" would otherwise slip through: os.path.basename strips
    the "D:" so the name validates as an ArtId, and joining it re-anchors the
    write to D:\\123456.png -- outside the extraction directory entirely.
    """
    normalized_name = member_name.replace("\\", "/")
    if normalized_name.endswith("/"):
        return False
    if normalized_name.startswith("/") or ".." in normalized_name.split("/"):
        return False
    if ":" in normalized_name:
        return False

    if normalized_name == CHANGES_MEMBER_NAME:
        return True
    if not normalized_name.startswith(IMAGES_MEMBER_PREFIX):
        return False

    image_name = normalized_name[len(IMAGES_MEMBER_PREFIX) :]
    return "/" not in image_name and parse_image_filename(image_name) is not None


def read_pack(zip_path) -> SharePack:
    """
    Validate a share pack and extract its known members to a temp directory.

    Raises ValueError if the zip is not a share pack at all.
    """
    extraction_directory = Path(tempfile.mkdtemp(prefix="mtga_share_pack_"))
    changes_path = None
    image_paths = []

    try:
        extracted_images_directory = extraction_directory / "images"
        extracted_images_directory.mkdir()

        with zipfile.ZipFile(zip_path) as pack_file:
            for member_name in pack_file.namelist():
                if not _is_expected_member(member_name):
                    print(f"Share pack: ignoring unexpected member {member_name!r}")
                    continue

                normalized_name = member_name.replace("\\", "/")
                if normalized_name == CHANGES_MEMBER_NAME:
                    destination_path = extraction_directory / CHANGES_MEMBER_NAME
                    changes_path = destination_path
                else:
                    destination_path = (
                        extracted_images_directory
                        / PurePosixPath(normalized_name).name
                    )
                    if destination_path in image_paths:
                        # A zip may legally carry the same name twice.
                        print(f"Share pack: ignoring duplicate member {member_name!r}")
                        continue
                    image_paths.append(destination_path)

                with pack_file.open(member_name) as source_file, open(
                    destination_path, "wb"
                ) as target_file:
                    shutil.copyfileobj(source_file, target_file)

        if changes_path is None and not image_paths:
            raise ValueError(
                "This zip is not a share pack: it has no exported_changes.json and no images."
            )
    except Exception:
        shutil.rmtree(extraction_directory, ignore_errors=True)
        raise

    return SharePack(extraction_directory, changes_path, sorted(image_paths))
