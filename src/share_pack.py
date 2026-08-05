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

from .unity_bundle import (
    extract_textures_from_bundle,
    load_unity_bundle,
    replace_texture_in_bundle,
)

SWAPPED_IMAGES_DIRECTORY_NAME = "swapped_images"
CHANGES_MEMBER_NAME = "exported_changes.json"
IMAGES_MEMBER_PREFIX = "images/"
CROPS_KEY = "crops"
LOCALIZATIONS_KEY = "Localizations_enUS"
MAX_MEMBER_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_IMAGE_PIXELS = 64 * 1024 * 1024
BACKUP_PREFIX = "MOD_"


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


def validate_changes_data(changes_data: dict, allowed_columns) -> None:
    """
    Reject a changes payload whose keys would be interpolated into SQL.

    change_grp_id builds "UPDATE Cards SET {columns}" by f-stringing the keys of each
    entry, so a key like "ArtId = ?, Order_Title = ? WHERE 1=1 --" rewrites every row
    in the table. Packs arrive from strangers, so every key is checked against the real
    Cards columns before any of it reaches the database.

    The GrpId keys themselves are safe -- change_grp_id passes them as bound parameters.
    Raises ValueError naming the offending key.
    """
    permitted_keys = set(allowed_columns) | {LOCALIZATIONS_KEY}
    for entry_key, entry_value in changes_data.items():
        if entry_key == CROPS_KEY:
            continue
        if not isinstance(entry_value, dict):
            raise ValueError(f"Entry {entry_key!r} is not an object.")
        for column_name in entry_value:
            if column_name not in permitted_keys:
                raise ValueError(
                    f"Entry {entry_key!r} sets unknown column {column_name!r}. "
                    "Refusing to apply this file."
                )


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
    extracted_bytes = 0

    try:
        extracted_images_directory = extraction_directory / "images"
        extracted_images_directory.mkdir()

        with zipfile.ZipFile(zip_path) as pack_file:
            for member in pack_file.infolist():
                member_name = member.filename
                if not _is_expected_member(member_name):
                    print(f"Share pack: ignoring unexpected member {member_name!r}")
                    continue
                if member.file_size > MAX_MEMBER_BYTES:
                    # Card art is a few MB at most. Without this, one crafted
                    # member streams unbounded and fills the recipient's disk.
                    print(
                        f"Share pack: ignoring oversized member {member_name!r} "
                        f"({member.file_size} bytes)"
                    )
                    continue
                if extracted_bytes + member.file_size > MAX_TOTAL_BYTES:
                    raise ValueError(
                        "This pack expands to more than "
                        f"{MAX_TOTAL_BYTES // (1024 * 1024)} MB; refusing to extract it."
                    )
                extracted_bytes += member.file_size

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

                # Open by ZipInfo, not name: with duplicate names, name lookup
                # always resolves to the last entry.
                with pack_file.open(member) as source_file, open(
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


def find_bundle_for_art_id(
    asset_bundle_directory, art_id, bundle_filenames=None
) -> Optional[str]:
    """
    Locate the AssetBundle file holding a card's art, or None if it is not present.

    The ArtId must end at a boundary: a bare prefix test matches 1234567_CardArt_*.mtga
    when looking up 123456, and because '7' sorts before '_' it wins every time -- which
    would write one card's art into another card's bundle.
    """
    normalized_art_id = normalize_art_id(art_id)
    if bundle_filenames is None:
        bundle_filenames = sorted(os.listdir(asset_bundle_directory))

    for filename in bundle_filenames:
        if not filename.endswith(".mtga") or not filename.startswith(normalized_art_id):
            continue
        if filename[len(normalized_art_id):][:1].isdigit():
            continue
        return filename
    return None


def apply_pack_images(
    image_paths, asset_bundle_directory, backup_directory, images_directory
) -> Tuple[int, List[str]]:
    """
    Write each pack image into the matching AssetBundle file.

    Alongside the bundle write, each applied image gets a MOD_ bundle backup (so the
    recipient's own "Load Changes Preset" restores it after a game update) and a copy in
    the local swapped images folder (so they can pass the pack on).

    No single failure aborts the batch: a missing bundle is expected, since MTGA downloads
    card art on demand. Returns (applied_count, problem_messages) -- a problem message is
    not always a skip, since a backup can fail after the art is already in the game.
    """
    applied_count = 0
    problem_messages = []
    backup_directory = Path(backup_directory)
    backup_directory.mkdir(parents=True, exist_ok=True)
    images_directory = Path(images_directory)
    images_directory.mkdir(parents=True, exist_ok=True)

    try:
        bundle_filenames = sorted(os.listdir(asset_bundle_directory))
    except OSError as error:
        return 0, [f"AssetBundle directory unavailable: {error}"]

    for image_path in image_paths:
        parsed_name = parse_image_filename(image_path.name)
        if not parsed_name:
            problem_messages.append(f"{image_path.name}: unrecognized filename")
            continue
        art_id, texture_index = parsed_name

        try:
            with Image.open(image_path) as probe_image:
                image_width, image_height = probe_image.size
            if image_width * image_height > MAX_IMAGE_PIXELS:
                problem_messages.append(
                    f"ArtId {art_id}: image is {image_width}x{image_height}, "
                    "too large to apply"
                )
                continue

            bundle_name = find_bundle_for_art_id(
                asset_bundle_directory, art_id, bundle_filenames
            )
            if not bundle_name:
                problem_messages.append(
                    f"ArtId {art_id}: no bundle found "
                    "(this card's art may not be downloaded yet)"
                )
                continue

            bundle_path = os.path.join(asset_bundle_directory, bundle_name)
            unity_environment = load_unity_bundle(bundle_path)
            textures = extract_textures_from_bundle(unity_environment)
            if texture_index >= len(textures):
                problem_messages.append(
                    f"ArtId {art_id}: texture {texture_index} missing "
                    f"(this bundle has {len(textures)})"
                )
                continue

            replace_texture_in_bundle(
                textures[texture_index], str(image_path), bundle_path, unity_environment
            )
            applied_count += 1

            # replace_texture_in_bundle has already committed its write, so the art
            # IS in the game from here on. A backup failure must not be reported as
            # a skip -- it is a card that works now and silently reverts later.
            try:
                backup_path = backup_directory / f"MOD_{bundle_name}"
                if backup_path.exists():
                    # Art made before share packs existed has no PNG on record, so this
                    # backup is its only copy. Preserve it once, on the first overwrite.
                    preserved_path = backup_path.with_suffix(".prepack.bak")
                    if not preserved_path.exists():
                        shutil.copyfile(backup_path, preserved_path)
                shutil.copyfile(bundle_path, backup_path)
                shutil.copyfile(image_path, images_directory / image_path.name)
            except Exception as error:
                problem_messages.append(
                    f"ArtId {art_id}: art applied but backup failed ({error}) "
                    "-- a game update will revert this card"
                )

        except Exception as error:
            problem_messages.append(f"ArtId {art_id}: {error}")

    return applied_count, problem_messages


def _index_backup_bundles(backup_directory) -> dict:
    """
    Map ArtId -> MOD_ backup filename.

    Anchored on the first underscore-separated field so 123456 never resolves to
    1234567_CardArt_*.mtga -- the same hazard find_bundle_for_art_id guards against.
    """
    backup_index = {}
    for filename in sorted(os.listdir(backup_directory)):
        if not filename.startswith(BACKUP_PREFIX) or not filename.endswith(".mtga"):
            continue
        art_id_part, separator, _ = filename[len(BACKUP_PREFIX):].partition("_")
        if separator and art_id_part.isascii() and art_id_part.isdigit():
            backup_index.setdefault(normalize_art_id(art_id_part), filename)
    return backup_index


def recover_images_from_backups(
    art_ids, backup_directory, images_directory
) -> Tuple[int, List[str]]:
    """
    Rebuild swapped_images entries from MOD_ bundle backups.

    For users who swapped art before share packs existed, the backups are the only record
    of that art. A MOD_ backup is written by any operation that calls save_grp_id_info --
    including a parallax unlock -- so it is NOT evidence the art was customised. The caller
    chooses which ArtIds to recover; this reads only what it is given.

    Texture 0 is taken: extract_textures_from_bundle sorts by size and colour complexity,
    and index 0 is the card art in every bundle observed. Art swapped onto a later texture
    recovers wrong, which the caller warns about.

    An ArtId already present in images_directory is left untouched -- a recorded swap is
    authoritative and its bundle is never opened.

    Returns (recovered_count, problem_messages).
    """
    images_directory = Path(images_directory)
    images_directory.mkdir(parents=True, exist_ok=True)

    try:
        backup_index = _index_backup_bundles(backup_directory)
    except OSError as error:
        return 0, [f"Backup directory unavailable: {error}"]

    recovered_count = 0
    problem_messages = []

    for art_id in art_ids:
        normalized_art_id = normalize_art_id(art_id)
        destination_path = images_directory / image_filename_for(normalized_art_id, 0)
        if destination_path.exists():
            continue

        backup_name = backup_index.get(normalized_art_id)
        if not backup_name:
            problem_messages.append(f"ArtId {normalized_art_id}: no backup found")
            continue

        try:
            textures = extract_textures_from_bundle(
                load_unity_bundle(os.path.join(backup_directory, backup_name))
            )
            if not textures:
                problem_messages.append(
                    f"ArtId {normalized_art_id}: backup holds no textures"
                )
                continue
            textures[0].image.save(destination_path, format="PNG")
            recovered_count += 1
        except Exception as error:
            problem_messages.append(f"ArtId {normalized_art_id}: {error}")

    return recovered_count, problem_messages
