# Unity AssetBundle CRC restoration for MTGA asset bundles.
#
# MTGA's download manifest (MTGA_Data/Downloads/Manifest_*.mtga, plain JSON) records a
# CRC per bundle, and the game passes it to AssetBundle.LoadFromFile. Any bundle this
# tool rewrites therefore fails to load outright:
#
#   CRC Mismatch. Provided 972e0a80, calculated d4edbec2 from data.
#     Will not load AssetBundle '...\AssetBundle\440362_CardArt_972e0a80-...mtga'
#   [Assets] Couldnt find asset Assets/Core/CardArt/440000/440362_AIF.tga
#
# and the card falls back to the game's placeholder art. This module recomputes the CRC
# after a write and tunes four throwaway bytes so it matches again.
#
# The expected CRC is the 8-hex group in the bundle's own filename, so no manifest lookup
# is needed -- it agreed with the manifest's "crc" field for all 27318 AssetBundle entries
# present at the time of writing. Files with no such group (ALT_*, Raw_*, resources.assets,
# audio .pck) carry no CRC in the manifest and are not checked by the game; they are
# skipped rather than touched.

import re
import zlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 434585_CardArt_89f11d38-bef421b0105f753d63db6d910c111a3c.mtga
#                ^^^^^^^^ the value Unity verifies
BUNDLE_CRC_PATTERN = re.compile(r"_([0-9A-Fa-f]{8})-[0-9A-Fa-f]{32}\.mtga$")

# Bytes needed to steer CRC32 to an arbitrary value. Four is exactly enough: the
# register is 32 bits wide, so four free bytes span the whole solution space.
PATCH_BYTES = 4

# The CRC is taken over the concatenated *uncompressed* archive members, so any object
# type that streams out of the .resS competes for the dead space this module writes into.
# Only bundles built solely from these types get the .resS strategy; anything else falls
# back to patching bytes the replaced texture itself owns.
RESOURCE_SAFE_OBJECT_TYPES = frozenset({"AssetBundle", "Texture2D"})


class BundleCrcError(Exception):
    """Raised when a bundle's CRC could not be restored, so the caller can warn loudly."""


def expected_crc_for(bundle_file_path) -> Optional[int]:
    """
    The CRC MTGA will demand for this bundle, or None if it is not a CRC-checked bundle.

    MOD_ backups keep the original name after the prefix, so the pattern still matches
    and a restored backup can be verified the same way as a live bundle.
    """
    match = BUNDLE_CRC_PATTERN.search(Path(bundle_file_path).name)
    return int(match.group(1), 16) if match else None


def _load(bundle_file_path):
    # Imported lazily: unity_bundle imports this module for the write path.
    from .unity_bundle import load_unity_bundle

    return load_unity_bundle(str(bundle_file_path))


def _member_blob(unity_environment) -> Tuple[bytes, List[Tuple[str, int]]]:
    """
    The exact bytes Unity runs CRC32 over: every archive member, uncompressed, in order.

    Verified against the game's own log -- this reproduced Unity's "calculated d4edbec2"
    for a modified bundle byte for byte.
    """
    blob = bytearray()
    layout: List[Tuple[str, int]] = []
    for member_name, member in unity_environment.file.files.items():
        if hasattr(member, "bytes"):
            member_bytes = bytes(member.bytes)
        else:
            member_bytes = member.save()
        layout.append((member_name, len(member_bytes)))
        blob += member_bytes
    return bytes(blob), layout


def compute_bundle_crc(bundle_file_path) -> int:
    """The CRC Unity will calculate for this file on disk."""
    blob, _ = _member_blob(_load(bundle_file_path))
    return zlib.crc32(blob) & 0xFFFFFFFF


