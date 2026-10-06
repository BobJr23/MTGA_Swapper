"""Shared desktop styling and the preview-first asset workspace.

Bundle/database writes are delegated to the application's existing operations.
Preview images are display-only; replacement images retain their full resolution.
"""

import io
import math
from pathlib import Path

from PIL import Image, ImageOps

BG = "#191c22"
PANEL_BG = "#232831"
SIDEBAR_BG = "#14171c"
PREVIEW_BG = "#101318"
TEXT_PRIMARY = "#eef1f5"
TEXT_SECONDARY = "#a5afbd"
ACCENT = "#477db8"
SUCCESS = "#83bd9e"
ERROR = "#e49a94"
THEME_MODE = "Dark"
DARK_PALETTE = {
    name: globals()[name]
    for name in (
        "BG",
        "PANEL_BG",
        "SIDEBAR_BG",
        "PREVIEW_BG",
        "TEXT_PRIMARY",
        "TEXT_SECONDARY",
        "ACCENT",
        "SUCCESS",
        "ERROR",
    )
}
LIGHT_PALETTE = dict(
    DARK_PALETTE,
    BG="#f1f3f6",
    PANEL_BG="#ffffff",
    SIDEBAR_BG="#e3e8ef",
    PREVIEW_BG="#e9edf2",
    TEXT_PRIMARY="#202936",
    TEXT_SECONDARY="#526174",
    SUCCESS="#28734f",
    ERROR="#a63832",
)


def theme_palette(mode):
    return dict(LIGHT_PALETTE if mode == "Light" else DARK_PALETTE)


FONT_NORMAL = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_HEADER = ("Segoe UI", 15, "bold")
BUTTON_SIZE = (19, 1)
SECTION_PADDING = (10, 8)
PREVIEW_SIZE = (310, 165)
CATEGORIES = (
    "Cards",
    "Basic Lands",
    "Card Sleeves",
    "Avatars",
    "Emotes",
    "Pets",
    "Other Assets",
)
LAND_NAMES = {
    "island",
    "forest",
    "mountain",
    "plains",
    "swamp",
    "wastes",
    "snowcoveredforest",
    "snowcoveredisland",
    "snowcoveredmountain",
    "snowcoveredplains",
    "snowcoveredswamp",
}


def configure_theme(mode="Dark"):
    import FreeSimpleGUI as sg

    global THEME_MODE
    THEME_MODE = mode if mode in ("Light", "Dark") else "Dark"
    globals().update(theme_palette(THEME_MODE))

    sg.theme_add_new(
        "MTGA Studio",
        {
            "BACKGROUND": BG,
            "TEXT": TEXT_PRIMARY,
            "INPUT": PREVIEW_BG,
            "TEXT_INPUT": TEXT_PRIMARY,
            "SCROLL": PANEL_BG,
            "BUTTON": (TEXT_PRIMARY, PANEL_BG),
            "PROGRESS": (ACCENT, PREVIEW_BG),
            "BORDER": 1,
            "SLIDER_DEPTH": 0,
            "PROGRESS_DEPTH": 0,
        },
    )
    sg.theme("MTGA Studio")
    sg.set_options(
        font=FONT_NORMAL,
        element_padding=(5, 3),
        button_element_size=BUTTON_SIZE,
        text_element_background_color=PANEL_BG,
        border_width=1,
    )


def button(text, key, primary=False, **kwargs):
    import FreeSimpleGUI as sg

    return sg.Button(
        text,
        key=key,
        border_width=1,
        button_color=(
            "#ffffff" if primary else TEXT_PRIMARY,
            ACCENT if primary else PANEL_BG,
        ),
        **kwargs,
    )


def section_title(text):
    import FreeSimpleGUI as sg

    return sg.Text(text, font=("Segoe UI", 11, "bold"), pad=(5, 8))


def panel(layout, **kwargs):
    import FreeSimpleGUI as sg

    return sg.Column(
        layout,
        background_color=PANEL_BG,
        pad=SECTION_PADDING,
        vertical_alignment="top",
        **kwargs,
    )


def preview_bytes(image=None, size=PREVIEW_SIZE):
    if isinstance(image, bytes):
        with Image.open(io.BytesIO(image)) as decoded:
            image = decoded.copy()
    canvas = Image.new("RGB", size, PREVIEW_BG)
    if image is not None:
        fitted = image.convert("RGBA")
        fitted.thumbnail(size, Image.Resampling.LANCZOS)
        position = ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2)
        canvas.paste(fitted, position, fitted)
    output = io.BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue()


