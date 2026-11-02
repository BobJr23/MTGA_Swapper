import json
import os
from pathlib import Path
import sqlite3

import pytest


def database(raw, suffix):
    raw.mkdir(parents=True, exist_ok=True)
    file = raw / f'Raw_CardDatabase_{suffix}.mtga'
    con = sqlite3.connect(file)
    con.execute('CREATE TABLE Cards (GrpId INTEGER, ArtId INTEGER, TitleId INTEGER, '
                'Order_Title TEXT, ExpansionCode TEXT, ArtSize INTEGER, LinkedFaceGrpIds TEXT, '
                'Tags TEXT, KnownSupportedStyles TEXT)')
    con.execute("INSERT INTO Cards (GrpId, ArtId, Order_Title, ExpansionCode, ArtSize) VALUES (1, 100, 'bolt', 'ABC', 1)")
    con.execute('CREATE TABLE Localizations_enUS (LocId INTEGER, Loc TEXT)')
    con.commit()
    con.close()
    return file


def manifest(downloads, name, *files):
    file = downloads / name
    file.write_text(json.dumps({'Assets': [{'Name': f.name} for f in files]}))
    return file


def test_active_general_manifest_wins_over_newer_future_and_saved_future(tmp_path):
    from src.database_locator import select_card_database
    raw = tmp_path / 'Downloads/Raw'
    active = database(raw, 'active')
    future = database(raw, 'future')
    general = manifest(raw.parent, 'Manifest_current.mtga', active)
    upcoming = manifest(raw.parent, 'Manifest_upcoming.mtga', future)
    log = tmp_path / 'Player.log'
    log.write_text(f'[Manifest]Using manifest metadata: General|{general.name}\n'
                   f'[Manifest]Using manifest metadata: Future|{upcoming.name}\n')
    os.utime(future, (2000000000, 2000000000))
    selection = select_card_database(raw, preferred_path=future, log_paths=[log])
    assert selection.path == active
    assert 'General' in selection.reason
    con = sqlite3.connect(selection.path)
    con.execute('UPDATE Cards SET ArtId=200 WHERE GrpId=1')
    con.commit()
    con.close()
    con = sqlite3.connect(future)
    assert con.execute('SELECT ArtId FROM Cards WHERE GrpId=1').fetchone() == (100,)
    con.close()
    # Redownloading/touching Future content must not change the next selection.
    assert select_card_database(raw, preferred_path=future, log_paths=[log]).path == active


def test_last_general_manifest_in_log_handles_an_arena_update(tmp_path):
    from src.database_locator import select_card_database
    raw = tmp_path / 'Raw'
    old, active = database(raw, 'old'), database(raw, 'active')
    old_manifest = manifest(tmp_path, 'Manifest_old.mtga', old)
    active_manifest = manifest(tmp_path, 'Manifest_active.mtga', active)
    log = tmp_path / 'Player.log'
    log.write_text(f'[Manifest]Using manifest metadata: General|{old_manifest.name}\n'
                   f'[Manifest]Using manifest metadata: General|{active_manifest.name}\n')
    assert select_card_database(raw, preferred_path=old, log_paths=[log]).path == active


def test_saved_manual_database_is_stable_without_active_manifest_metadata(tmp_path):
    from src.database_locator import select_card_database
    active, extra = database(tmp_path, 'manual'), database(tmp_path, 'extra')
    before = {f.name: f.read_bytes() for f in tmp_path.iterdir()}
    assert select_card_database(tmp_path, preferred_path=active, log_paths=[]).path == active
    assert {f.name: f.read_bytes() for f in tmp_path.iterdir()} == before


def test_ambiguous_databases_are_not_guessed_from_timestamps(tmp_path):
    from src.database_locator import select_card_database, DatabaseSelectionError
    database(tmp_path, 'one')
    database(tmp_path, 'two')
    with pytest.raises(DatabaseSelectionError, match='Arena'):
        select_card_database(tmp_path, log_paths=[])


def test_future_only_database_is_never_a_fallback(tmp_path):
    from src.database_locator import select_card_database, DatabaseSelectionError
    raw = tmp_path / 'Raw'
    future = database(raw, 'future')
    upcoming = manifest(tmp_path, 'Manifest_future.mtga', future)
    log = tmp_path / 'Player.log'
    log.write_text(f'[Manifest]Using manifest metadata: Future|{upcoming.name}\n')
    with pytest.raises(DatabaseSelectionError):
        select_card_database(raw, preferred_path=future, log_paths=[log])


