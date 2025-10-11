# MTGA Swapper - A tool for swapping Magic: The Gathering Arena card arts
# Main application module containing the GUI and core functionality
# fmt: off
from pathlib import Path
from src.upscaler import is_upscaling_available, get_resource_path

user_config_directory = Path.home() / ".mtga_swapper"
user_config_directory.mkdir(exist_ok=True)
user_config_file_path = user_config_directory / "config.json"
user_save_changes_path = user_config_directory / "changes.json"
update_path = user_config_directory / "update.json"

# Create default config file if it doesn't exist
if not user_config_file_path.exists():
    with open(get_resource_path("config.json"), "r") as source_config:
        with open(user_config_file_path, "w") as destination_config:
            destination_config.write(source_config.read())

if not user_save_changes_path.exists():
    with open(get_resource_path("changes.json"), "r") as source_config:
        with open(user_save_changes_path, "w") as destination_config:
            destination_config.write(source_config.read())

with open(get_resource_path("update.json"), "r") as source_config:
    with open(update_path, "w") as destination_config:
        destination_config.write(source_config.read())

from src.updater import main as check_for_updates
check_for_updates(update_path)
import src.sql_editor as database_manager
from random import randint
from src.sql_editor import (
    save_grp_id_info,
    change_grp_id,
    fetch_all_data,
    save_loc_id_info,
    json,
    find_mtga_db_path
)

# Import upscaling functionality only if dependencies are available
if is_upscaling_available:
    from src.upscaler import upscale_card_image

from src.decklist import create_decklist_import_window, create_search_tokens_window
from src.card_models import MTGACard, format_card_display, sort_cards_by_attribute
from src.gui_utils import (
    open_file_dialog,
    open_directory_dialog,
    convert_pil_image_to_bytes,
)
from src.set_swapper import create_set_swap_window, generate_swap_file, perform_set_swap, spiderman_localizations
import sys
import io
from src.image_utils import (
    remove_alpha_channel,
    resize_image_to_screen,
    adjust_image_aspect_ratio,
    resize_image_for_gallery,
)
from src.unity_bundle import (
    load_unity_bundle,
    extract_fonts,
    get_card_texture_data,
    convert_texture_to_bytes,
    save_image_to_file,
    extract_textures_from_bundle,
    replace_texture_in_bundle,
    configure_unity_version,
    export_3d_meshes,
)

import FreeSimpleGUI as sg
from tkinter import Tk
from tkinter.filedialog import askopenfilename, askdirectory
from PIL import Image
import os
import io
from typing import Dict, Any, Optional, List, Union, Tuple


# Set GUI theme for dark appearance
sg.theme("DarkBlue3")


# Initialize configuration directory and file


# Initialize variables for database connection
database_cursor = None
database_connection = None
database_file_path = None
all_cards_formatted = ["Select a database first"]
displayed_cards = ["Select a database first"]
image_save_directory = None
is_alternate = False
database_file_path = find_mtga_db_path()
# Load configuration from file or initialize with defaults
if (
    database_file_path or sg.popup_yes_no(
        "Do you want to load from config file?",
        title="Load Config",
    )
    == "Yes"
):
    # Load existing configuration
    with open(user_config_file_path, "r") as config_file:
        try:
            user_config = sg.json.loads(config_file.read())
        except sg.json.JSONDecodeError:
            sg.popup_error("Error loading config file", auto_close_duration=3)
            user_config = {"SavePath": "", "DatabasePath": ""}
        image_save_directory = (
            user_config["SavePath"] if user_config["SavePath"] else None
        )

        # Validate and load database if path exists
        if database_file_path or user_config["DatabasePath"] != "" and os.path.exists(
            user_config["DatabasePath"]
        ):
            if not database_file_path:
                database_file_path = user_config["DatabasePath"]
            try:
                # Initialize database connection
                database_cursor, database_connection, database_file_path = (
                    database_manager.create_database_connection(database_file_path)
                )

                # Query all cards from database with proper formatting
                all_cards_formatted = list(
                    map(
                        format_card_display,
                        sorted(
                            database_cursor.execute(
                                """
                                    SELECT 
                                        CASE 
                                            WHEN NULLIF(c1.Order_Title, '') IS NOT NULL THEN c1.Order_Title
                                            WHEN NULLIF(c1.Order_Title, '') IS NULL 
                                                AND NULLIF(c2.Order_Title, '') IS NOT NULL THEN c2.Order_Title || '-flip-side'
                                        END AS Order_Title,
                                        c1.ExpansionCode,
                                        c1.ArtSize,
                                        c1.GrpId,
                                        c1.ArtId
                                    FROM Cards c1
                                    LEFT JOIN Cards c2
                                        ON c1.LinkedFaceGrpIds = c2.GrpId
                                    AND NULLIF(c2.Order_Title, '') IS NOT NULL
                                    WHERE NULLIF(c1.Order_Title, '') IS NOT NULL
                                    OR NULLIF(c2.Order_Title, '') IS NOT NULL;
                                """
                            ).fetchall()
                        ),
                    )
                )
            except (
                database_manager.sqlite3.OperationalError,
                database_manager.sqlite3.DatabaseError,
                TypeError,
            ):
                sg.popup_error(
                    "Missing or incorrect database selected", auto_close_duration=3
                )
                database_file_path = None
                all_cards_formatted = ["Select a database first"]

            displayed_cards = all_cards_formatted
            filtered_search_results = displayed_cards
            if not image_save_directory:
                image_save_directory = sg.popup_get_folder("Select Image Save Folder")
            asset_bundle_directory = (
                os.path.dirname(database_file_path)[0:-3] + "AssetBundle"
            )
            configure_unity_version(database_file_path, "2022.3.42f1")
            if image_save_directory and database_file_path:
                with open(user_config_file_path, "w") as config_file:
                    user_config["SavePath"] = str(Path(image_save_directory).as_posix())
                    user_config["DatabasePath"] = str(Path(database_file_path).as_posix())
                    config_file.write(sg.json.dumps(user_config, indent=4))
        else:
            database_file_path = None
            all_cards_formatted = ["Select a database first"]
            displayed_cards = ["Select a database first"]
            sg.popup_error(
                "Invalid or missing database file. Please select a valid .mtga file.",
                auto_close_duration=3,
            )
            
else:
    # Initialize with empty configuration
    user_config = {"SavePath": None, "DatabasePath": None}
    image_save_directory = None
    database_file_path = None
    all_cards_formatted = ["Select a database first"]
    displayed_cards = ["Select a database first"]

# Initialize card swap variables and deck filtering state
first_card_to_swap, second_card_to_swap = None, None
current_search_input = ""
is_using_decklist_filter = False
cards_from_imported_deck = None