def filter_cards(cards, category="Cards", query="", sort="Name", deck=None):
    from src.card_models import sort_cards_by_attribute

    query = query.replace(" ", "").casefold()
    result = [
        card
        for card in cards
        if len(card.split()) == 5
        and (category != "Basic Lands" or card.split()[0].casefold() in LAND_NAMES)
        and (deck is None or card[:15].strip() in deck or card.split()[0] in deck)
        and query in card.replace(" ", "").casefold()
    ]
    return sort_cards_by_attribute(result, sort)


class Replacement:
    def __init__(self):
        self.clear()

    def clear(self):
        self.path = None
        self.image = None

    def choose(self, path):
        with Image.open(path) as image:
            staged = ImageOps.exif_transpose(image).copy()
        self.image = staged
        self.path = Path(path)

    def process(self, remove_alpha=False, ratio=None):
        if self.image is None:
            raise ValueError("Choose a replacement image first.")
        if ratio is not None:
            if not all(math.isfinite(v) and v > 0 for v in ratio):
                raise ValueError("Enter positive width and height values.")
            width, height = self.image.size
            target = ratio[0] / ratio[1]
            size = (
                (max(1, round(height * target)), height)
                if width / height > target
                else (width, max(1, round(width / target)))
            )
            self.image = ImageOps.fit(self.image, size, method=Image.Resampling.LANCZOS)
        if remove_alpha:
            self.image = self.image.convert("RGB")