def test_active_missing_database_is_not_replaced_with_future_or_old(tmp_path):
    from src.database_locator import select_card_database, DatabaseSelectionError
    raw = tmp_path / 'Raw'
    old = database(raw, 'old')
    active = raw / 'Raw_CardDatabase_missing.mtga'
    general = manifest(tmp_path, 'Manifest_active.mtga', active)
    log = tmp_path / 'Player.log'
    log.write_text(f'[Manifest]Using manifest metadata: General|{general.name}\n')
    with pytest.raises(DatabaseSelectionError, match='download'):
        select_card_database(raw, preferred_path=old, log_paths=[log])
    assert not active.exists()


def test_invalid_sqlite_and_unrelated_databases_are_excluded(tmp_path):
    from src.database_locator import select_card_database
    active = database(tmp_path, 'valid')
    (tmp_path / 'Raw_CardDatabase_broken.mtga').write_bytes(b'incomplete download')
    sqlite3.connect(tmp_path / 'Raw_CardDatabase_empty.mtga').close()
    assert select_card_database(tmp_path, log_paths=[]).path == active


def test_latest_audio_log_entry_does_not_hide_general_card_manifest(tmp_path):
    from src.database_locator import select_card_database
    raw = tmp_path / 'Raw'
    active, future = database(raw, 'current'), database(raw, 'future')
    general = manifest(tmp_path, 'Manifest_general.mtga', active)
    audio = manifest(tmp_path, 'Manifest_Audio_foo.mtga', Path('Audio.pck'))
    log = tmp_path / 'Player.log'
    log.write_text(f'[Manifest]Using manifest metadata: General|{general.name}\n'
                   f'[Manifest]Using manifest metadata: General|{audio.name}\n')
    assert select_card_database(raw, log_paths=[log]).path == active


def test_crop_database_follows_the_manifest_of_selected_card_database(tmp_path):
    from src.database_locator import select_crop_database
    raw = tmp_path / 'Raw'
    active, future = database(raw, 'current'), database(raw, 'future')
    for name in ('Raw_ArtCropDatabase_current.mtga', 'Raw_ArtCropDatabase_future.mtga'):
        con = sqlite3.connect(raw / name)
        con.execute('CREATE TABLE Crops (Path TEXT, Format TEXT, X REAL, Y REAL, Z REAL, W REAL, Generated INTEGER)')
        con.close()
    current_crop = raw / 'Raw_ArtCropDatabase_current.mtga'
    future_crop = raw / 'Raw_ArtCropDatabase_future.mtga'
    manifest(tmp_path, 'Manifest_general.mtga', active, current_crop)
    manifest(tmp_path, 'Manifest_future.mtga', future, future_crop)
    assert select_crop_database(active) == current_crop
    assert select_crop_database(future) == future_crop
    from src.load_preset import apply_crop_changes
    apply_crop_changes({'100': [{'path': 'Assets/Art/100', 'format': 'Normal',
                                'x': 1, 'y': .5, 'z': 0, 'w': .25, 'generated': 1}]},
                       str(tmp_path / 'AssetBundle'), str(active))
    con = sqlite3.connect(current_crop)
    assert con.execute('SELECT X,Y,Z,W FROM Crops').fetchall() == [(1, .5, 0, .25)]
    con.close()
    con = sqlite3.connect(future_crop)
    assert con.execute('SELECT COUNT(*) FROM Crops').fetchone() == (0,)
    con.close()


def test_open_missing_database_does_not_create_an_empty_file(tmp_path):
    from src.sql_editor import create_database_connection
    missing = tmp_path / 'Raw_CardDatabase_missing.mtga'
    with pytest.raises(sqlite3.OperationalError):
        create_database_connection(str(missing))
    assert not missing.exists()


def test_logged_missing_manifest_does_not_use_saved_old_database(tmp_path):
    from src.database_locator import select_card_database, DatabaseSelectionError
    raw = tmp_path / 'Raw'
    old = database(raw, 'old')
    log = tmp_path / 'Player.log'
    log.write_text('[Manifest]Using manifest metadata: General|Manifest_missing.mtga\n')
    with pytest.raises(DatabaseSelectionError, match='download'):
        select_card_database(raw, preferred_path=old, log_paths=[log])