# Create main GUI layout
main_window_layout = [
    [
        sg.Frame(
            "",
            [
                [
                    sg.Button(
                        "Select database file & image save location",
                        key="-SELECT_DATABASE-",
                        size=(35, 1),
                        pad=(5, 5),
                    ),
                    sg.Button("Swap Arts", key="-SWAP_ARTS-", size=(15, 1), pad=(5, 5)),
                    sg.Button(
                        "Load Decklist", key="-LOAD_DECKLIST-", size=(15, 1), pad=(5, 5)
                    ),
                ],
                [
                    sg.Button(
                        (
                            "Select database and image save location before changing sleeves and avatars"
                            if database_file_path is None
                            else "Change Sleeves, Avatars, etc."
                        ),
                        key="-CHANGE_ASSETS-",
                        disabled=database_file_path is None,
                        size=(53, 1),
                    ),
                    sg.Button(
                        "Export Fonts", key="-EXPORT_FONTS-", size=(15, 1), pad=(5, 5)
                    ),
                ],
                [
                    sg.Button("Search tokens", key="-SEARCH_TOKENS-", expand_x=True),
                    sg.Button(
                        "Load Changes Preset", key="-LOAD_PRESET-", expand_x=True
                    ),
                    sg.Button(
                        "Export Changes Preset", key="-EXPORT_PRESET-", expand_x=True
                    ),
                ],
                [
                    sg.Button(
                        "Set Swapper (Swap entire sets)",
                        key="-SET_SWAPPER-",
                        expand_x=True,
                        disabled=database_file_path is None,
                    ),
                ],
                [
                    sg.Input(
                        "Database: "
                        + (database_file_path if database_file_path else "None"),
                        key="DATABASE_DISPLAY",
                        readonly=True,
                        font=("Segoe UI", 8),
                        size=(80, 1),
                    )
                ],
                [
                    sg.Input(
                        "Image Save Location: "
                        + (image_save_directory if image_save_directory else "None"),
                        key="IMAGE_SAVE_DISPLAY",
                        readonly=True,
                        font=("Segoe UI", 8),
                        size=(80, 1),
                    )
                ],
            ],
            relief=sg.RELIEF_RIDGE,
        )
    ],
    [
        sg.Frame(
            "Search Cards",
            [
                [
                    sg.Text(
                        "Search by any of these attributes (Format: Name, Set, ArtType, GrpID, ArtID)",
                        justification="left",
                    )
                ],
                [
                    sg.Input(
                        size=(40, 1),
                        enable_events=True,
                        key="-SEARCH_INPUT-",
                        pad=(5, 5),
                    ),
                    sg.Checkbox(
                        "Use Decklist",
                        key="-USE_DECKLIST-",
                        default=is_using_decklist_filter,
                        enable_events=True,
                    ),
                ],
                [
                    sg.Button(
                        "Unlock Parallax Style for all cards in the list below",
                        key="-UNLOCK_PARALLAX-",
                    ),
                    sg.Button(
                        "Backup changes for all cards in the list below",
                        key="-LOAD_OLD_CHANGES-",
                        expand_x=True,
                    ),
                ],
                [
                    sg.Text("Sort by:"),
                    sg.Combo(
                        ["Name", "Set", "ArtType", "GrpID", "ArtID"],
                        default_value="Name",
                        key="-SORT_BY-",
                        enable_events=True,
                        readonly=True,
                        size=(15, 1),
                    ),
                ],
                [
                    sg.Text(
                        f"{'Name':<30} {'Set':<7} {'ArtType':<12} {'GrpID':<8} {'ArtID':<8}",
                        font=("Courier New", 10, "bold"),
                    )
                ],
                [
                    sg.Listbox(
                        displayed_cards,
                        size=(70, 20),
                        enable_events=True,
                        key="-CARD_LIST-",
                        pad=(5, 5),
                        font=("Courier New", 10),
                    )
                ],
            ],
            relief=sg.RELIEF_GROOVE,
            expand_x=True,
        )
    ],
]

# Create main application window
main_window = sg.Window(
    "MTGA Swapper",
    main_window_layout,
    grab_anywhere=True,
    finalize=True,
    font=("Segoe UI", 10),
    element_justification="center",
    background_color="#1B2838",
    relative_location=(0, 0),
)

