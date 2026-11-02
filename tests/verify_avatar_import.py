"""Verify sprite imports on temporary copies of downloaded Arena bundles.

Uses the configured database location only to read fixtures. All writes and
backups remain in TemporaryDirectory; installed Arena assets are never edited.
Run from the repository root with the app's Python environment.
"""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
from time import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image
from src.asset_catalog import AssetCatalog, AssetRecord, load_object, object_image
from src.bundle_crc import verify_bundle_crc
from src.sprite_edit import SpriteRegion
from src.unity_bundle import configure_unity_version, save_image_to_file


def run():
    config = json.loads((Path.home() / '.mtga_swapper/config.json').read_text())
    configure_unity_version(config['DatabasePath'])
    catalog = AssetCatalog.load(Path(config['DatabasePath']).parent.parent)
    fixtures = [record for record in catalog.records if record.role == 'Avatar'
                and record.available and 'avatar_' in Path(record.path).name.lower()]
    portraits = [record for record in catalog.records if record.role == 'Avatar'
                 and record.available and Path(record.path).name.lower().startswith('avatarbust_')]
    fixtures = fixtures[:1] + portraits[:2]
    if not fixtures:
        raise RuntimeError('No downloaded avatar portrait fixtures found.')
    tree = ast.parse(Path('main.py').read_text(encoding='utf-8'))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == 'apply_workspace_asset')
    for source_record in fixtures:
        digest = hashlib.sha256(source_record.file.read_bytes()).digest()
        with tempfile.TemporaryDirectory(prefix='mtga_avatar_verification_') as temporary:
            folder = Path(temporary)
            output, backups = folder / 'images', folder / 'backups'
            output.mkdir()
            backups.mkdir()
            copy = folder / source_record.bundle
            shutil.copyfile(source_record.file, copy)
            record = AssetRecord(source_record.path, source_record.bundle, copy, 'Avatar')
            environment, reader = load_object(record)
            namespace = dict(Path=Path, time=time, shutil=shutil, save_image_to_file=save_image_to_file,
                             image_save_directory=str(output), backup_directory=backups)
            exec(compile(ast.Module(body=[function], type_ignores=[]), 'main.py', 'exec'), namespace)
            # Include every neighboring sprite, even if it is not manifest-indexed.
            neighbors = {obj.path_id: object_image(obj).convert('RGBA').tobytes()
                         for obj in environment.objects if obj.type.name == 'Sprite'
                         and obj.path_id != reader.path_id}
            for color in ('#de3154', '#26bc79'):
                region = SpriteRegion.from_reader(reader, environment)
                imported = Image.new('RGBA', (300, 500), color)
                imported.paste((40, 80, 220, 80), (50, 80, 200, 350))
                prepared = region.replace(imported)
                expected = prepared.preview
                target = dict(record=record, reader=reader, environment=environment,
                              bundle_original=copy.read_bytes(), sprite_region=region)
                namespace['apply_workspace_asset'](target, imported)
                okay, message = verify_bundle_crc(copy)
                assert okay, message
                environment, reader = load_object(record)
                actual = object_image(reader).convert('RGBA')
                assert actual.size == expected.size
                assert actual.tobytes() == expected.tobytes(), 'Saved sprite differs from its staged preview'
                for obj in environment.objects:
                    if obj.path_id in neighbors and obj.type.name == 'Sprite':
                        assert object_image(obj).convert('RGBA').tobytes() == neighbors[obj.path_id], (
                            'Neighbor sprite changed: ' + str(obj.path_id))
                assert (backups / ('MOD_' + copy.name)).read_bytes() == copy.read_bytes()
                assert list(output.glob('*.png'))
            print(Path(record.path).name, ': repeated import, preview, neighbors, backups and CRC passed')
        assert hashlib.sha256(source_record.file.read_bytes()).digest() == digest


if __name__ == '__main__':
    run()