def test_unpaired_future_crop_database_is_not_used_as_a_fallback(tmp_path):
    from src.database_locator import select_crop_database, DatabaseSelectionError
    raw = tmp_path / 'Raw'
    current, future = database(raw, 'current'), database(raw, 'future')
    crop = raw / 'Raw_ArtCropDatabase_future.mtga'
    con = sqlite3.connect(crop)
    con.execute('CREATE TABLE Crops (Path TEXT, Format TEXT, X REAL, Y REAL, Z REAL, W REAL, Generated INTEGER)')
    con.close()
    manifest(tmp_path, 'Manifest_future.mtga', future, crop)
    with pytest.raises(DatabaseSelectionError):
        select_crop_database(current)


def test_another_installations_log_does_not_override_saved_database(tmp_path):
    from src.database_locator import select_card_database
    first = tmp_path / 'first/MTGA_Data/Downloads/Raw'
    second = tmp_path / 'second/MTGA_Data/Downloads/Raw'
    chosen, other = database(first, 'chosen'), database(second, 'other')
    other_manifest = manifest(second.parent, 'Manifest_other.mtga', other)
    log = tmp_path / 'Player.log'
    log.write_text(f"Mono path[0] = '{second.parent.parent.as_posix()}/Managed'\n"
                   f'[Manifest]Using manifest metadata: General|{other_manifest.name}\n')
    assert select_card_database(first, preferred_path=chosen, log_paths=[log]).path == chosen


def test_auto_finder_follows_the_installation_from_the_current_arena_log(tmp_path, monkeypatch):
    from src.load_preset import find_mtga_db_path
    from src import database_locator
    first = tmp_path / 'first/MTGA_Data/Downloads/Raw'
    second = tmp_path / 'second/MTGA_Data/Downloads/Raw'
    saved, active = database(first, 'saved'), database(second, 'active')
    active_manifest = manifest(second.parent, 'Manifest_active.mtga', active)
    log = tmp_path / 'Player.log'
    log.write_text(f"Mono path[0] = '{second.parent.parent.as_posix()}/Managed'\n"
                   f'[Manifest]Using manifest metadata: General|{active_manifest.name}\n')
    monkeypatch.setattr('src.load_preset.platform.system', lambda: 'Linux')
    monkeypatch.setattr(database_locator, 'arena_log_paths', lambda: [log])
    assert Path(find_mtga_db_path(saved)) == active


def test_open_editor_rejects_database_changed_by_a_new_general_manifest(tmp_path, monkeypatch):
    from src import database_locator
    from src.database_locator import require_current_database, DatabaseSelectionError
    raw = tmp_path / 'Raw'
    old, active = database(raw, 'old'), database(raw, 'active')
    active_manifest = manifest(tmp_path, 'Manifest_active.mtga', active)
    log = tmp_path / 'Player.log'
    log.write_text(f'[Manifest]Using manifest metadata: General|{active_manifest.name}\n')
    monkeypatch.setattr(database_locator, 'arena_log_paths', lambda: [log])
    with pytest.raises(DatabaseSelectionError, match='changed'):
        require_current_database(old, old.stat().st_ino)
    require_current_database(active, active.stat().st_ino)