def main_layout(cards, database, output, version, upscaling):
    import FreeSimpleGUI as sg

    sidebar = [
        [
            sg.Text(
                "MTGA Swapper",
                font=("Segoe UI", 13, "bold"),
                background_color=SIDEBAR_BG,
            )
        ],
        [
            sg.Text(
                "Asset customization",
                text_color=TEXT_SECONDARY,
                background_color=SIDEBAR_BG,
            )
        ],
        [
            sg.Text(
                "Library",
                text_color=TEXT_SECONDARY,
                pad=(5, 12),
                background_color=SIDEBAR_BG,
            )
        ],
        *[
            [
                button(
                    category,
                    "-NAV-" + category,
                    size=(17, 1),
                    primary=category == "Cards",
                )
            ]
            for category in CATEGORIES
        ],
        [
            sg.Text(
                "Tools",
                text_color=TEXT_SECONDARY,
                pad=(5, 12),
                background_color=SIDEBAR_BG,
            )
        ],
        [button("Edit art crops", "-CROP_EDITOR-", size=(22, 1))],
        [button("Edit card frames / colors", "-THEME_EDITOR-", size=(22, 1))],
        [button("Inspect assets by role", "-ROLE_BROWSER-", size=(22, 1))],
        [
            button(
                "Swap entire sets", "-SET_SWAPPER-", size=(22, 1), disabled=not database
            )
        ],
        [sg.Text("", background_color=SIDEBAR_BG)],
        [button("Settings", "-SETTINGS-", size=(17, 1))],
        [button("Presets and share packs", "-MAINTENANCE-", size=(22, 1))],
        [button("Search token art", "-SEARCH_TOKENS-", size=(22, 1))],
        [button("Export game fonts", "-EXPORT_FONTS-", size=(22, 1))],
        [button("Discord Server", "-JOIN_DISCORD-", size=(17, 1))],
        [
            sg.Text(
                version or "Development",
                font=FONT_SMALL,
                text_color=TEXT_SECONDARY,
                background_color=SIDEBAR_BG,
                pad=(5, 12),
            )
        ],
    ]
    library = [
        [
            sg.Text("Cards", key="-LIBRARY_TITLE-", font=FONT_HEADER),
            sg.Text("", key="-LIBRARY_COUNT-", text_color=TEXT_SECONDARY),
        ],
        [
            sg.Text("Search"),
            sg.Input(
                key="-SEARCH_INPUT-",
                enable_events=True,
                size=(35, 1),
                expand_x=True,
                tooltip="Search name, set, art type, group ID, art ID or asset path",
            ),
        ],
        [
            sg.Text("Sort"),
            sg.Combo(
                ["Name", "Set", "ArtType", "GrpID", "ArtID"],
                default_value="Name",
                readonly=True,
                key="-SORT_BY-",
                enable_events=True,
                size=(10, 1),
            ),
            sg.Checkbox("Use decklist", key="-USE_DECKLIST-", enable_events=True),
        ],
        [
            sg.Text(
                f"{'Name':<30} {'Set':<10} {'Type':<9} {'Group':<8} {'Art':<8}",
                font=("Consolas", 9),
                text_color=TEXT_SECONDARY,
                key="-CARD_HEADINGS-",
            )
        ],
        [
            sg.pin(
                sg.Listbox(
                    cards,
                    size=(71, 20),
                    font=("Consolas", 9),
                    key="-CARD_LIST-",
                    enable_events=True,
                    expand_x=True,
                    expand_y=True,
                )
            )
        ],
        [
            sg.pin(
                sg.Listbox(
                    [],
                    size=(61, 20),
                    key="-WORKSPACE_ASSETS-",
                    enable_events=True,
                    visible=False,
                    expand_x=True,
                    expand_y=True,
                )
            )
        ],
        [
            sg.Text(
                "Select an asset to preview it.",
                key="-LIBRARY_HINT-",
                text_color=TEXT_SECONDARY,
                size=(62, 2),
            )
        ],
        [
            button("Load decklist", "-LOAD_DECKLIST-"),
            button("Browse texture gallery", "-CHANGE_ASSETS-", disabled=not database),
        ],
        [button("Swap two card arts", "-SWAP_ARTS-")],
        [
            sg.pin(
                sg.Column(
                    [
                        [section_title("Actions for this list")],
                        [
                            sg.Text(
                                "Applies to the cards currently shown above.",
                                text_color=TEXT_SECONDARY,
                            )
                        ],
                        [
                            button(
                                "Unlock parallax", "-UNLOCK_PARALLAX-", size=(25, 1)
                            ),
                            button(
                                "Export listed card art",
                                "-EXPORT_ALL_ARTS-",
                                size=(25, 1),
                            ),
                        ],
                        [
                            button(
                                "Back up listed changes",
                                "-LOAD_OLD_CHANGES-",
                                size=(25, 1),
                            ),
                            button(
                                "Recover backup art",
                                "-RECOVER_BACKUP_ART-",
                                size=(25, 1),
                            ),
                        ],
                    ],
                    key="-LIST_ACTIONS-",
                    background_color=PANEL_BG,
                    pad=(0, 0),
                )
            )
        ],
    ]
    inspector = [
        [section_title("Current asset")],
        [sg.Image(data=preview_bytes(), key="-ORIGINAL_PREVIEW-")],
        [
            sg.Text(
                "Select an asset from the library to begin.",
                key="-TARGET_NAME-",
                size=(43, 1),
            )
        ],
        [
            sg.Text(
                "",
                key="-TARGET_META-",
                size=(43, 2),
                font=FONT_SMALL,
                text_color=TEXT_SECONDARY,
            )
        ],
        [section_title("Replacement")],
        [sg.Image(data=preview_bytes(), key="-REPLACEMENT_PREVIEW-")],
        [
            sg.Text(
                "Choose an image to preview your replacement.",
                key="-REPLACEMENT_NAME-",
                size=(43, 2),
                text_color=TEXT_SECONDARY,
            )
        ],
        [
            button("Choose image", "-CHOOSE_REPLACEMENT-", size=(18, 1)),
            button("Clear", "-CLEAR_REPLACEMENT-", size=(10, 1)),
        ],
        [
            button("Process Replacement", "-TOGGLE_PROCESSING-", size=(23, 1)),
            button(
                "Detailed editor", "-OPEN_CARD_EDITOR-", size=(15, 1), disabled=True
            ),
        ],
        [
            sg.pin(
                sg.Column(
                    [
                        [
                            sg.Checkbox(
                                "Remove alpha", key="-STAGE_ALPHA-", default=False
                            )
                        ],
                        [
                            sg.Text("Crop ratio"),
                            sg.Input("11", key="-STAGE_WIDTH-", size=(4, 1)),
                            sg.Text(":"),
                            sg.Input("8", key="-STAGE_HEIGHT-", size=(4, 1)),
                            button("Crop", "-STAGE_CROP-", size=(8, 1)),
                        ],
                        [
                            button(
                                "Apply alpha option", "-STAGE_PROCESS-", size=(20, 1)
                            ),
                            button(
                                "Upscale",
                                "-STAGE_UPSCALE-",
                                size=(12, 1),
                                disabled=not upscaling,
                            ),
                        ],
                    ],
                    key="-PROCESSING_PANEL-",
                    visible=False,
                    pad=(0, 0),
                )
            )
        ],
        [
            button(
                "Apply Card Swap",
                "-APPLY_REPLACEMENT-",
                primary=True,
                size=(39, 1),
                disabled=True,
            )
        ],
    ]
    settings = [
        [sg.Text("Settings", font=FONT_HEADER)],
        [section_title("Appearance")],
        [
            sg.Text("Application theme"),
            sg.Combo(
                ["Dark", "Light"],
                default_value=THEME_MODE,
                readonly=True,
                enable_events=True,
                key="-APP_THEME-",
                size=(12, 1),
            ),
        ],
        [
            sg.Text(
                "Theme changes take effect next time you open the app.",
                text_color=TEXT_SECONDARY,
            )
        ],
        [section_title("MTGA database")],
        [
            sg.Input(
                database or "Not selected",
                readonly=True,
                key="DATABASE_DISPLAY",
                size=(65, 1),
            )
        ],
        [button("Choose database", "-SELECT_DATABASE-")],
        [section_title("Image export folder")],
        [
            sg.Input(
                output or "Not selected",
                readonly=True,
                key="IMAGE_SAVE_DISPLAY",
                size=(65, 1),
            )
        ],
        [button("Choose output folder", "-SELECT_OUTPUT_FOLDER-")],
        [section_title("Image processing")],
        [
            sg.Text(
                (
                    "Upscaling available"
                    if upscaling
                    else "Upscaling unavailable in this build"
                ),
                text_color=TEXT_SECONDARY,
            )
        ],
        [
            sg.Text(
                "Updates are checked automatically at launch.",
                text_color=TEXT_SECONDARY,
            )
        ],
        [button("Open backup folder", "-OPEN_BACKUPS-")],
        [button("Back to library", "-BACK_LIBRARY-")],
    ]
    maintenance = [
        [sg.Text("Presets and share packs", font=FONT_HEADER)],
        [
            sg.Text(
                "Presets store database changes. Share packs also include custom card images.",
                text_color=TEXT_SECONDARY,
                size=(74, 2),
            )
        ],
        [section_title("Import")],
        [
            button("Load changes preset", "-LOAD_PRESET-", size=(25, 1)),
            button("Import share pack", "-IMPORT_SHARE_PACK-", size=(25, 1)),
        ],
        [section_title("Export")],
        [
            button("Export changes preset", "-EXPORT_PRESET-", size=(25, 1)),
            button("Export share pack", "-EXPORT_SHARE_PACK-", size=(25, 1)),
        ],
        [button("Back to library", "-BACK_MAINTENANCE-")],
    ]
    return [
        [
            sg.Column(
                sidebar,
                background_color=SIDEBAR_BG,
                vertical_alignment="top",
                pad=(10, 10),
                scrollable=True,
                vertical_scroll_only=True,
                size_subsample_height=1,
                key="-SIDEBAR_SCROLL-",
                expand_y=True,
            ),
            sg.Column(
                [
                    [
                        sg.pin(
                            sg.Column(
                                [
                                    [
                                        panel(library, expand_x=True, expand_y=True),
                                        panel(inspector),
                                    ]
                                ],
                                key="-WORKSPACE-",
                                pad=(0, 0),
                                expand_x=True,
                                expand_y=True,
                            )
                        )
                    ],
                    [
                        sg.pin(
                            panel(
                                settings,
                                key="-SETTINGS_PANEL-",
                                visible=False,
                                expand_x=True,
                            )
                        )
                    ],
                    [
                        sg.pin(
                            panel(
                                maintenance,
                                key="-MAINTENANCE_PANEL-",
                                visible=False,
                                expand_x=True,
                            )
                        )
                    ],
                    [
                        sg.Text(
                            "Ready — select an asset to begin.",
                            key="-WORKSPACE_STATUS-",
                            size=(95, 1),
                            expand_x=True,
                        )
                    ],
                    [
                        sg.ProgressBar(
                            100,
                            key="-WORKSPACE_PROGRESS-",
                            orientation="h",
                            size=(50, 4),
                            expand_x=True,
                        )
                    ],
                    [button("Show details", "-TOGGLE_LOG-", size=(15, 1))],
                    [
                        sg.pin(
                            sg.Multiline(
                                "",
                                key="-WORKSPACE_LOG-",
                                size=(95, 5),
                                disabled=True,
                                visible=False,
                                expand_x=True,
                            )
                        )
                    ],
                ],
                vertical_alignment="top",
                pad=(0, 0),
                expand_x=True,
                expand_y=True,
                scrollable=True,
                vertical_scroll_only=True,
                size_subsample_height=1,
                key="-CONTENT_SCROLL-",
            ),
        ]
    ]