def solve_crc_patch(prefix: bytes, suffix: bytes, target_crc: int) -> bytes:
    """
    Find the PATCH_BYTES bytes X where crc32(prefix + X + suffix) == target_crc.

    CRC32 is affine over GF(2): f(X) = f(0) XOR g(X) with g linear in X's 32 bits. So
    build g's basis one bit at a time, reduce it to row echelon form, then read the
    answer back out. zlib's chaining (crc32(a + b) == crc32(b, crc32(a))) keeps all 33
    evaluations in C rather than looping over the payload in Python.
    """
    prefix_crc = zlib.crc32(prefix)

    def crc_with(patch: bytes) -> int:
        return zlib.crc32(suffix, zlib.crc32(patch, prefix_crc))

    baseline = crc_with(b"\x00" * PATCH_BYTES)
    remainder = target_crc ^ baseline

    # leading set bit -> (basis vector, the patch bits that produce it)
    pivots: Dict[int, Tuple[int, int]] = {}
    for bit_index in range(PATCH_BYTES * 8):
        vector = crc_with((1 << bit_index).to_bytes(PATCH_BYTES, "little")) ^ baseline
        patch_bits = 1 << bit_index
        while vector:
            leading_bit = vector.bit_length() - 1
            if leading_bit not in pivots:
                pivots[leading_bit] = (vector, patch_bits)
                break
            existing_vector, existing_bits = pivots[leading_bit]
            vector ^= existing_vector
            patch_bits ^= existing_bits

    solution = 0
    while remainder:
        leading_bit = remainder.bit_length() - 1
        if leading_bit not in pivots:
            raise BundleCrcError("CRC target is unreachable from this patch site.")
        vector, patch_bits = pivots[leading_bit]
        remainder ^= vector
        solution ^= patch_bits
    return solution.to_bytes(PATCH_BYTES, "little")


def _member_offsets(layout: List[Tuple[str, int]]) -> Dict[str, Tuple[int, int]]:
    """member name -> (start offset in the blob, length)."""
    offsets = {}
    cursor = 0
    for member_name, length in layout:
        offsets[member_name] = (cursor, length)
        cursor += length
    return offsets


def _resource_patch_site(unity_environment, layout) -> Optional[int]:
    """
    Blob offset of unreferenced bytes inside a .resS member, or None.

    Card art bundles keep both textures in a .resS. Replacing one moves its pixels inline
    into the SerializedFile and clears its m_StreamData, which leaves the region it used
    to occupy in the .resS referenced by nobody -- free bytes that cost no image quality.
    """
    object_types = {obj.type.name for obj in unity_environment.objects}
    if not object_types <= RESOURCE_SAFE_OBJECT_TYPES:
        return None

    offsets = _member_offsets(layout)
    claimed: Dict[str, List[Tuple[int, int]]] = {name: [] for name in offsets}
    for obj in unity_environment.objects:
        if obj.type.name != "Texture2D":
            continue
        stream_data = getattr(obj.read(), "m_StreamData", None)
        if stream_data is None or not stream_data.path or not stream_data.size:
            continue
        # m_StreamData.path is "archive:/CAB-xxx/CAB-xxx.resS"
        referenced_member = stream_data.path.rsplit("/", 1)[-1]
        if referenced_member in claimed:
            claimed[referenced_member].append(
                (stream_data.offset, stream_data.offset + stream_data.size)
            )

    for member_name, (member_start, member_length) in offsets.items():
        if not member_name.endswith(".resS"):
            continue
        gap_start = 0
        for range_start, range_end in sorted(claimed[member_name]) + [
            (member_length, member_length)
        ]:
            if range_start - gap_start >= PATCH_BYTES:
                # Sit a little inside the gap rather than flush against a live range.
                return member_start + gap_start + min(
                    64, range_start - gap_start - PATCH_BYTES
                )
            gap_start = max(gap_start, range_end)
    return None


def _texture_tail_patch_site(unity_environment, blob: bytes) -> Optional[int]:
    """
    Blob offset of the last bytes of the largest texture's inline pixel data, or None.

    Fallback for bundles with no dead .resS space. These bytes belong to the texture this
    tool just wrote, so nothing else can be corrupted by tuning them. Where the texture
    carries a mip chain they land in its smallest mip, which is only ever sampled when the
    card is drawn a few pixels wide.
    """
    textures = [
        texture
        for texture in (
            obj.read() for obj in unity_environment.objects if obj.type.name == "Texture2D"
        )
        if texture.image_data
    ]
    if not textures:
        return None

    texture = max(textures, key=lambda item: len(item.image_data))
    pixel_data = bytes(texture.image_data)
    first = blob.find(pixel_data)
    if first < 0 or blob.find(pixel_data, first + 1) >= 0:
        # Ambiguous or absent: refuse rather than patch the wrong copy.
        return None
    return first + len(pixel_data) - PATCH_BYTES


