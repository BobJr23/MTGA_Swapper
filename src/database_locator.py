"""Resolve Arena's live databases without touching downloaded game files.

Arena pre-downloads Future manifests alongside the General manifest used by the
current client. Neither directory order nor a database's modification time says
which one is active. Player.log records the manifest roles explicitly.
"""
from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
import platform
import re
import sqlite3


class DatabaseSelectionError(RuntimeError):
    pass


@dataclass(frozen=True)
class DatabaseSelection:
    path: Path
    reason: str


CARD_COLUMNS = {'grpid', 'artid', 'titleid', 'order_title', 'expansioncode',
                'artsize', 'linkedfacegrpids', 'tags', 'knownsupportedstyles'}
CROP_COLUMNS = {'path', 'format', 'x', 'y', 'z', 'w', 'generated'}
MANIFEST_LINE = re.compile(
    r'Using manifest metadata:\s*(General|Future)\|([^\s|]+\.mtga)', re.IGNORECASE)
DATA_PATH_LINE = re.compile(r"Mono path\[0\]\s*=\s*['\"](.+?)[/\\]Managed['\"]")


def arena_log_paths():
    home = Path.home()
    if platform.system() == 'Darwin':
        roots = [home / 'Library/Logs/Wizards Of The Coast/MTGA',
                 home / 'Library/Logs/com.wizards.mtga']
    else:
        roots = [home / 'AppData/LocalLow/Wizards Of The Coast/MTGA']
    # Current log takes precedence over the previous session.
    return [root / name for name in ('Player.log', 'Player-prev.log') for root in roots]


def active_data_root(log_paths=None):
    for log in arena_log_paths() if log_paths is None else log_paths:
        try:
            with Path(log).open(encoding='utf-8', errors='replace') as stream:
                for line in stream:
                    match = DATA_PATH_LINE.search(line)
                    if match:
                        return Path(match.group(1)).resolve()
        except OSError:
            continue
    return None


def _database_has_columns(path, table, required):
    if not path.is_file():
        return False
    connection = None
    try:
        connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=1)
        columns = {row[1].casefold() for row in connection.execute(f'PRAGMA table_info({table})')}
        if not required <= columns:
            return False
        connection.execute(f'SELECT * FROM {table} LIMIT 1').fetchone()
        if table == 'Cards':
            localization = {row[1].casefold() for row in connection.execute('PRAGMA table_info(Localizations_enUS)')}
            return {'locid', 'loc'} <= localization
        return True
    except (OSError, sqlite3.Error):
        return False
    finally:
        if connection is not None:
            connection.close()


def is_card_database(path):
    return _database_has_columns(Path(path), 'Cards', CARD_COLUMNS)


@lru_cache(maxsize=32)
def _manifest_names_cached(path, modified, size):
    with Path(path).open(encoding='utf-8-sig') as stream:
        document = json.load(stream)
    assets = document.get('Assets', []) if isinstance(document, dict) else []
    # Manifests are data. Only bare filenames may be resolved under Raw.
    return tuple(asset['Name'] for asset in assets if isinstance(asset, dict)
                 and isinstance(asset.get('Name'), str)
                 and asset['Name'].startswith(('Raw_CardDatabase', 'Raw_ArtCropDatabase'))
                 and Path(asset['Name']).name == asset['Name']
                 and '/' not in asset['Name'] and '\\' not in asset['Name'])


def _manifest_names(path):
    try:
        info = path.stat()
        return _manifest_names_cached(str(path), info.st_mtime_ns, info.st_size)
    except (OSError, ValueError, TypeError):
        return None


