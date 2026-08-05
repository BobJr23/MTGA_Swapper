# Share pack creation and loading for MTGA Swapper.
# A share pack is a .zip holding a user's swapped card art (one PNG per ArtId)
# alongside exported_changes.json, so a whole setup can be handed to someone else.
# Deliberately manifest-free: the zip is simple enough to assemble by hand.

import os
from typing import Optional, Tuple

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