class Workspace:
    """Presentation state; callbacks reuse existing loading and saving functions."""

    def __init__(
        self, window, context, load_card, apply_card, upscale=None, apply_asset=None
    ):
        self.window = window
        self.context = context
        self.load_card = load_card
        self.apply_card = apply_card
        self.apply_asset = apply_asset
        self.upscale = upscale
        self.category = "Cards"
        self.catalog = None
        self.catalog_database = None
        self.records = []
        self.target = None
        self.original = None
        self.replacement = Replacement()
        self.log = []
        self.refresh({})

    def status(self, message, error=False, progress=0):
        self.window["-WORKSPACE_STATUS-"].update(
            message, text_color=ERROR if error else TEXT_PRIMARY
        )
        self.window["-WORKSPACE_PROGRESS-"].update(progress)
        self.log = (self.log + [message])[-100:]
        self.window["-WORKSPACE_LOG-"].update("\n".join(self.log))
        self.window.refresh()

    def clear_target(self):
        self.target = self.original = None
        self.replacement.clear()
        self.window["-ORIGINAL_PREVIEW-"].update(data=preview_bytes())
        self.window["-TARGET_NAME-"].update(
            "Select an asset from the library to begin."
        )
        self.window["-TARGET_META-"].update("")
        self.window["-OPEN_CARD_EDITOR-"].update(disabled=True)
        self.paint_replacement()

    def paint_replacement(self):
        self.window["-REPLACEMENT_PREVIEW-"].update(
            data=preview_bytes(self.replacement.image)
        )
        path = self.replacement.path
        image = self.replacement.image
        self.window["-REPLACEMENT_NAME-"].update(
            f"{path.name}\n{image.width} × {image.height}"
            if path and image
            else "Choose an image to preview your replacement."
        )
        self.window["-REPLACEMENT_NAME-"].set_tooltip(str(path) if path else "")
        self.window["-APPLY_REPLACEMENT-"].update(
            disabled=self.target is None or image is None
        )

    def refresh(self, values):
        context = self.context()
        cards_mode = self.category in ("Cards", "Basic Lands")
        self.window["-CARD_LIST-"].update(visible=cards_mode)
        self.window["-CARD_HEADINGS-"].update(visible=cards_mode)
        self.window["-LIST_ACTIONS-"].update(visible=cards_mode)
        self.window["-WORKSPACE_ASSETS-"].update(visible=not cards_mode)
        self.window["-SORT_BY-"].update(disabled=not cards_mode)
        self.window["-USE_DECKLIST-"].update(disabled=not cards_mode)
        self.window["-LIBRARY_TITLE-"].update(self.category)
        if cards_mode:
            deck = context["deck"] if values.get("-USE_DECKLIST-", False) else None
            if values.get("-USE_DECKLIST-") and deck is None:
                self.window["-USE_DECKLIST-"].update(False)
                self.status("Load a decklist before enabling its filter.", error=True)
            shown = filter_cards(
                context["cards"],
                self.category,
                values.get("-SEARCH_INPUT-", ""),
                values.get("-SORT_BY-", "Name"),
                deck,
            )
            context["set_filtered"](shown)
            self.window["-CARD_LIST-"].update(shown)
            count = len(shown)
        else:
            database = context["database"]
            if database != self.catalog_database:
                self.catalog = None
                self.catalog_database = database
            if database and self.catalog is None:
                from src.visual_tools_ui import catalog_for_database

                self.status("Loading MTGA asset library…", progress=20)
                self.catalog = catalog_for_database(database)
            query = values.get("-SEARCH_INPUT-", "").casefold().strip()
            role = {"Card Sleeves": "Sleeve", "Avatars": "Avatar"}.get(self.category)
            records = self.catalog.records if self.catalog else []
            self.records = [
                record
                for record in records
                if (not role or record.role == role)
                and (
                    self.category not in ("Emotes", "Pets")
                    or self.category[:-1].casefold()
                    in (record.path + record.bundle).casefold()
                )
                and query in (record.path + " " + record.bundle).casefold()
            ]
            count = len(self.records)
            self.records = self.records[:2000]
            self.window["-WORKSPACE_ASSETS-"].update(
                [
                    f"{Path(record.path).stem}  [{record.role}]"
                    for record in self.records
                ]
            )
        self.window["-LIBRARY_COUNT-"].update(f"{count:,} assets")
        hint = (
            "Select an asset to preview it."
            if count
            else "No assets match. Clear your search or choose an MTGA database in Settings."
        )
        if not cards_mode and count > 2000:
            hint = "Showing the first 2,000 matches. Narrow your search to see more."
        self.window["-LIBRARY_HINT-"].update(hint)

    def handle(self, event, values):
        import FreeSimpleGUI as sg

        handled = event.startswith("-NAV-") if isinstance(event, str) else False
        handled = handled or event in (
            "-APP_THEME-",
            "-SETTINGS-",
            "-MAINTENANCE-",
            "-BACK_LIBRARY-",
            "-BACK_MAINTENANCE-",
            "-TOGGLE_LOG-",
            "-TOGGLE_PROCESSING-",
            "-SEARCH_INPUT-",
            "-SORT_BY-",
            "-USE_DECKLIST-",
            "-CARD_LIST-",
            "-WORKSPACE_ASSETS-",
            "-CHOOSE_REPLACEMENT-",
            "-CLEAR_REPLACEMENT-",
            "-STAGE_CROP-",
            "-STAGE_PROCESS-",
            "-STAGE_UPSCALE-",
            "-APPLY_REPLACEMENT-",
        )
        if not handled:
            return False
        try:
            if event in (
                "-SETTINGS-",
                "-MAINTENANCE-",
                "-BACK_LIBRARY-",
                "-BACK_MAINTENANCE-",
            ) or event.startswith("-NAV-"):
                self.window["-WORKSPACE-"].update(
                    visible=event not in ("-SETTINGS-", "-MAINTENANCE-")
                )
                self.window["-SETTINGS_PANEL-"].update(visible=event == "-SETTINGS-")
                self.window["-MAINTENANCE_PANEL-"].update(
                    visible=event == "-MAINTENANCE-"
                )
            if event == "-APP_THEME-":
                self.context()["save_theme"](values["-APP_THEME-"])
                self.status(
                    "Appearance saved. Your theme will apply next time you open the app."
                )
            elif event.startswith("-NAV-"):
                self.category = event[5:]
                for category in CATEGORIES:
                    self.window["-NAV-" + category].update(
                        button_color=(
                            "#ffffff" if category == self.category else TEXT_PRIMARY,
                            ACCENT if category == self.category else PANEL_BG,
                        )
                    )
                self.clear_target()
                self.window["-APPLY_REPLACEMENT-"].update(
                    "Apply "
                    + {
                        "Cards": "Card",
                        "Basic Lands": "Land",
                        "Card Sleeves": "Sleeve",
                    }.get(self.category, self.category.rstrip("s"))
                    + " Swap"
                )
                self.refresh(values)
                self.status("Ready — select an asset to begin.")
            elif event in ("-SEARCH_INPUT-", "-SORT_BY-", "-USE_DECKLIST-"):
                self.clear_target()
                self.refresh(values)
            elif event in ("-TOGGLE_LOG-", "-TOGGLE_PROCESSING-"):
                key = (
                    "-WORKSPACE_LOG-"
                    if event == "-TOGGLE_LOG-"
                    else "-PROCESSING_PANEL-"
                )
                self.window[key].update(visible=not self.window[key].visible)
            elif event in ("-CARD_LIST-", "-WORKSPACE_ASSETS-") and values.get(event):
                self.clear_target()
                self.status("Loading asset preview…", progress=20)
                if event == "-CARD_LIST-":
                    self.target, self.original = self.load_card(values[event][0])
                    card = self.target["card"]
                    name, metadata = (
                        card.name,
                        f"{card.set_code}  |  Group {card.grp_id}  |  Art {card.art_id}",
                    )
                    self.window["-OPEN_CARD_EDITOR-"].update(disabled=False)
                else:
                    from src.asset_catalog import load_object, object_image

                    record = self.records[self.window[event].get_indexes()[0]]
                    self.window["-TARGET_NAME-"].update(Path(record.path).name)
                    self.window["-TARGET_META-"].update(record.role)
                    environment, reader = load_object(record)
                    self.original = object_image(reader)
                    name, metadata = Path(record.path).name, record.role
                    self.target = {
                        "record": record,
                        "environment": environment,
                        "reader": reader,
                        "bundle_original": record.file.read_bytes(),
                    }
                    if reader.type.name != "Texture2D":
                        self.target = None
                        metadata += " — inspect atlas sprites in Browse by role"
                self.window["-ORIGINAL_PREVIEW-"].update(
                    data=preview_bytes(self.original)
                )
                self.window["-TARGET_NAME-"].update(name)
                self.window["-TARGET_META-"].update(
                    metadata + f"\n{self.original.width} × {self.original.height}"
                )
                self.status(
                    (
                        "Choose a replacement image."
                        if self.target
                        else "This asset is available for preview only."
                    ),
                    progress=100,
                )
            elif event == "-CHOOSE_REPLACEMENT-":
                file = sg.popup_get_file(
                    "Choose replacement image",
                    file_types=(("Images", "*.png;*.jpg;*.jpeg;*.tga;*.bmp;*.webp"),),
                )
                if file:
                    self.replacement.choose(file)
                    self.paint_replacement()
                    self.status(
                        "Replacement ready. Review the preview, then apply the swap."
                    )
            elif event == "-CLEAR_REPLACEMENT-":
                self.replacement.clear()
                self.paint_replacement()
                self.status("Replacement cleared.")
            elif event in ("-STAGE_CROP-", "-STAGE_PROCESS-", "-STAGE_UPSCALE-"):
                self.status("Processing replacement image…", progress=30)
                ratio = (
                    (float(values["-STAGE_WIDTH-"]), float(values["-STAGE_HEIGHT-"]))
                    if event == "-STAGE_CROP-"
                    else None
                )
                self.replacement.process(values.get("-STAGE_ALPHA-", False), ratio)
                if event == "-STAGE_UPSCALE-":
                    if self.upscale is None:
                        raise ValueError("Upscaling is unavailable in this build.")
                    image = self.replacement.image
                    stream = io.BytesIO()
                    image.save(stream, format="PNG")
                    stream.seek(0)
                    self.replacement.image = self.upscale(
                        stream, image.width, image.height
                    )
                self.paint_replacement()
                self.status(
                    "Processing complete. Review the replacement preview.", progress=100
                )
            elif event == "-APPLY_REPLACEMENT-":
                if self.target is None or self.replacement.image is None:
                    raise ValueError(
                        "Select an asset and choose a replacement image first."
                    )
                self.status("Replacing asset…", progress=35)
                if "card" in self.target:
                    self.apply_card(self.target, self.replacement.image)
                else:
                    if self.apply_asset is None:
                        raise ValueError("The asset writer is unavailable.")
                    self.apply_asset(self.target, self.replacement.image)
                    record = self.target["record"]
                    # Release serialized state: another write must reload the saved bundle.
                    from src.asset_catalog import load_object

                    self.target["environment"], self.target["reader"] = load_object(
                        record
                    )
                    self.target["bundle_original"] = record.file.read_bytes()
                self.original = self.replacement.image.copy()
                self.window["-ORIGINAL_PREVIEW-"].update(
                    data=preview_bytes(self.original)
                )
                self.window["-TARGET_META-"].update(
                    f"Applied replacement  |  {self.original.width} × {self.original.height}"
                )
                self.replacement.clear()
                self.paint_replacement()
                self.status(
                    "Swap completed successfully. Restart Arena to load the changed asset.",
                    progress=100,
                )
        except Exception as error:
            if event == "-APPLY_REPLACEMENT-":
                # A failed serializer/save may have changed in-memory objects.
                # Reload the selected asset before allowing another write.
                self.target = None
                self.window["-APPLY_REPLACEMENT-"].update(disabled=True)
                self.window["-OPEN_CARD_EDITOR-"].update(disabled=True)
            self.status(str(error), error=True)
        self.window.refresh()
        self.window["-CONTENT_SCROLL-"].contents_changed()
        return True


