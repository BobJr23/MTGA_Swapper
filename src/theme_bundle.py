"""CRC-preserving bundle writes for theme assets, with backup and conflict checks."""
from pathlib import Path
import hashlib
import os
import tempfile
import uuid
import zlib

def save_edited_bundle(environment, file, original):
    import UnityPy
    from UnityPy.streams import EndianBinaryReader
    from src.bundle_crc import expected_crc_for, solve_crc_patch, _member_blob
    file = Path(file)
    if file.read_bytes() != original:
        raise RuntimeError("The bundle changed outside this editor. Reload before saving.")
    expected = expected_crc_for(file)
    if expected is not None:
        # A new, deliberately unreferenced archive member supplies the patch bytes.
        # No existing texture, palette, or serialized object is used as scratch space.
        member_name = "mtga_swapper_theme_" + uuid.uuid4().hex + ".resS"
        member = EndianBinaryReader(bytes(4))
        member.flags = 0
        environment.file.files[member_name] = member
        blob, _ = _member_blob(environment)
        patch = solve_crc_patch(blob[:-4], b"", expected)
        member = EndianBinaryReader(patch)
        member.flags = 0
        environment.file.files[member_name] = member
        blob, _ = _member_blob(environment)
        if zlib.crc32(blob) & 0xFFFFFFFF != expected:
            raise RuntimeError("Could not produce the expected bundle CRC.")
    encoded = environment.file.save()
    digest = hashlib.sha256(original).hexdigest()[:16]
    backup = file.with_name(file.name + "." + digest + ".theme-backup")
    if not backup.exists():
        backup.write_bytes(original)
    descriptor, temporary = tempfile.mkstemp(dir=file.parent, prefix=".theme-", suffix=".mtga")
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        if expected is not None:
            checked, _ = _member_blob(UnityPy.load(encoded))
            if zlib.crc32(checked) & 0xFFFFFFFF != expected:
                raise RuntimeError("Saved bundle did not pass CRC verification.")
        if file.read_bytes() != original:
            raise RuntimeError("The bundle changed during save.")
        os.replace(temporary, file)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return backup
