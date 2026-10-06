"""Real Tk/FreeSimpleGUI layout and event checks; no Arena files are written.

Run with Python from the repository root. Pass --screenshot to capture the
workspace briefly on screen for visual review. Default checks are invisible.
"""
import ast
import sys
from pathlib import Path

if sys.platform == 'win32':
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(2)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import FreeSimpleGUI as sg
from PIL import Image
from src.card_models import MTGACard, format_card_display
from src.modern_ui import (configure_theme, main_layout, Workspace, preview_bytes,
                           card_editor_layout, asset_editor_layout)


def run():
    configure_theme('Light' if '--light' in sys.argv else 'Dark')
    cards = [format_card_display(('island', 'ZEN', '1', '12', '111')),
             format_card_display(('bolt', 'ABC', '1', '15', '114'))]
    filtered = []
    applied = []
    saved_themes = []
    context = lambda: dict(cards=cards, database=None, deck={'island'},
                           set_filtered=lambda result: filtered.__setitem__(slice(None), result),
                           save_theme=saved_themes.append)
    def load_card(formatted):
        return dict(card=MTGACard(*formatted.split()), formatted=formatted), Image.new('RGB', (800, 400), '#465e75')
    window = sg.Window('MTGA Swapper UI verification', main_layout(cards, None, None, 'v1.0', False),
                       finalize=True, alpha_channel=0, location=(30, 30), resizable=True)
    try:
        workspace = Workspace(window, context, load_card, lambda target, image: applied.append(image.size))
        values = {'-SORT_BY-': 'Name', '-SEARCH_INPUT-': '', '-USE_DECKLIST-': False}
        # Every existing main-window key must resolve in the redesigned layout.
        legacy_keys = {'-SELECT_DATABASE-', '-SELECT_OUTPUT_FOLDER-', '-SWAP_ARTS-', '-LOAD_DECKLIST-',
            '-CHANGE_ASSETS-', '-EXPORT_FONTS-', '-CROP_EDITOR-', '-ROLE_BROWSER-', '-THEME_EDITOR-',
            '-SEARCH_TOKENS-', '-LOAD_PRESET-', '-EXPORT_PRESET-', '-EXPORT_SHARE_PACK-',
            '-IMPORT_SHARE_PACK-', '-SET_SWAPPER-', '-JOIN_DISCORD-', 'DATABASE_DISPLAY',
            'IMAGE_SAVE_DISPLAY', '-SEARCH_INPUT-', '-USE_DECKLIST-', '-UNLOCK_PARALLAX-',
            '-LOAD_OLD_CHANGES-', '-EXPORT_ALL_ARTS-', '-RECOVER_BACKUP_ART-', '-SORT_BY-', '-CARD_LIST-'}
        assert legacy_keys <= set(window.key_dict)
        for element in window.key_dict.values():
            if isinstance(element, sg.Button):
                assert int(element.Widget.cget('borderwidth')) >= 1
        assert window['-LIST_ACTIONS-'].visible
        assert window['-UNLOCK_PARALLAX-'].ParentContainer == window['-LIST_ACTIONS-']
        workspace.handle('-APP_THEME-', dict(values, **{'-APP_THEME-': 'Light'}))
        assert saved_themes == ['Light']
        assert len(filtered) == 2
        workspace.handle('-NAV-Basic Lands', values)
        assert filtered == [cards[0]]
        workspace.handle('-CARD_LIST-', dict(values, **{'-CARD_LIST-': [cards[0]]}))
        assert workspace.target['card'].art_id == '111'
        assert applied == []
        workspace.replacement.path = Path('replacement.png')
        workspace.replacement.image = Image.new('RGB', (600, 600), '#ad8f65')
        workspace.paint_replacement()
        assert not window['-APPLY_REPLACEMENT-'].Disabled
        workspace.handle('-APPLY_REPLACEMENT-', values)
        assert applied == [(600, 600)]
        assert workspace.replacement.image is None
        # Exercise exact catalog selection as well as the card-list path.
        from src.asset_catalog import AssetCatalog, AssetRecord
        from types import SimpleNamespace
        from unittest.mock import patch
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / 'sleeve.mtga'
            file.write_bytes(b'unchanged bundle')
            record = AssetRecord('Assets/Sleeves/custom.png', file.name, file, 'Sleeve')
            workspace.catalog = AssetCatalog(Path(folder), [record])
            workspace.handle('-NAV-Card Sleeves', values)
            assert not window['-LIST_ACTIONS-'].visible
            assert workspace.records == [record]
            window['-WORKSPACE_ASSETS-'].update(set_to_index=0)
            reader = SimpleNamespace(type=SimpleNamespace(name='Texture2D'),
                                     read=lambda: SimpleNamespace(image=Image.new('RGBA', (100, 140), 'blue')))
            with patch('src.asset_catalog.load_object', return_value=(object(), reader)):
                workspace.handle('-WORKSPACE_ASSETS-', dict(values, **{'-WORKSPACE_ASSETS-': ['custom [Sleeve]']}))
            assert workspace.target['record'] is record
            assert workspace.original.size == (100, 140)
            assert file.read_bytes() == b'unchanged bundle'
        for event, key in [('-SETTINGS-', '-SETTINGS_PANEL-'), ('-MAINTENANCE-', '-MAINTENANCE_PANEL-'),
                           ('-BACK_LIBRARY-', '-WORKSPACE-')]:
            workspace.handle(event, values)
            assert window[key].visible
        workspace.handle('-TOGGLE_PROCESSING-', values)
        workspace.handle('-TOGGLE_LOG-', values)
        # Expanded sections and a reduced viewport must retain scroll access.
        initial_size = window.size
        window.set_size((initial_size[0], 600))
        window.refresh()
        window['-CONTENT_SCROLL-'].contents_changed()
        canvas = window['-CONTENT_SCROLL-'].Widget.canvas
        canvas.yview_moveto(1)
        window.refresh()
        assert canvas.yview()[1] >= .99
        assert canvas.bbox('all')[3] > canvas.winfo_height()
        canvas.yview_moveto(0)
        window.set_size(initial_size)
        workspace.handle('-TOGGLE_LOG-', values)
        workspace.handle('-TOGGLE_PROCESSING-', values)
        workspace.handle('-NAV-Cards', values)
        assert window['-LIST_ACTIONS-'].visible
        workspace.handle('-CARD_LIST-', dict(values, **{'-CARD_LIST-': [cards[1]]}))
        workspace.replacement.path = Path('custom-art.png')
        workspace.replacement.image = Image.new('RGB', (800, 500), '#947b5d')
        workspace.paint_replacement()
        window.refresh()
        print('Main window size:', window.size)
        action = window['-APPLY_REPLACEMENT-'].Widget
        assert action.winfo_y() + action.winfo_height() <= action.master.winfo_height()
        if '--screenshot' in sys.argv:
            from PIL import ImageGrab
            window.set_alpha(1)
            window.bring_to_front()
            window.refresh()
            window.TKroot.update()
            window.read(timeout=250)
            x, y = window.TKroot.winfo_rootx(), window.TKroot.winfo_rooty()
            ImageGrab.grab(bbox=(x, y, x + window.TKroot.winfo_width(), y + window.TKroot.winfo_height())).save('ui-preview.png')
    finally:
        window.close()
    data = preview_bytes(Image.new('RGB', (200, 300)))
    for layout, required in [
        (card_editor_layout(data, True, ['bolt (ABC)'], '1', False),
         {'-CHANGE_IMAGE-', '-PREVIOUS-', '-NEXT-', '-SET_SWAP_1-', '-SET_SWAP_2-',
          '-ADJUST_STYLE_TAGS-', '-SEARCH_ALTERNATES-', '-EDIT_DETAILS-', '-SET_ASPECT_RATIO-',
          '-ASPECT_WIDTH-', '-ASPECT_HEIGHT-', '-REMOVE_ALPHA-', '-SAVE_IMAGE-', '-UPSCALE_IMAGE-', '-CARD_IMAGE-'}),
        (asset_editor_layout(data, True, 'Texture 1 of 2'),
         {'-CHANGE_ASSET_IMAGE-', '-ASSET_PREVIOUS-', '-ASSET_NEXT-', '-RETURN_GALLERY-',
          '-SET_ASPECT_RATIO-', '-ASPECT_WIDTH-', '-ASPECT_HEIGHT-', '-ASSET_REMOVE_ALPHA-',
          '-SAVE_ASSET-', '-ASSET_IMAGE-', '-ASSET_INFO-'})]:
        editor = sg.Window('Editor verification', layout, finalize=True, alpha_channel=0)
        try:
            assert required <= set(editor.key_dict)
        finally:
            editor.close()
    ast.parse(Path('main.py').read_text(encoding='utf-8'))
    print('Main and detailed editor keys, navigation, preview staging and apply dispatch passed.')


if __name__ == '__main__':
    run()