@pytest.mark.parametrize('event', ['-LOAD_PRESET-', '-UNLOCK_PARALLAX-'])
def test_blocking_picker_or_confirmation_revalidates_before_database_write(tmp_path, monkeypatch, event):
    import ast
    from types import SimpleNamespace
    from src import database_locator
    raw = tmp_path / 'Raw'
    old, active = database(raw, 'old'), database(raw, 'active')
    old_manifest = manifest(tmp_path, 'Manifest_old.mtga', old)
    active_manifest = manifest(tmp_path, 'Manifest_active.mtga', active)
    log = tmp_path / 'Player.log'
    log.write_text(f'[Manifest]Using manifest metadata: General|{old_manifest.name}\n')
    monkeypatch.setattr(database_locator, 'arena_log_paths', lambda: [log])
    preset = tmp_path / 'preset.json'
    preset.write_text('{}')
    writes, errors = [], []
    def change_game_during_dialog(*args, **kwargs):
        log.write_text(f'[Manifest]Using manifest metadata: General|{active_manifest.name}\n')
        return str(preset) if event == '-LOAD_PRESET-' else 'Yes'
    scope = dict(event=event, Path=Path, json=json, database_file_path=str(old),
                 database_identity=old.stat().st_ino, database_selection_error=None,
                 require_current_database=database_locator.require_current_database,
                 DatabaseSelectionError=database_locator.DatabaseSelectionError,
                 askopenfilename=change_game_during_dialog,
                 sg=SimpleNamespace(popup_yes_no=change_game_during_dialog,
                                    popup_error=lambda *args, **kwargs: errors.append(args[0])),
                 filtered_search_results=['bolt ABC 1 1 100'], lands_set=set(),
                 change_grp_id=lambda *args, **kwargs: writes.append('preset'),
                 database_manager=SimpleNamespace(unlock_parallax_style=lambda *args: writes.append('parallax')))
    tree = ast.parse(Path('main.py').read_text(encoding='utf-8'))
    guard = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'editor_database_is_current')
    loop = next(n for n in tree.body if isinstance(n, ast.While))
    action = next(n for n in loop.body if isinstance(n, ast.If) and isinstance(n.test, ast.Compare)
                  and isinstance(n.test.left, ast.Name) and n.test.left.id == 'event'
                  and isinstance(n.test.comparators[0], ast.Constant) and n.test.comparators[0].value == event)
    once = ast.For(target=ast.Name(id='_', ctx=ast.Store()), iter=ast.List(elts=[ast.Constant(None)], ctx=ast.Load()),
                   body=[action], orelse=[])
    module = ast.fix_missing_locations(ast.Module(body=[guard, once], type_ignores=[]))
    exec(compile(module, 'main.py', 'exec'), scope)
    assert writes == []
    assert len(errors) == 1
    assert 'changed' in errors[0]


def test_finder_respects_custom_install_and_saved_path_without_game_log(tmp_path, monkeypatch):
    from src.load_preset import find_mtga_db_path
    from src import database_locator
    old, future = database(tmp_path, 'manual'), database(tmp_path, 'extra')
    monkeypatch.setattr('src.load_preset.platform.system', lambda: 'Linux')
    monkeypatch.setattr(database_locator, 'arena_log_paths', lambda: [])
    assert Path(find_mtga_db_path(str(old))) == old
    assert Path(find_mtga_db_path(str(old))) == old


def test_database_refresh_switches_connection_and_discards_old_library_event(tmp_path):
    import ast
    from types import SimpleNamespace
    from src import sql_editor
    from src.card_models import format_card_display
    from src.database_locator import DatabaseSelectionError
    old, active = database(tmp_path / 'Raw', 'old'), database(tmp_path / 'Raw', 'active')
    cursor, connection, _ = sql_editor.create_database_connection(str(old))
    statuses = []
    class Element:
        def update(self, *args, **kwargs):
            self.value = args[0] if args else None
    window = {key: Element() for key in ('DATABASE_DISPLAY', '-CHANGE_ASSETS-', '-SET_SWAPPER-')}
    scope = dict(Path=Path, json=json, database_manager=sql_editor,
                 database_cursor=cursor, database_connection=connection, database_file_path=str(old),
                 database_identity=old.stat().st_ino, database_selection_error=None,
                 last_database_check=0, time=lambda: 10,
                 find_mtga_db_path=lambda *args, **kwargs: str(active),
                 DatabaseSelectionError=DatabaseSelectionError,
                 get_cards_query='SELECT Order_Title, ExpansionCode, ArtSize, GrpId, ArtId FROM Cards',
                 format_card_display=format_card_display, configure_unity_version=lambda _: None,
                 main_window=window, user_config={'Theme': 'Light'}, user_config_file_path=tmp_path / 'config.json',
                 workspace=SimpleNamespace(clear_target=lambda: None, refresh=lambda _: None,
                                           status=lambda message, **kwargs: statuses.append(message)))
    tree = ast.parse(Path('main.py').read_text(encoding='utf-8'))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in ('activate_database', 'refresh_current_database')]
    exec(compile(ast.Module(body=functions, type_ignores=[]), 'main.py', 'exec'), scope)
    try:
        assert scope['refresh_current_database']({}) is False
        assert scope['database_file_path'] == str(active)
        with pytest.raises(sqlite3.ProgrammingError):
            connection.execute('SELECT 1')
        assert Path(scope['database_connection'].execute('PRAGMA database_list').fetchone()[2]) == active
        assert window['DATABASE_DISPLAY'].value == str(active)
        assert scope['first_card_to_swap'] is None
        assert json.loads((tmp_path / 'config.json').read_text()) == {'Theme': 'Light', 'DatabasePath': active.as_posix()}
        assert scope['refresh_current_database']({}) is True
    finally:
        scope['database_connection'].close()
