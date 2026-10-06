import io

from PIL import Image


def test_theme_preference_accepts_light_dark_and_defaults_invalid_values():
    from src.modern_ui import theme_palette
    assert theme_palette('Light')['BG'] == '#f1f3f6'
    assert theme_palette('Dark')['BG'] == '#191c22'
    assert theme_palette('unknown') == theme_palette('Dark')


def test_theme_save_preserves_existing_path_configuration(tmp_path):
    import json
    config = {'SavePath': 'images', 'DatabasePath': 'cards.mtga'}
    path = tmp_path / 'config.json'
    callback = _main_callback('save_workspace_theme', dict(user_config=config,
                             user_config_file_path=path, json=json))
    callback('Light')
    assert json.loads(path.read_text()) == {
        'SavePath': 'images', 'DatabasePath': 'cards.mtga', 'Theme': 'Light'}


def test_preview_preserves_aspect_and_source_pixels():
    from src.modern_ui import preview_bytes
    image = Image.new('RGBA', (800, 400), 'red')
    preview = Image.open(io.BytesIO(preview_bytes(image, (200, 200))))
    assert preview.size == (200, 200)
    assert preview.getpixel((100, 49))[:3] != (255, 0, 0)
    assert preview.getpixel((100, 50))[:3] == (255, 0, 0)
    assert preview.getpixel((100, 149))[:3] == (255, 0, 0)
    assert preview.getpixel((100, 150))[:3] != (255, 0, 0)
    assert image.size == (800, 400)


def test_land_search_deck_and_sort_are_combined():
    from src.modern_ui import filter_cards
    cards = ['island ZEN 1 12 111', 'forest ZEN 1 13 112',
             'island ABC 1 14 113', 'bolt ZEN 1 15 114']
    assert filter_cards(cards, 'Basic Lands', 'island', 'Set', {'island'}) == [
        'island ABC 1 14 113', 'island ZEN 1 12 111']
    assert filter_cards(cards, 'Cards', '', 'Name', {'bolt'}) == ['bolt ZEN 1 15 114']
    assert filter_cards(cards, 'Cards', '', 'Name', set()) == []


def test_replacement_is_staged_without_modifying_input_and_clear_discards_it(tmp_path):
    from src.modern_ui import Replacement
    path = tmp_path / 'custom.png'
    Image.new('RGBA', (400, 200), (10, 20, 30, 40)).save(path)
    original = path.read_bytes()
    replacement = Replacement()
    replacement.choose(path)
    replacement.process(remove_alpha=True, ratio=(1, 1))
    assert replacement.image.size == (200, 200)
    assert replacement.image.mode == 'RGB'
    assert path.read_bytes() == original
    replacement.clear()
    assert replacement.image is None
    assert replacement.path is None


def test_invalid_ratio_keeps_staged_image():
    from src.modern_ui import Replacement
    import pytest
    replacement = Replacement()
    replacement.image = Image.new('RGB', (200, 100))
    with pytest.raises(ValueError):
        replacement.process(ratio=(0, 1))
    assert replacement.image.size == (200, 100)


def _main_callback(name, namespace):
    # Importing main launches the updater and writes user settings. Extract the
    # callback to exercise the actual implementation without those side effects.
    import ast
    from pathlib import Path
    tree = ast.parse(Path('main.py').read_text(encoding='utf-8'))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
    exec(compile(ast.Module(body=[function], type_ignores=[]), 'main.py', 'exec'), namespace)
    return namespace[name]


def test_cosmetic_apply_keeps_original_image_and_modified_bundle_backups(tmp_path):
    from pathlib import Path
    from types import SimpleNamespace
    import shutil
    from src.image_utils import save_image_to_file
    file = tmp_path / 'sleeve.mtga'
    file.write_bytes(b'original bundle')
    output = tmp_path / 'images'
    backups = tmp_path / 'backups'
    output.mkdir()
    backups.mkdir()
    texture = SimpleNamespace(image=Image.new('RGBA', (20, 30), (10, 20, 30, 40)))
    # Substitute only the Unity serialization boundary; files/backups are real.
    def write_texture(texture, replacement, file, environment):
        Path(file).write_bytes(Path(replacement).read_bytes())
    callback = _main_callback('apply_workspace_asset', dict(
        Path=Path, time=lambda: 123, shutil=shutil,
        image_save_directory=str(output), backup_directory=backups,
        save_image_to_file=save_image_to_file, replace_texture_in_bundle=write_texture))
    target = dict(record=SimpleNamespace(file=file, bundle=file.name),
                  bundle_original=b'original bundle', environment=object(),
                  reader=SimpleNamespace(path_id=7, read=lambda: texture))
    callback(target, Image.new('RGB', (40, 50), 'red'))
    assert (backups / 'MOD_sleeve.mtga').read_bytes() == file.read_bytes()
    with Image.open(output / 'sleeve.mtga-7_backup123.png') as image:
        assert image.size == (20, 30)
        assert image.getpixel((0, 0)) == (10, 20, 30, 40)
    with Image.open(file) as image:
        assert image.size == (40, 50)


def test_cosmetic_apply_refuses_external_bundle_change(tmp_path):
    from pathlib import Path
    from types import SimpleNamespace
    import pytest
    file = tmp_path / 'sleeve.mtga'
    file.write_bytes(b'changed outside editor')
    callback = _main_callback('apply_workspace_asset', dict(image_save_directory=str(tmp_path)))
    with pytest.raises(ValueError, match='changed outside'):
        callback(dict(record=SimpleNamespace(file=file), bundle_original=b'original'), Image.new('RGB', (1, 1)))
    assert file.read_bytes() == b'changed outside editor'


def test_card_apply_keeps_full_resolution_for_share_pack_and_both_alpha_backups(tmp_path):
    from pathlib import Path
    from types import SimpleNamespace
    import shutil
    from src.image_utils import save_image_to_file
    from src.share_pack import record_swapped_image
    file = tmp_path / '000111_art.mtga'
    file.write_bytes(b'original bundle')
    output, backups, packs = (tmp_path / name for name in ('images', 'backups', 'packs'))
    for folder in (output, backups, packs):
        folder.mkdir()
    texture = SimpleNamespace(image=Image.new('RGBA', (20, 30), (10, 20, 30, 40)))
    def write_texture(texture, replacement, file, environment):
        Path(file).write_bytes(Path(replacement).read_bytes())
    callback = _main_callback('apply_workspace_card', dict(
        Path=Path, time=lambda: 123, shutil=shutil, image_save_directory=str(output),
        backup_directory=backups, swapped_images_directory=packs,
        save_image_to_file=save_image_to_file, replace_texture_in_bundle=write_texture,
        record_swapped_image=record_swapped_image, load_unity_bundle=lambda _: object(),
        extract_textures_from_bundle=lambda _: [texture]))
    target = dict(card=SimpleNamespace(name='island', art_id='000111'), bundle=file,
                  index=0, bundle_original=b'original bundle')
    callback(target, Image.new('RGB', (1200, 800), 'red'))
    assert (backups / 'MOD_000111_art.mtga').read_bytes() == file.read_bytes()
    assert target['bundle_original'] == file.read_bytes()
    with Image.open(packs / '000111.png') as image:
        assert image.size == (1200, 800)
    assert sorted(Image.open(path).mode for path in output.iterdir()) == ['RGB', 'RGBA']