def restore_bundle_crc(bundle_file_path) -> str:
    """
    Make MTGA accept a bundle this tool has rewritten, and report what happened.

    Idempotent: a bundle whose CRC already matches is left untouched, so this is safe to
    run over restored backups and imported share pack art as well as fresh swaps.

    Raises BundleCrcError if the CRC cannot be restored -- the art is already written at
    that point, so callers should surface it rather than swallow it.
    """
    bundle_path = Path(bundle_file_path)
    expected_crc = expected_crc_for(bundle_path)
    if expected_crc is None:
        return f"{bundle_path.name}: not a CRC-checked bundle, left as is"

    unity_environment = _load(bundle_path)
    blob, layout = _member_blob(unity_environment)
    if zlib.crc32(blob) & 0xFFFFFFFF == expected_crc:
        return f"{bundle_path.name}: CRC already correct"

    patch_site = _resource_patch_site(unity_environment, layout)
    site_description = "unused .resS space"
    if patch_site is None:
        patch_site = _texture_tail_patch_site(unity_environment, blob)
        site_description = "texture data tail"
    if patch_site is None:
        raise BundleCrcError(
            f"{bundle_path.name}: no safe bytes available to restore the CRC; "
            "MTGA will refuse to load this bundle."
        )

    patch = solve_crc_patch(blob[:patch_site], blob[patch_site + PATCH_BYTES :], expected_crc)

    original_bytes = bundle_path.read_bytes()
    blob_offset = original_bytes.find(blob)
    if blob_offset < 0:
        raise BundleCrcError(
            f"{bundle_path.name}: bundle payload is not stored uncompressed, "
            "so the CRC could not be restored."
        )

    patched_bytes = bytearray(original_bytes)
    patch_offset = blob_offset + patch_site
    patched_bytes[patch_offset : patch_offset + PATCH_BYTES] = patch
    bundle_path.write_bytes(bytes(patched_bytes))

    # Confirm against a fresh read: this is the number the game will compute.
    final_crc = compute_bundle_crc(bundle_path)
    if final_crc != expected_crc:
        bundle_path.write_bytes(original_bytes)
        raise BundleCrcError(
            f"{bundle_path.name}: CRC restore failed "
            f"(got {final_crc:08x}, expected {expected_crc:08x}); bundle left unpatched."
        )

    return f"{bundle_path.name}: CRC restored to {expected_crc:08x} via {site_description}"


def verify_bundle_crc(bundle_file_path) -> Tuple[bool, str]:
    """
    Check whether MTGA will load a bundle. Returns (ok, human readable detail).

    Used for diagnostics and for repairing MOD_ backups written before CRC restoration
    existed -- those carry the art but the wrong CRC.
    """
    bundle_path = Path(bundle_file_path)
    expected_crc = expected_crc_for(bundle_path)
    if expected_crc is None:
        return True, f"{bundle_path.name}: not CRC-checked"
    try:
        actual_crc = compute_bundle_crc(bundle_path)
    except Exception as error:
        return False, f"{bundle_path.name}: could not be read ({error})"
    if actual_crc == expected_crc:
        return True, f"{bundle_path.name}: CRC {actual_crc:08x} OK"
    return (
        False,
        f"{bundle_path.name}: CRC {actual_crc:08x} but MTGA expects {expected_crc:08x}",
    )


def scan_and_repair(targets, repair: bool = False) -> Tuple[int, int, List[str]]:
    """
    Verify (and optionally repair) every CRC-checked bundle under the given paths.

    Covers the two cases the write path cannot: bundles swapped before CRC restoration
    existed, and MOD_ backups holding good art with a stale CRC. Returns
    (checked_count, repaired_count, messages).
    """
    bundle_paths: List[Path] = []
    for target in targets:
        target_path = Path(target)
        if target_path.is_dir():
            bundle_paths.extend(sorted(target_path.glob("*.mtga")))
        elif target_path.is_file():
            bundle_paths.append(target_path)

    checked = repaired = 0
    messages: List[str] = []
    for bundle_path in bundle_paths:
        if expected_crc_for(bundle_path) is None:
            continue
        checked += 1
        is_valid, detail = verify_bundle_crc(bundle_path)
        if is_valid:
            continue
        if not repair:
            messages.append(detail)
            continue
        try:
            messages.append(restore_bundle_crc(bundle_path))
            repaired += 1
        except Exception as error:
            messages.append(f"{bundle_path.name}: repair failed ({error})")
    return checked, repaired, messages


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Verify or repair the Unity AssetBundle CRC that MTGA checks before loading "
            "a bundle. Point it at the game's AssetBundle folder and/or "
            "~/MTGA_Swapper_Backups."
        )
    )
    parser.add_argument("targets", nargs="+", help="Bundle files or directories")
    parser.add_argument(
        "--repair",
        action="store_true",
        help="Rewrite mismatched bundles so MTGA will load them (default: report only).",
    )
    arguments = parser.parse_args()

    checked, repaired, messages = scan_and_repair(arguments.targets, arguments.repair)
    for message in messages:
        print(message)
    print(f"\nchecked {checked} CRC-verified bundle(s); {len(messages)} needed attention", end="")
    print(f"; repaired {repaired}" if arguments.repair else "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