def card_editor_layout(data, multiple, alternates, art_type, upscaling):
    """Keep the editor's original keys while giving actions distinct sections."""
    import FreeSimpleGUI as sg

    preview = [
        [section_title("Current card art")],
        [sg.Image(data=preview_bytes(data, (620, 470)), key="-CARD_IMAGE-")],
        [
            sg.Text(
                "Changes made here use the existing detailed editor workflow.",
                text_color=TEXT_SECONDARY,
            )
        ],
    ]
    controls = [
        [section_title("Replace and export")],
        [
            button(
                "Choose and apply image", "-CHANGE_IMAGE-", primary=True, size=(26, 1)
            )
        ],
        [button("Export image", "-SAVE_IMAGE-", size=(26, 1))],
        [section_title("Texture and alternate art")],
        [
            button("Previous", "-PREVIOUS-", visible=multiple, size=(12, 1)),
            button("Next", "-NEXT-", visible=multiple, size=(12, 1)),
        ],
        [
            sg.Combo(
                alternates,
                default_value=alternates[0] if alternates else "",
                key="-SEARCH_ALTERNATES-",
                readonly=True,
                enable_events=True,
                size=(28, 1),
            )
        ],
        [section_title("Image processing")],
        [
            sg.Checkbox(
                "Remove alpha", key="-REMOVE_ALPHA-", default=True, enable_events=True
            )
        ],
        [
            sg.Text("Aspect ratio"),
            sg.Input(
                "3" if art_type == "1" else "11", key="-ASPECT_WIDTH-", size=(4, 1)
            ),
            sg.Text(":"),
            sg.Input(
                "4" if art_type == "1" else "8", key="-ASPECT_HEIGHT-", size=(4, 1)
            ),
        ],
        [button("Set aspect ratio", "-SET_ASPECT_RATIO-", size=(26, 1))],
        [
            button(
                "Upscale image", "-UPSCALE_IMAGE-", disabled=not upscaling, size=(26, 1)
            )
        ],
        [section_title("Card styles and metadata")],
        [button("Adjust style tags", "-ADJUST_STYLE_TAGS-", size=(26, 1))],
        [button("Edit details", "-EDIT_DETAILS-", size=(26, 1))],
        [section_title("Swap two card arts")],
        [
            button("Set to Swap 1", "-SET_SWAP_1-", size=(12, 1)),
            button("Set to Swap 2", "-SET_SWAP_2-", size=(12, 1)),
        ],
        [button("Close editor", "-EXIT-", size=(26, 1))],
    ]
    return [[panel(preview), panel(controls)]]