def _logged_manifests(downloads, logs):
    """Return roles from the newest readable session that has matching metadata."""
    for log in logs:
        entries = []
        log_data_root = None
        try:
            with Path(log).open(encoding='utf-8', errors='replace') as stream:
                for line in stream:
                    data_path = DATA_PATH_LINE.search(line)
                    if data_path:
                        log_data_root = Path(data_path.group(1)).resolve()
                    match = MANIFEST_LINE.search(line)
                    if match:
                        role, name = match.groups()
                        if Path(name).name != name or '/' in name or '\\' in name:
                            continue
                        manifest = downloads / name
                        names = _manifest_names(manifest)
                        if names and any(name.startswith('Raw_CardDatabase') and name.endswith('.mtga') for name in names):
                            entries.append((role.casefold(), manifest, names))
                        elif names is None and not name.startswith(('Manifest_Audio_', 'Manifest_Localization_')):
                            # A logged General manifest may itself still be
                            # downloading. Do not silently reuse a stale database.
                            entries.append((role.casefold(), manifest, ()))
        except OSError:
            continue
        if log_data_root and log_data_root / 'Downloads' != downloads.resolve():
            continue
        if entries:
            return entries
    return []


def select_card_database(raw_directory, preferred_path=None, log_paths=None):
    raw = Path(raw_directory).resolve()
    logs = arena_log_paths() if log_paths is None else log_paths
    entries = _logged_manifests(raw.parent, logs)
    active = [entry for entry in entries if entry[0] == 'general']
    if active:
        _, manifest, names = active[-1]
        names = [name for name in names if name.startswith('Raw_CardDatabase') and name.endswith('.mtga')]
        if len(names) != 1:
            raise DatabaseSelectionError('Arena\'s active manifest is missing, downloading, or does not '
                                         'identify one card database. Let Arena finish its download, then try again.')
        selected = raw / names[0]
        if not is_card_database(selected):
            raise DatabaseSelectionError(
                'Arena\'s active card database is missing, still downloading, or incompatible. '
                'Let Arena finish its download, then try again.\n' + str(selected))
        return DatabaseSelection(selected, 'Arena General manifest: ' + manifest.name)

    future = {name for role, _, names in entries if role == 'future' for name in names}
    if preferred_path:
        preferred = Path(preferred_path).resolve()
        if preferred.parent == raw and preferred.name not in future and is_card_database(preferred):
            return DatabaseSelection(preferred, 'Saved database; active Arena manifest unavailable')
    candidates = [path for path in sorted(raw.glob('Raw_CardDatabase*.mtga'))
                  if path.name not in future and is_card_database(path)]
    if len(candidates) == 1:
        return DatabaseSelection(candidates[0], 'Only compatible, non-Future card database')
    if not candidates:
        raise DatabaseSelectionError('No compatible current card database is available. '
                                     'Let Arena finish downloading its current assets, then try again.')
    raise DatabaseSelectionError(
        'Multiple card databases exist, but Arena\'s active manifest is unavailable. '
        'Launch Arena once and try again, or select your known working database in Settings. '
        'Swapper will remember that selection.')


def select_crop_database(card_database_path):
    """Resolve crops from the same manifest as the selected card database."""
    card = Path(card_database_path).resolve()
    raw = card.parent
    matches = []
    for manifest in sorted(raw.parent.glob('Manifest_*.mtga')):
        names = _manifest_names(manifest) or ()
        if card.name in names:
            matches.extend(raw / name for name in names
                           if name.startswith('Raw_ArtCropDatabase') and name.endswith('.mtga'))
    candidates = sorted(set(matches))
    valid = [path for path in candidates if _database_has_columns(path, 'Crops', CROP_COLUMNS)]
    if len(candidates) == 1 and len(valid) == 1:
        return valid[0]
    raise DatabaseSelectionError('Could not identify a compatible crop database for the selected '
                                 'card database. Let Arena finish downloading its assets, then try again.')


def require_current_database(card_database_path, identity=None):
    """Reject a stale modal editor before it starts another write operation."""
    path = Path(card_database_path).resolve()
    root = active_data_root()
    if root and root / 'Downloads/Raw' != path.parent:
        raise DatabaseSelectionError('Arena is using a different installation. Close this editor '
                                     'and re-select the asset in the refreshed library.')
    selected = select_card_database(path.parent, preferred_path=path)
    if selected.path != path or (identity is not None and path.stat().st_ino != identity):
        raise DatabaseSelectionError('Arena changed its active database. Close this editor and '
                                     're-select the asset in the refreshed library before applying changes.')