# Main GUI Event Loop
while True:
    event, values = main_window.read()
    if event in (sg.WIN_CLOSED, "Exit"):
        break

    # Handle sorting of cards by selected attribute
    if event == "-SORT_BY-":
        selected_sort_attribute = values["-SORT_BY-"]
        sorted_card_list = sort_cards_by_attribute(
            main_window["-CARD_LIST-"].Values or displayed_cards,
            selected_sort_attribute,
        )
        main_window["-CARD_LIST-"].update(sorted_card_list)

    if event == "-LOAD_PRESET-":
        preset_path = open_file_dialog(
            "Select your changes preset JSON file", "JSON files", "*.json"
        )
        change_grp_id(preset_path, database_cursor, database_connection)

        sg.popup_auto_close("Preset loaded successfully!", auto_close_duration=1)
    if event == "-EXPORT_PRESET-":
        with open(user_save_changes_path, "r") as changes_file:
            changes_data = json.load(changes_file)

        with open("exported_changes.json", "w") as export_file:
            json.dump(changes_data, export_file, indent=4)

        sg.popup_auto_close(
            "Exported changes to exported_changes.json", auto_close_duration=0.5
        )

    # Handle Set Swapper functionality
    if event == "-SET_SWAPPER-":
        if not database_file_path or not image_save_directory:
            sg.popup_error(
                "Please select database and image save location first",
                auto_close_duration=3,
            )
            continue

        # Create set swapper window
        swap_window = create_set_swap_window()

        try:
            while True:
                swap_event, swap_values = swap_window.read()

                if swap_event in (sg.WIN_CLOSED, "-CLOSE-"):
                    break

                if swap_event == "-GENERATE_SWAPS-":
                    source_set = swap_values["-SOURCE_SET-"].strip().lower()
                    target_set = swap_values["-TARGET_SET-"].strip().lower()

                    if not source_set or not target_set:
                        sg.popup_error("Please enter both source and target set codes.")
                        continue

                    # Generate to Downloads folder
                    output_path = (
                        Path.home()
                        / "Downloads"
                        / f"swaps_{source_set}_to_{target_set}.json"
                    )

                    if generate_swap_file(source_set, target_set, output_path):
                        swap_window["-SWAP_FILE-"].update(str(output_path))
                        sg.popup_ok(
                            f"Swap file generated successfully!\n\nSaved to:\n{output_path}",
                            title="Success",
                        )
                    else:
                        sg.popup_error(
                            "Failed to generate swap file.\n\n"
                            "Possible reasons:\n"
                            "- Invalid set codes\n"
                            "- No matching cards found\n"
                            "- Network error"
                        )

                if swap_event == "-APPLY_SWAPS-":
                    swap_file = swap_values["-SWAP_FILE-"].strip()

                    if not swap_file or not Path(swap_file).exists():
                        sg.popup_error("Please select a valid swap file.")
                        continue

                    # Confirm before applying
                    confirm = sg.popup_yes_no(
                        "This will modify your game files.\n\n"
                        "A backup will be created automatically.\n\n"
                        "Do you want to continue?",
                        title="Confirm Swap",
                    )

                    if confirm == "Yes":
                        asset_bundle_dir = (
                            Path(database_file_path).parent.parent / "AssetBundle"
                        )
                        backup_dir = Path.home() / "MTGA_Swapper_Backups"
                        sg.popup_quick_message(
                            "Please wait, this may take a couple of minutes. There will be a popup when completed",
                            auto_close_duration=2,
                        )

                        if perform_set_swap(
                            Path(swap_file),
                            database_cursor,
                            database_connection,
                            asset_bundle_dir,
                            backup_dir,
                        ):
                            sg.popup_ok(
                                "Set swap completed successfully!\n\n"
                                "Backups saved to:\n" + str(backup_dir) + "\n\n"
                                "Launch MTG Arena to see your changes.",
                                title="Success",
                            )
                        else:
                            sg.popup_error(
                                "Set swap failed. Please check your swap file and try again."
                            )
                if swap_event == "-SPIDERMAN-":
                    if not database_file_path:
                        sg.popup_error(
                            "Please select a database first", auto_close_duration=3
                        )
                        continue
                    try:
                        spiderman_localizations(database_cursor, database_connection, get_resource_path("TempLocalizations.csv"))
                        sg.popup_auto_close(
                            "Spiderman localizations applied successfully!",
                            auto_close_duration=2,
                        )
                    except Exception as e:
                        sg.popup_error(f"Error applying localizations: {e}")

        finally:
            swap_window.close()

    # Handle database and save directory selection
    if event == "-SELECT_DATABASE-":
        database_file_path = open_file_dialog(
            "Select your Raw_CardDatabase mtga file in Raw Folder",
            "mtga files",
            "*.mtga",
        )
        try:
            # Initialize database connection and load cards
            database_cursor, database_connection, database_file_path = (
                database_manager.create_database_connection(database_file_path)
            )

            all_cards_formatted = list(
                map(
                    format_card_display,
                    sorted(
                        database_cursor.execute(
                            """
        SELECT 
        CASE 
            WHEN c1.Order_Title IS NOT NULL THEN c1.Order_Title
            WHEN c1.Order_Title IS NULL AND c2.Order_Title IS NOT NULL THEN c2.Order_Title || '-flip-side'
        END AS Order_Title,
        c1.ExpansionCode,
        c1.ArtSize,
        c1.GrpID,
        c1.ArtID
        FROM Cards c1
        LEFT JOIN Cards c2
        ON c1.LinkedFaceGrpIds = c2.GrpID
        AND c2.Order_Title IS NOT NULL
        WHERE c1.Order_Title IS NOT NULL OR c2.Order_Title IS NOT NULL
    """
                        ).fetchall()
                    ),
                )
            )
            displayed_cards = all_cards_formatted
        except (
            database_manager.sqlite3.OperationalError,
            database_manager.sqlite3.DatabaseError,
            TypeError,
        ):
            sg.popup_error(
                "Missing or incorrect database selected", auto_close_duration=3
            )

        # Select image save directory
        image_save_directory = open_directory_dialog(
            "Select a folder to save images to"
        )

        # Save configuration to file
        if image_save_directory and database_file_path:
            with open(user_config_file_path, "w") as config_file:
                user_config["SavePath"] = str(Path(image_save_directory).as_posix())
                user_config["DatabasePath"] = str(Path(database_file_path).as_posix())
                config_file.write(sg.json.dumps(user_config, indent=4))

        # Configure Unity version and update GUI
        configure_unity_version(database_file_path, "2022.3.42f1")
        main_window["-CARD_LIST-"].update(displayed_cards)
        main_window["-CHANGE_ASSETS-"].update(
            "Change Sleeves, Avatars, etc.", disabled=False
        )
        main_window["-SET_SWAPPER-"].update(disabled=False)
        main_window["DATABASE_DISPLAY"].update(
            "Database: " + (database_file_path if database_file_path else "None")
        )
        main_window["IMAGE_SAVE_DISPLAY"].update(
            "Image Save Location: "
            + (image_save_directory if image_save_directory else "None")
        )
        asset_bundle_directory = (
            os.path.dirname(database_file_path)[0:-3] + "AssetBundle"
        )

    if event == "-SEARCH_TOKENS-":
        if database_cursor is not None:
            window_tokens = create_search_tokens_window(database_cursor)
            while True:
                event_token, values_token = window_tokens.read()
                if event_token == sg.WINDOW_CLOSED or event_token == "-CANCEL_BUTTON-":
                    break
                elif event_token == "-SEARCH_BUTTON-":
                    artist_name = values_token["-SEARCH_INPUT-"]
                    # Perform search operation here
                    tokens = database_manager.get_tokens_by_artist(
                        artist_name, database_cursor
                    )
                    if tokens:
                        window_tokens["-RESULT_LIST-"].update(
                            values=[f"{name} - {art_id}" for name, art_id in tokens]
                        )
                    else:
                        window_tokens["-RESULT_LIST-"].update(
                            values=["No tokens found."]
                        )
                elif event_token == "-RESULT_LIST-":
                    selected_token = values_token["-RESULT_LIST-"][0]
                    token_card = MTGACard(
                        "", "", "", "", selected_token.split(" - ")[1]
                    )

                    image_data_list, texture_data_list, matching_file = (
                        get_card_texture_data(
                            token_card, database_file_path, ret_matching=True
                        )
                    )
                    if image_data_list:
                        display_texture_bytes = convert_texture_to_bytes(
                            image_data_list[0]
                        )
                        token_card.image = display_texture_bytes
                    else:
                        print("No texture found.")
                    token_editor_layout = [
                        [
                            sg.Button(
                                "Change image",
                                key="-CHANGE_ASSET_IMAGE-",
                            ),
                            sg.Button(
                                "Set aspect ratio to",
                                key="-SET_ASPECT_RATIO-",
                            ),
                            sg.Input(
                                "Width",
                                key="-ASPECT_WIDTH-",
                                size=(5, 1),
                            ),
                            sg.Input(
                                "Height",
                                key="-ASPECT_HEIGHT-",
                                size=(5, 1),
                            ),
                            sg.Button("Save", key="-SAVE_ASSET-"),
                        ],
                        [
                            sg.Image(
                                source=display_texture_bytes,
                                key="-ASSET_IMAGE-",
                            )
                        ],
                    ]
                    # Show the token editor window
                    token_editor_window = sg.Window(
                        "Edit Token",
                        token_editor_layout,
                        modal=True,
                        finalize=True,
                        grab_anywhere=True,
                        relative_location=(0, 0),
                    )
                    while True:
                        event, values = token_editor_window.read()
                        if event == sg.WINDOW_CLOSED:
                            break
                        if event == "-CHANGE_ASSET_IMAGE-":
                            new_image_path = open_file_dialog(
                                "Select your new image", "image files", "*.png"
                            )
                            if new_image_path not in ("", None):
                                # Create backup of original image
                                backup_image_path = f"{os.path.join(image_save_directory, token_card.art_id)}-token_backup.png"
                                save_image_to_file(
                                    texture_data_list[0].image, backup_image_path, True
                                )
                                unity_environment = load_unity_bundle(
                                    os.path.join(asset_bundle_directory, matching_file)
                                )
                                # Replace the texture with new image
                                texture_data = extract_textures_from_bundle(
                                    unity_environment
                                )[0]
                                replace_texture_in_bundle(
                                    texture_data,
                                    new_image_path,
                                    os.path.join(asset_bundle_directory, matching_file),
                                    unity_environment,
                                )
                                display_texture_bytes = convert_texture_to_bytes(
                                    texture_data.image
                                )

                                # Update display with new image
                                token_editor_window["-ASSET_IMAGE-"].update(
                                    source=display_texture_bytes
                                )
                                token_card.image = texture_data.image
                                sg.popup_auto_close(
                                    "Image changed successfully!", auto_close_duration=1
                                )
                            else:
                                sg.popup_error(
                                    "Invalid image file", auto_close_duration=1
                                )

                        # Handle asset saving
                        if event == "-SAVE_ASSET-":

                            save_path = f"{os.path.join(image_save_directory, token_card.art_id)}-token.png"
                            save_image_to_file(token_card.image, save_path, True)
                            sg.popup_auto_close(
                                "Asset saved successfully!", auto_close_duration=1
                            )
        else:
            sg.popup_error("Please select a database first", auto_close_duration=3)

    # Handle decklist loading
    if event == "-LOAD_DECKLIST-":
        cards_from_imported_deck = create_decklist_import_window()
        main_window["-USE_DECKLIST-"].update(value=True)
        event = "-USE_DECKLIST-"
        values["-USE_DECKLIST-"] = True

    if event == "-UNLOCK_PARALLAX-":
        grpid_list = [
            card.split()[3]
            for card in filtered_search_results
            if card.split()[0]
            not in ("island", "forest", "mountain", "plains", "wastes", "swamp")
        ]

        if database_manager.unlock_parallax_style(
            grpid_list, database_cursor, database_connection, user_save_changes_path
        ):
            sg.popup_auto_close("Parallax style unlocked successfully!")
        else:
            sg.popup_auto_close(
                "Failed to unlock parallax style, ensure that the database is not open in another program."
            )

    if event == "-LOAD_OLD_CHANGES-":
        grpid_list = [
            card.split()[3]
            for card in filtered_search_results
            if card.split()[0]
            not in ("island", "forest", "mountain", "plains", "wastes", "swamp")
        ]
        save_grp_id_info(
            grpid_list,
            user_save_changes_path,
            database_cursor,
            database_connection,
        )
        with open(user_save_changes_path, "r") as changes_file:
            changes_data = json.load(changes_file)

        with open("exported_changes.json", "w") as export_file:
            json.dump(changes_data, export_file, indent=4)

        sg.popup_auto_close(
            "Exported changes to exported_changes.json", auto_close_duration=0.5
        )

    # Handle font export functionality
    if event == "-EXPORT_FONTS-":
        font_bundle_path = askopenfilename(
            title="Select file that starts with 'Fonts_' in AssetBundle Folder"
        )
        font_export_directory = askdirectory(
            initialdir=os.path.dirname(font_bundle_path),
            title="Select folder to save fonts",
        )
        if font_bundle_path:
            unity_environment = load_unity_bundle(font_bundle_path)
            extracted_fonts = extract_fonts(unity_environment, font_export_directory)

    # Handle change assets functionality (sleeves, avatars, etc.)
    if event == "-CHANGE_ASSETS-":
        if database_file_path and image_save_directory:
            # Get the AssetBundle directory path
            asset_bundle_directory = (
                os.path.dirname(database_file_path)[0:-3] + "AssetBundle"
            )

            # Get list of asset bundle files (excluding card art)
            asset_bundle_files = sorted(
                [
                    bundle_file
                    for bundle_file in os.listdir(asset_bundle_directory)
                    if not any(
                        [
                            "CardArt" in bundle_file,
                            bundle_file.startswith("Bucket_Card.Sleeve"),
                        ]
                    )
                ]
            )

            # Create asset browser window
            asset_browser_layout = [
                [sg.Text("Select a file to change/view the assets of")],
                [sg.Text("Search for files by type")],
                [sg.Input(size=(90, 1), enable_events=True, key="-ASSET_SEARCH-")],
                [sg.Button("Export all images below", key="-EXPORT_ALL_ASSETS-")],
                [
                    sg.Listbox(
                        asset_bundle_files,
                        size=(90, 40),
                        enable_events=True,
                        key="-ASSET_LIST-",
                    )
                ],
            ]

            asset_browser_window = sg.Window(
                "Asset Browser - Sleeves, Avatars, etc.",
                asset_browser_layout,
                modal=True,
                grab_anywhere=True,
                relative_location=(0, 0),
                finalize=True,
            )

            # Asset browser event loop
            while True:
                asset_event, asset_values = asset_browser_window.read()
                if asset_event in (sg.WIN_CLOSED, "Exit"):
                    break

                # Handle search filtering
                if asset_event == "-ASSET_SEARCH-" and asset_values["-ASSET_SEARCH-"]:
                    search_term = asset_values["-ASSET_SEARCH-"].lower()
                    filtered_files = [
                        file
                        for file in asset_bundle_files
                        if search_term in file.lower()
                    ]
                    asset_browser_window["-ASSET_LIST-"].update(filtered_files)
                elif (
                    asset_event == "-ASSET_SEARCH-"
                    and not asset_values["-ASSET_SEARCH-"]
                ):
                    asset_browser_window["-ASSET_LIST-"].update(asset_bundle_files)

                # Handle export all assets
                if asset_event == "-EXPORT_ALL_ASSETS-":
                    current_asset_list = asset_browser_window["-ASSET_LIST-"].Values
                    if (
                        sg.popup_yes_no(
                            f"Are you sure you want to export all images from these {len(current_asset_list)} file bundles?"
                        )
                        == "Yes"
                    ):
                        if not os.path.exists(image_save_directory):
                            os.makedirs(image_save_directory)

                        for asset_file_name in current_asset_list:
                            try:
                                unity_environment = load_unity_bundle(
                                    os.path.join(
                                        asset_bundle_directory, asset_file_name
                                    )
                                )
                                extracted = extract_textures_from_bundle(
                                    unity_environment
                                )
                                for texture in extracted:
                                    texture.image.save(
                                        os.path.join(
                                            image_save_directory,
                                            f"{texture.m_Name}.png",
                                        )
                                    )
                            except Exception as e:
                                print(f"Error processing {asset_file_name}: {e}")

                        sg.popup_auto_close(
                            "All images exported successfully!", auto_close_duration=2
                        )

                # Handle individual asset selection
                if asset_event == "-ASSET_LIST-" and asset_values["-ASSET_LIST-"]:
                    selected_asset_file = asset_values["-ASSET_LIST-"][0]

                    try:
                        # Load the selected asset bundle
                        unity_environment = load_unity_bundle(
                            os.path.join(asset_bundle_directory, selected_asset_file)
                        )

                        # Get all textures from the bundle
                        texture_data_list = extract_textures_from_bundle(
                            unity_environment
                        )

                        if texture_data_list:
                            # Create gallery view with thumbnails
                            images_per_row = 3
                            gallery_images = []

                            for i, texture in enumerate(texture_data_list):
                                # Create thumbnail for gallery
                                thumbnail_image = resize_image_for_gallery(
                                    texture.image, (200, 200)
                                )
                                thumbnail_bytes = convert_texture_to_bytes(
                                    thumbnail_image
                                )

                                gallery_images.append(
                                    sg.Button(
                                        image_data=thumbnail_bytes,
                                        key=f"-GALLERY-IMG-{i}-",
                                        pad=(5, 5),
                                        tooltip=f"Click to view/edit image {i+1}",
                                    )
                                )

                            # Arrange images in rows
                            gallery_rows = [
                                gallery_images[i : i + images_per_row]
                                for i in range(0, len(gallery_images), images_per_row)
                            ]

                            # Create gallery layout
                            gallery_layout = [
                                [
                                    sg.Text(
                                        f"Gallery for: {selected_asset_file} ({len(texture_data_list)} images)"
                                    )
                                ],
                                [sg.Text("Click on an image to view/edit full size")],
                                [
                                    sg.Checkbox(
                                        "Remove Alpha (recommended)",
                                        key="-GALLERY_REMOVE_ALPHA-",
                                        default=True,
                                        enable_events=True,
                                    )
                                ],
                                [
                                    sg.Button(
                                        "Export all images", key="-GALLERY_EXPORT_ALL-"
                                    )
                                ],
                                [
                                    sg.Button(
                                        "Export all 3D meshes",
                                        key="-GALLERY_EXPORT_MESHES-",
                                    )
                                ],
                                [
                                    sg.Column(
                                        [row for row in gallery_rows],
                                        scrollable=True,
                                        vertical_scroll_only=True,
                                        size=(700, 500),
                                    )
                                ],
                                [sg.Button("Close Gallery", key="-GALLERY_CLOSE-")],
                            ]

                            gallery_window = sg.Window(
                                "Asset Gallery",
                                gallery_layout,
                                modal=True,
                                grab_anywhere=True,
                                finalize=True,
                                location=(0, 0),
                            )

                            # Gallery event loop
                            while True:
                                gallery_event, gallery_values = gallery_window.read()
                                if gallery_event in (sg.WIN_CLOSED, "-GALLERY_CLOSE-"):
                                    gallery_window.close()
                                    break

                                # Handle export all images
                                if gallery_event == "-GALLERY_EXPORT_ALL-":
                                    if not os.path.exists(image_save_directory):
                                        os.makedirs(image_save_directory)

                                    for i, texture in enumerate(texture_data_list):
                                        save_path = f"{os.path.join(image_save_directory, selected_asset_file)}-{i}.png"
                                        save_image_to_file(
                                            texture.image,
                                            save_path,
                                            gallery_values["-GALLERY_REMOVE_ALPHA-"],
                                        )
                                    sg.popup_auto_close(
                                        f"All images exported to {image_save_directory}!",
                                        auto_close_duration=1,
                                    )

                                # Handle export meshes
                                if gallery_event == "-GALLERY_EXPORT_MESHES-":
                                    if not os.path.exists(image_save_directory):
                                        os.makedirs(image_save_directory)
                                    mesh_count = export_3d_meshes(
                                        unity_environment, image_save_directory
                                    )
                                    sg.popup_auto_close(
                                        f"{mesh_count} 3D meshes were found and exported to {image_save_directory}!",
                                        auto_close_duration=1,
                                    )

                                # Handle individual image selection from gallery
                                for i in range(len(texture_data_list)):
                                    if gallery_event == f"-GALLERY-IMG-{i}-":
                                        texture_index = i
                                        current_texture = texture_data_list[
                                            texture_index
                                        ]

                                        # Resize for display
                                        display_image = resize_image_to_screen(
                                            current_texture.image
                                        )
                                        display_texture_bytes = (
                                            convert_texture_to_bytes(display_image)
                                        )

                                        # Create individual asset editor window
                                        asset_editor_layout = [
                                            [
                                                sg.Button(
                                                    "Change image",
                                                    key="-CHANGE_ASSET_IMAGE-",
                                                ),
                                                (
                                                    sg.Button(
                                                        "Previous",
                                                        key="-ASSET_PREVIOUS-",
                                                    )
                                                    if len(texture_data_list) > 1
                                                    else sg.Text("")
                                                ),
                                                (
                                                    sg.Button(
                                                        "Next", key="-ASSET_NEXT-"
                                                    )
                                                    if len(texture_data_list) > 1
                                                    else sg.Text("")
                                                ),
                                                sg.Button(
                                                    "Return to Gallery",
                                                    key="-RETURN_GALLERY-",
                                                ),
                                                sg.Button(
                                                    "Set aspect ratio to",
                                                    key="-SET_ASPECT_RATIO-",
                                                ),
                                                sg.Input(
                                                    "Width",
                                                    key="-ASPECT_WIDTH-",
                                                    size=(5, 1),
                                                ),
                                                sg.Input(
                                                    "Height",
                                                    key="-ASPECT_HEIGHT-",
                                                    size=(5, 1),
                                                ),
                                                sg.Checkbox(
                                                    "Remove Alpha",
                                                    key="-ASSET_REMOVE_ALPHA-",
                                                    default=True,
                                                    enable_events=True,
                                                ),
                                                sg.Button("Save", key="-SAVE_ASSET-"),
                                            ],
                                            [
                                                sg.Image(
                                                    source=display_texture_bytes,
                                                    key="-ASSET_IMAGE-",
                                                )
                                            ],
                                            [
                                                sg.Text(
                                                    f"Texture {texture_index + 1} of {len(texture_data_list)} in {selected_asset_file}",
                                                    key="-ASSET_INFO-",
                                                )
                                            ],
                                        ]

                                        asset_editor_window = sg.Window(
                                            f"Asset Editor - {selected_asset_file}",
                                            asset_editor_layout,
                                            modal=True,
                                            grab_anywhere=True,
                                            relative_location=(0, 0),
                                            finalize=True,
                                        )

                                        # Asset editor event loop
                                        while True:
                                            asset_editor_event, asset_editor_values = (
                                                asset_editor_window.read()
                                            )
                                            if asset_editor_event in (
                                                sg.WIN_CLOSED,
                                                "Exit",
                                                "-RETURN_GALLERY-",
                                            ):
                                                asset_editor_window.close()
                                                break

                                            # Handle navigation between textures
                                            if asset_editor_event in (
                                                "-ASSET_PREVIOUS-",
                                                "-ASSET_NEXT-",
                                            ):
                                                texture_index += (
                                                    1
                                                    if asset_editor_event
                                                    == "-ASSET_NEXT-"
                                                    else -1
                                                )
                                                if texture_index >= len(
                                                    texture_data_list
                                                ):
                                                    texture_index = 0
                                                if texture_index < 0:
                                                    texture_index = (
                                                        len(texture_data_list) - 1
                                                    )

                                                current_texture = texture_data_list[
                                                    texture_index
                                                ]
                                                display_image = resize_image_to_screen(
                                                    current_texture.image
                                                )
                                                display_texture_bytes = (
                                                    convert_texture_to_bytes(
                                                        display_image
                                                    )
                                                )
                                                asset_editor_window[
                                                    "-ASSET_IMAGE-"
                                                ].update(source=display_texture_bytes)
                                                asset_editor_window[
                                                    "-ASSET_INFO-"
                                                ].update(
                                                    f"Texture {texture_index + 1} of {len(texture_data_list)} in {selected_asset_file}"
                                                )

                                            # Handle image replacement
                                            if (
                                                asset_editor_event
                                                == "-CHANGE_ASSET_IMAGE-"
                                            ):
                                                new_image_path = open_file_dialog(
                                                    "Select your new image",
                                                    "image files",
                                                    "*.png",
                                                )
                                                if new_image_path not in ("", None):
                                                    # Create backup
                                                    backup_path = f"{os.path.join(image_save_directory, selected_asset_file)}-{texture_index}_backup{randint(1, 1000)}.png"
                                                    save_image_to_file(
                                                        current_texture.image,
                                                        backup_path,
                                                        asset_editor_values[
                                                            "-ASSET_REMOVE_ALPHA-"
                                                        ],
                                                    )

                                                    # Replace texture
                                                    replace_texture_in_bundle(
                                                        current_texture,
                                                        new_image_path,
                                                        os.path.join(
                                                            asset_bundle_directory,
                                                            selected_asset_file,
                                                        ),
                                                        unity_environment,
                                                    )

                                                    # Update displays
                                                    new_img = Image.open(new_image_path)
                                                    display_image = (
                                                        resize_image_to_screen(new_img)
                                                    )
                                                    display_texture_bytes = (
                                                        convert_texture_to_bytes(
                                                            display_image
                                                        )
                                                    )
                                                    asset_editor_window[
                                                        "-ASSET_IMAGE-"
                                                    ].update(
                                                        source=display_texture_bytes
                                                    )

                                                    # Update gallery thumbnail
                                                    thumbnail_image = (
                                                        resize_image_for_gallery(
                                                            new_img, (200, 200)
                                                        )
                                                    )
                                                    thumbnail_bytes = (
                                                        convert_texture_to_bytes(
                                                            thumbnail_image
                                                        )
                                                    )
                                                    gallery_window[
                                                        f"-GALLERY-IMG-{texture_index}-"
                                                    ].update(image_data=thumbnail_bytes)

                                                    # Update texture data
                                                    texture_data_list[
                                                        texture_index
                                                    ].image = new_img

                                                    sg.popup_auto_close(
                                                        "Image changed successfully!",
                                                        auto_close_duration=1,
                                                    )

                                            # Handle aspect ratio adjustment
                                            if (
                                                asset_editor_event
                                                == "-SET_ASPECT_RATIO-"
                                            ):
                                                try:
                                                    (
                                                        resized_image,
                                                        new_width,
                                                        new_height,
                                                    ) = adjust_image_aspect_ratio(
                                                        current_texture.image,
                                                        (
                                                            float(
                                                                asset_editor_values[
                                                                    "-ASPECT_WIDTH-"
                                                                ]
                                                            ),
                                                            float(
                                                                asset_editor_values[
                                                                    "-ASPECT_HEIGHT-"
                                                                ]
                                                            ),
                                                        ),
                                                    )
                                                    display_texture_bytes = (
                                                        convert_texture_to_bytes(
                                                            resized_image
                                                        )
                                                    )
                                                    asset_editor_window[
                                                        "-ASSET_IMAGE-"
                                                    ].update(
                                                        source=display_texture_bytes
                                                    )
                                                except ValueError:
                                                    sg.popup_error(
                                                        "Invalid aspect ratio values, edit them before applying",
                                                        auto_close_duration=3,
                                                    )

                                            # Handle saving current texture
                                            if asset_editor_event == "-SAVE_ASSET-":
                                                save_path = f"{os.path.join(image_save_directory, selected_asset_file)}-{texture_index}.png"
                                                save_image_to_file(
                                                    current_texture.image,
                                                    save_path,
                                                    asset_editor_values[
                                                        "-ASSET_REMOVE_ALPHA-"
                                                    ],
                                                )
                                                sg.popup_auto_close(
                                                    "Image saved successfully!",
                                                    auto_close_duration=1,
                                                )

                                        break  # Exit the gallery loop when returning from editor

                        else:
                            sg.popup_error("No textures found in this asset bundle!")

                    except Exception as e:
                        sg.popup_error(f"Error loading asset bundle: {e}")

            asset_browser_window.close()
        else:
            sg.popup_error(
                "You haven't selected a database and/or save location",
                auto_close_duration=3,
            )

    # Handle decklist filtering toggle
    if event == "-USE_DECKLIST-":
        is_using_decklist_filter = values["-USE_DECKLIST-"]
        if is_using_decklist_filter:
            if cards_from_imported_deck is None:
                sg.popup_error(
                    "Load a decklist first or disable Use Decklist",
                    auto_close_duration=3,
                )
                main_window["-USE_DECKLIST-"].update(value=False)
                continue

            # Filter cards based on imported decklist
            filtered_cards_from_deck = [
                card
                for card in all_cards_formatted
                if card[:15].strip() in cards_from_imported_deck
            ]
            displayed_cards = filtered_cards_from_deck
            if filtered_cards_from_deck:
                main_window["-CARD_LIST-"].update(filtered_cards_from_deck)
            filtered_search_results = filtered_cards_from_deck

        else:
            main_window["-CARD_LIST-"].update(all_cards_formatted)
            displayed_cards = all_cards_formatted

    # Handle search input for filtering cards
    if values and values["-SEARCH_INPUT-"] != "":
        if values["-SEARCH_INPUT-"] != current_search_input:
            current_search_input = values["-SEARCH_INPUT-"].replace(" ", "").lower()
            search_query = current_search_input

            # Filter cards based on search query
            filtered_search_results = [
                card for card in displayed_cards if search_query in card.lower()
            ]
            main_window["-CARD_LIST-"].update(filtered_search_results)
    else:
        # Reset to full card list when search is cleared
        if current_search_input != "":
            main_window["-CARD_LIST-"].update(displayed_cards)
            current_search_input = ""

    # Handle card art swapping functionality
    if event == "-SWAP_ARTS-":
        # Prepare preview images for both cards to be swapped
        first_card_preview_image = None
        second_card_preview_image = None

        if first_card_to_swap:
            try:
                card_data = get_card_texture_data(
                    first_card_to_swap,
                    database_file_path,
                )
                if card_data and card_data[0]:
                    first_card_preview_image = convert_pil_image_to_bytes(
                        card_data[0][0]
                    )
            except:
                pass

        if second_card_to_swap:
            try:
                card_data = get_card_texture_data(
                    second_card_to_swap,
                    database_file_path,
                )
                if card_data and card_data[0]:
                    second_card_preview_image = convert_pil_image_to_bytes(
                        card_data[0][0]
                    )
            except:
                pass

        # Create swap confirmation dialog layout
        swap_confirmation_layout = [
            [sg.Text("You are about to swap the following cards:")],
            [
                sg.Column(
                    [
                        [sg.Text("First Card:")],
                        [
                            sg.Text(
                                (
                                    str(first_card_to_swap)
                                    if first_card_to_swap
                                    else "Not selected"
                                ),
                                font=("Courier New", 10),
                            )
                        ],
                        [
                            (
                                sg.Image(first_card_preview_image, subsample=2)
                                if first_card_preview_image
                                else sg.Text("No image")
                            )
                        ],
                    ]
                ),
                sg.Column(
                    [
                        [sg.Text("Second Card:")],
                        [
                            sg.Text(
                                (
                                    str(second_card_to_swap)
                                    if second_card_to_swap
                                    else "Not selected"
                                ),
                                font=("Courier New", 10),
                            )
                        ],
                        [
                            (
                                sg.Image(second_card_preview_image, subsample=2)
                                if second_card_preview_image
                                else sg.Text("No image")
                            )
                        ],
                    ]
                ),
            ],
            [
                sg.Button(
                    "Confirm Swap",
                    key="-CONFIRM_SWAP-",
                    disabled=first_card_to_swap is None or second_card_to_swap is None,
                ),
                sg.Button("Cancel", key="-CANCEL_SWAP-"),
            ],
        ]

        # Create and show swap confirmation window
        swap_confirmation_window = sg.Window(
            "Confirm Swap",
            swap_confirmation_layout,
            modal=True,
            finalize=True,
            relative_location=(0, 0),
        )

        # Swap confirmation event loop
        while True:
            swap_event, swap_values = swap_confirmation_window.read()
            if swap_event in (sg.WIN_CLOSED, "-CANCEL_SWAP-"):
                swap_confirmation_window.close()
                break
            if (
                swap_event == "-CONFIRM_SWAP-"
                and first_card_to_swap
                and second_card_to_swap
            ):
                # Perform the actual card swap in the database

                if (
                    first_card_to_swap.name != second_card_to_swap.name
                    or first_card_to_swap.name
                    in ("island", "forest", "mountain", "plains", "swamp")
                ):

                    database_manager.swap_card_group_ids(
                        first_card_to_swap.grp_id,
                        second_card_to_swap.grp_id,
                        database_cursor,
                        database_connection,
                        user_save_changes_path,
                    )
                else:
                    print("Swapping styles")
                    database_manager.swap_card_styles(
                        first_card_to_swap.grp_id,
                        second_card_to_swap.grp_id,
                        database_cursor,
                        database_connection,
                        user_save_changes_path,
                    )

                sg.popup_ok("Cards swapped successfully!", auto_close_duration=2)
                swap_confirmation_window.close()
                break

    # Handle card selection from the list
    if event == "-CARD_LIST-" and values["-CARD_LIST-"]:
        # Create card object from selected list item

        selected_card_data = MTGACard(
            *values["-CARD_LIST-"][0].split(),
        )

        database_cursor.execute(
            """
            SELECT TitleId
            FROM Cards
            WHERE GrpId = ?
        """,
            (selected_card_data.grp_id,),
        )
        row = database_cursor.fetchone()

        if row is None:
            print("Row not found.")
        else:
            title_id = row[0]

        alternates = database_cursor.execute(
            """
                SELECT 
                    ExpansionCode,
                    ArtSize,
                    GrpId,
                    ArtId
                FROM Cards
                WHERE 
                    TitleId = ?
                    AND ArtId != ?
            """,
            (title_id, selected_card_data.art_id),
        ).fetchall()

        alternates = [MTGACard(selected_card_data.name, *row) for row in alternates]

        alternate_display = [
            selected_card_data.name + " (" + card.set_code + ") - alternate"
            for card in alternates
        ]
        alternates.insert(0, selected_card_data)
        alternate_display.insert(
            0,
            selected_card_data.name
            + " ("
            + selected_card_data.set_code
            + ") - selected",
        )

        # Ensure art_id is properly formatted (6 digits with leading zeros)
        if len(selected_card_data.art_id) < 6:
            selected_card_data.art_id = selected_card_data.art_id.zfill(6)

        # Construct path to asset bundles
        asset_bundle_directory = (
            os.path.dirname(database_file_path)[0:-3] + "AssetBundle"
        )

        try:
            # Find the asset bundle file for this specific card
            matching_bundle_files = [
                bundle_file
                for bundle_file in os.listdir(asset_bundle_directory)
                if bundle_file.startswith(str(selected_card_data.art_id))
                and bundle_file.endswith(".mtga")
            ][0]

            # Load the Unity asset bundle
            unity_environment = load_unity_bundle(
                os.path.join(asset_bundle_directory, matching_bundle_files)
            )
            texture_index = 0

            # Get card textures and process them for display
            image_data_list, texture_data_list = get_card_texture_data(
                selected_card_data,
                database_file_path,
            )

            if texture_data_list:
                card_textures = texture_data_list
                display_texture_bytes = convert_texture_to_bytes(
                    image_data_list[texture_index]
                )

                texture_width, texture_height = texture_data_list[
                    texture_index
                ].image.size
            else:
                # Handle case where no textures are found
                card_textures = None
                display_texture_bytes = None
                sg.popup_error("No textures found for selected card!")
                continue
            selected_card_data.image = image_data_list[0]
            if card_textures is not None:
                # Create card editor window layout
                card_editor_layout = [
                    [
                        [
                            sg.Button("Change image", key="-CHANGE_IMAGE-"),
                            (
                                sg.Button("Previous in bundle", key="-PREVIOUS-")
                                if len(card_textures) > 1
                                else sg.Text("")
                            ),
                            (
                                sg.Button("Next in bundle", key="-NEXT-")
                                if len(card_textures) > 1
                                else sg.Text("")
                            ),
                            sg.Button("Set to Swap 1", key="-SET_SWAP_1-"),
                            sg.Button("Set to Swap 2", key="-SET_SWAP_2-"),
                            sg.Button("Adjust style tags", key="-ADJUST_STYLE_TAGS-"),
                            sg.Combo(
                                values=alternate_display,
                                default_value=(
                                    alternate_display[0] if alternate_display else ""
                                ),
                                key="-SEARCH_ALTERNATES-",
                                readonly=True,
                                enable_events=True,
                            ),
                        ],
                        [
                            sg.Button("Edit details", key="-EDIT_DETAILS-"),
                            sg.Button("Set aspect ratio to", key="-SET_ASPECT_RATIO-"),
                            sg.Input(
                                "3" if selected_card_data.art_type == "1" else "11",
                                key="-ASPECT_WIDTH-",
                                size=(3, 1),
                            ),
                            sg.Input(
                                "4" if selected_card_data.art_type == "1" else "8",
                                key="-ASPECT_HEIGHT-",
                                size=(3, 1),
                            ),
                            sg.Checkbox(
                                "Remove Alpha (recommended)",
                                key="-REMOVE_ALPHA-",
                                default=True,
                                enable_events=True,
                            ),
                            sg.Button("Save", key="-SAVE_IMAGE-"),
                            sg.Button(
                                "Upscale",
                                key="-UPSCALE_IMAGE-",
                                disabled=not is_upscaling_available,
                            ),
                        ],
                    ],
                    [
                        sg.Image(
                            source=display_texture_bytes,
                            key="-CARD_IMAGE-",
                        )
                    ],
                ]

                # Create card editor window
                card_editor_window = sg.Window(
                    "Showing: " + selected_card_data.name + " Art",
                    card_editor_layout,
                    modal=True,
                    grab_anywhere=True,
                    relative_location=(0, 0),
                    finalize=True,
                )

                # Card editor event loop
                while True:
                    editor_event, editor_values = card_editor_window.read()
                    if editor_event == "-EXIT-" or editor_event == sg.WIN_CLOSED:
                        break

                    # Handle navigation between textures in the bundle
                    if editor_event in ("-PREVIOUS-", "-NEXT-"):
                        texture_index += 1 if editor_event == "-NEXT-" else -1
                        if texture_index >= len(card_textures):
                            texture_index = 0
                        if texture_index < 0:
                            texture_index = len(card_textures) - 1
                        1070957949
                        display_texture_bytes = convert_texture_to_bytes(
                            image_data_list[texture_index]
                        )
                        card_editor_window["-CARD_IMAGE-"].update(
                            source=display_texture_bytes
                        )
                        selected_card_data.image = image_data_list[texture_index]

                    if editor_event == "-EDIT_DETAILS-":
                        details = fetch_all_data(
                            database_cursor, selected_card_data.grp_id
                        )
                        if details:
                            detail_layout = []
                            for key, value in details.items():
                                detail_layout.append(
                                    [
                                        sg.Text(key, size=(15, 1)),
                                        sg.Input(value, key=f"-DETAIL-{key}-"),
                                    ]
                                )
                            # Split detail_layout into two columns of equal length
                            num_fields = len(detail_layout)
                            mid_index = (num_fields + 1) // 2

                            left_column = detail_layout[:mid_index]
                            right_column = detail_layout[mid_index:]

                            # Add the Save Details button below both columns
                            columns_layout = [
                                [
                                    sg.Button("Save Details", key="-SAVE_DETAILS-"),
                                    sg.Text(
                                        "Warning: Make sure you know what you're doing!",
                                        size=(40, 1),
                                    ),
                                ],
                                [
                                    sg.Text("Name", size=(15, 1)),
                                    sg.Input(
                                        database_manager.get_localization_from_id(
                                            database_cursor, details["TitleId"]
                                        ),
                                        key=f"-Loc_DETAIL-TitleId-",
                                    ),
                                    sg.Text("Flavor Text", size=(15, 1)),
                                    sg.Input(
                                        database_manager.get_localization_from_id(
                                            database_cursor, details["FlavorTextId"]
                                        ),
                                        key=f"-Loc_DETAIL-FlavorTextId-",
                                    ),
                                    # sg.Text("Type", size=(15, 1)),
                                    # sg.Input(
                                    #     database_manager.get_localization_from_id(
                                    #         database_cursor, details["TypeTextId"]
                                    #     ),
                                    #     key=f"-Loc_DETAIL-{key}-",
                                    # ),
                                    # sg.Text("Subtype", size=(15, 1)),
                                    # sg.Input(
                                    #     database_manager.get_localization_from_id(
                                    #         database_cursor, details["SubtypeTextId"]
                                    #     ),
                                    #     key=f"-Loc_DETAIL-{key}-",
                                    # ),
                                ],
                                [
                                    sg.Column(left_column, vertical_alignment="top"),
                                    sg.Column(right_column, vertical_alignment="top"),
                                ],
                            ]

                            detail_window = sg.Window(
                                f"Editing details for {selected_card_data.name}",
                                columns_layout,
                                modal=True,
                                grab_anywhere=True,
                                relative_location=(0, -50),
                                finalize=True,
                            )

                            while True:
                                detail_event, detail_values = detail_window.read()
                                if detail_event in (sg.WIN_CLOSED, "Exit"):
                                    break
                                if detail_event == "-SAVE_DETAILS-":
                                    new_values = {
                                        key.replace("-DETAIL-", "")[:-1]: detail_values[
                                            key
                                        ]
                                        for key in detail_values
                                        if key.startswith("-DETAIL-")
                                    }
                                    change_grp_id(
                                        "",
                                        database_cursor,
                                        database_connection,
                                        json_manual=new_values,
                                    )
                                    save_grp_id_info(
                                        [selected_card_data.grp_id],
                                        user_save_changes_path,
                                        database_cursor,
                                        database_connection,
                                    )
                                    sg.popup_ok(
                                        "Details updated successfully!",
                                        auto_close_duration=2,
                                    )

                                    new_loc_values = {
                                        key.replace("-Loc_DETAIL-", "")[
                                            :-1
                                        ]: detail_values[key]
                                        for key in detail_values
                                        if key.startswith("-Loc_DETAIL-")
                                    }
                                    for loc_key, loc_value in new_loc_values.items():
                                        if loc_key in (
                                            "TitleId",
                                            "FlavorTextId",
                                            "TypeTextId",
                                            "SubtypeTextId",
                                        ):
                                            database_manager.set_localization_from_id(
                                                database_cursor,
                                                details[loc_key],
                                                loc_value,
                                            )
                                            save_loc_id_info(
                                                user_save_changes_path,
                                                details[loc_key],
                                                loc_value,
                                                selected_card_data.grp_id,
                                            )

                                    break
                            detail_window.close()

                    if editor_event == "-ADJUST_STYLE_TAGS-":
                        current_tags = database_cursor.execute(
                            "SELECT Tags FROM Cards WHERE GrpId = ?",
                            (selected_card_data.grp_id,),
                        ).fetchone()[0]

                        new_tag = sg.popup_get_text(
                            "Edit Tags (Add 1696804317 to the tags (comma separated if needed) to use the animated style borderless)",
                            default_text=(
                                current_tags
                                if current_tags not in ("", "('',)")
                                else ""
                            ),
                        )
                        if new_tag:
                            database_cursor.execute(
                                "UPDATE Cards SET Tags = ? WHERE GrpId = ?",
                                (new_tag, selected_card_data.grp_id),
                            )
                            save_grp_id_info(
                                [selected_card_data.grp_id],
                                user_save_changes_path,
                                database_cursor,
                                database_connection,
                            )

                            database_connection.commit()

                    if editor_event == "-SEARCH_ALTERNATES-":
                        selected_card_data = (
                            alternates[
                                alternate_display.index(
                                    editor_values["-SEARCH_ALTERNATES-"]
                                )
                            ]
                            if editor_values["-SEARCH_ALTERNATES-"] in alternate_display
                            else False
                        )

                        asset_bundle_directory = (
                            os.path.dirname(database_file_path)[0:-3] + "AssetBundle"
                        )

                        try:
                            # Find the asset bundle file for this specific card
                            matching_bundle_files = [
                                bundle_file
                                for bundle_file in os.listdir(asset_bundle_directory)
                                if bundle_file.startswith(
                                    str(selected_card_data.art_id)
                                )
                                and bundle_file.endswith(".mtga")
                            ][0]

                            # Load the Unity asset bundle
                            unity_environment = load_unity_bundle(
                                os.path.join(
                                    asset_bundle_directory, matching_bundle_files
                                )
                            )
                            texture_index = 0

                            # Get card textures and process them for display
                            image_data_list, texture_data_list = get_card_texture_data(
                                selected_card_data,
                                database_file_path,
                            )

                            if texture_data_list:
                                card_textures = texture_data_list
                                display_texture_bytes = convert_texture_to_bytes(
                                    image_data_list[texture_index]
                                )

                                texture_width, texture_height = texture_data_list[
                                    texture_index
                                ].image.size
                            else:
                                # Handle case where no textures are found
                                card_textures = None
                                display_texture_bytes = None
                                sg.popup_error("No textures found for selected card!")
                                continue
                            selected_card_data.image = image_data_list[0]
                        except:
                            sg.popup_error("Failed to load card image!")
                        selected_card_data.image = image_data_list[0]
                        card_editor_window["-CARD_IMAGE-"].update(
                            source=convert_texture_to_bytes(selected_card_data.image)
                        )

                    # Handle image replacement
                    if editor_event == "-CHANGE_IMAGE-":
                        new_image_path = open_file_dialog(
                            "Select your new image", "image files", "*.png"
                        )
                        if new_image_path not in ("", None):
                            # Create backup of original image
                            backup_image_path = f"{os.path.join(image_save_directory, selected_card_data.name.replace('/', '-'))}-{str(texture_index)}-{texture_width}x{texture_height}_backup{randint(1, 1000)}.png"
                            save_image_to_file(
                                texture_data_list[texture_index].image,
                                backup_image_path,
                                editor_values["-REMOVE_ALPHA-"],
                            )

                            # Replace the texture with new image
                            texture_data = extract_textures_from_bundle(
                                unity_environment
                            )[texture_index]
                            replace_texture_in_bundle(
                                texture_data,
                                new_image_path,
                                os.path.join(
                                    asset_bundle_directory, matching_bundle_files
                                ),
                                unity_environment,
                            )
                            display_texture_bytes = convert_texture_to_bytes(
                                texture_data.image
                            )

                            # Update display with new image
                            card_editor_window["-CARD_IMAGE-"].update(
                                source=display_texture_bytes
                            )
                            selected_card_data.image = texture_data.image
                            sg.popup_auto_close(
                                "Image changed successfully!", auto_close_duration=1
                            )
                        else:
                            sg.popup_error("Invalid image file", auto_close_duration=1)

                    # Handle alpha channel removal
                    if editor_event == "-REMOVE_ALPHA-":
                        processed_image = remove_alpha_channel(
                            texture_data_list[texture_index].image,
                            editor_values["-REMOVE_ALPHA-"],
                        )
                        display_texture_bytes = convert_texture_to_bytes(
                            processed_image
                        )
                        card_editor_window["-CARD_IMAGE-"].update(
                            source=display_texture_bytes
                        )
                        selected_card_data.image = processed_image

                    # Handle image saving
                    if editor_event == "-SAVE_IMAGE-":
                        save_path = f"{os.path.join(image_save_directory, selected_card_data.name.replace('/', '-'))}-{str(texture_index)}-{texture_width}x{texture_height}.png"
                        save_image_to_file(
                            selected_card_data.image,
                            save_path,
                            editor_values["-REMOVE_ALPHA-"],
                        )
                        sg.popup_auto_close(
                            "Image saved successfully!", auto_close_duration=1
                        )

                    # Handle image upscaling
                    if editor_event == "-UPSCALE_IMAGE-" and is_upscaling_available:
                        current_width, current_height = card_textures[
                            texture_index
                        ].image.size
                        upscaled_image = upscale_card_image(
                            io.BytesIO(display_texture_bytes),
                            current_width,
                            current_height,
                        )

                        # Resize for display if too large
                        display_image = resize_image_to_screen(upscaled_image)
                        display_texture_bytes = convert_texture_to_bytes(display_image)
                        card_editor_window["-CARD_IMAGE-"].update(
                            source=display_texture_bytes
                        )
                        selected_card_data.image = upscaled_image

                        # Update dimensions
                        texture_width, texture_height = upscaled_image.size

                    # Handle aspect ratio adjustment
                    if editor_event == "-SET_ASPECT_RATIO-":
                        try:
                            resized_image, new_width, new_height = (
                                adjust_image_aspect_ratio(
                                    display_texture_bytes,
                                    (
                                        float(editor_values["-ASPECT_WIDTH-"]),
                                        float(editor_values["-ASPECT_HEIGHT-"]),
                                    ),
                                )
                            )
                            display_texture_bytes = convert_texture_to_bytes(
                                resized_image
                            )
                            card_editor_window["-CARD_IMAGE-"].update(
                                source=display_texture_bytes
                            )
                            texture_width, texture_height = new_width, new_height
                            selected_card_data.image = resized_image
                        except ValueError:
                            sg.popup_error(
                                "Invalid aspect ratio values, edit them before applying",
                                auto_close_duration=3,
                            )

                    # Handle setting cards for swapping
                    if editor_event == "-SET_SWAP_1-":
                        first_card_to_swap = selected_card_data

                    if editor_event == "-SET_SWAP_2-":
                        second_card_to_swap = selected_card_data

                card_editor_window.close()

            else:
                sg.popup_error("Invalid texture file", auto_close_duration=1)

        except IndexError as e:
            sg.popup_error(
                "Card not working at the moment" + str(e), auto_close_duration=2
            )
            continue

# Close the main window when the event loop ends

main_window.close()