def asset_editor_layout(data, multiple, information):
    import FreeSimpleGUI as sg

    return [
        [
            panel(
                [
                    [section_title("Current texture")],
                    [
                        sg.Image(
                            data=preview_bytes(data, (620, 470)), key="-ASSET_IMAGE-"
                        )
                    ],
                    [
                        sg.Text(
                            information,
                            key="-ASSET_INFO-",
                            size=(75, 2),
                            text_color=TEXT_SECONDARY,
                        )
                    ],
                ]
            ),
            panel(
                [
                    [section_title("Replace and export")],
                    [
                        button(
                            "Choose and apply image",
                            "-CHANGE_ASSET_IMAGE-",
                            primary=True,
                            size=(26, 1),
                        )
                    ],
                    [button("Export image", "-SAVE_ASSET-", size=(26, 1))],
                    [section_title("Texture navigation")],
                    [
                        button(
                            "Previous",
                            "-ASSET_PREVIOUS-",
                            visible=multiple,
                            size=(12, 1),
                        ),
                        button("Next", "-ASSET_NEXT-", visible=multiple, size=(12, 1)),
                    ],
                    [section_title("Image processing")],
                    [
                        sg.Checkbox(
                            "Remove alpha",
                            key="-ASSET_REMOVE_ALPHA-",
                            default=True,
                            enable_events=True,
                        )
                    ],
                    [
                        sg.Text("Aspect ratio"),
                        sg.Input("11", key="-ASPECT_WIDTH-", size=(4, 1)),
                        sg.Text(":"),
                        sg.Input("8", key="-ASPECT_HEIGHT-", size=(4, 1)),
                    ],
                    [button("Set aspect ratio", "-SET_ASPECT_RATIO-", size=(26, 1))],
                    [button("Return to gallery", "-RETURN_GALLERY-", size=(26, 1))],
                ]
            ),
        ]
    ]
