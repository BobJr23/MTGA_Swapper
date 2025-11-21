import json
import platform
import sqlite3
from pathlib import Path
import os
import shutil


def save_grp_id_info(
    grp_id: list[str],
    user_save_changes_path: str,
    cursor,
    connection,
    asset_bundle_path: str,
) -> None:
    """
    Save the information of a list of GrpIds to a JSON file.

    Args:
        grp_id: The Group ID of the card to load changes for
        user_save_changes_path: Path to the user's save changes JSON file
        cursor: SQLite database cursor
        connection: SQLite database connection
        asset_bundle_path: Path to the MTGA asset bundle directory

    """
    with open(user_save_changes_path, "r") as changes_file:
        changes_data = json.load(changes_file)
    changes_file.close()
    # Use IN clause with placeholders for multiple GrpIds
    placeholders = ",".join("?" * len(grp_id))
    cursor.execute(f"SELECT * FROM Cards WHERE GrpId IN ({placeholders})", grp_id)

    # Get column names
    column_names = [description[0] for description in cursor.description]

    # Fetch all results and format with column names
    rows = cursor.fetchall()

    for row in rows:
        # Create a dictionary for this row with column names as keys
        row_dict = {col_name: value for col_name, value in zip(column_names, row)}

        # Extract GrpId as the main key
        grp_id_value = row_dict.pop(
            "GrpId"
        )  # Remove GrpId from the dict and get its value

        # Use GrpId as the key, and the remaining columns as the value
        changes_data[grp_id_value] = row_dict

        artid = row_dict.get("ArtId")
        matching_files = [
            filename
            for filename in os.listdir(asset_bundle_path)
            if filename.startswith(str(artid)) and filename.endswith(".mtga")
        ]
        if matching_files:
            shutil.copy(
                os.path.join(asset_bundle_path, matching_files[0]),
                Path.home() / "MTGA_Swapper_Backups" / f"MOD_{matching_files[0]}",
            )

    connection.commit()
    with open(user_save_changes_path, "w") as output_file:
        json.dump(changes_data, output_file, indent=4)
    output_file.close()


def change_grp_id(
    change_path: str,
    cursor,
    connection,
    json_manual: dict | None = None,
    asset_bundle_path: str | None = None,
) -> None:
    print("Applying changes to the database...")
    if json_manual:
        grp_id = json_manual.pop("GrpId")
        localizations = json_manual.pop("Localizations_enUS", None)
        set_values = ", ".join([f"{col} = ?" for col in json_manual.keys()])
        if localizations:
            cursor.executemany(
                f"UPDATE Localizations_enUS SET Loc = ? WHERE LocId = ?",
                [(text, loc_id) for loc_id, text in localizations.items()],
            )

        cursor.execute(
            f"UPDATE Cards SET {set_values} WHERE GrpId = ?",
            list(json_manual.values()) + [grp_id],
        )
    else:
        with open(change_path, "r") as changes_file:
            changes_data = json.load(changes_file)
        changes_file.close()
        available_backups = Path.home() / "MTGA_Swapper_Backups"
        backups = list(available_backups.glob("MOD_*.mtga"))
        backups.sort(key=os.path.getmtime)
        for art in backups:
            matching_files = [
                filename
                for filename in os.listdir(asset_bundle_path)
                if filename.startswith(str(art.name)[4:10])
                and filename.endswith(".mtga")
            ]
            if matching_files:
                shutil.copy(
                    art,
                    os.path.join(asset_bundle_path, matching_files[0]),
                )
        for grp_id, new_values in changes_data.items():

            localizations = new_values.pop("Localizations_enUS", None)
            # Update the database with the new values for the specified GrpId
            set_values = ", ".join([f"{col} = ?" for col in new_values.keys()])
            cursor.execute(
                f"UPDATE Cards SET {set_values} WHERE GrpId = ?",
                list(new_values.values()) + [grp_id],
            )
            if localizations:
                cursor.executemany(
                    f"UPDATE Localizations_enUS SET Loc = ? WHERE LocId = ?",
                    [(text, loc_id) for loc_id, text in localizations.items()],
                )

    connection.commit()


def save_loc_id_info(
    user_save_changes_path: str,
    loc_id: str,
    new_loc: str,
    grp_id: str | None = None,
) -> dict[str, str] | dict:

    with open(user_save_changes_path, "r") as changes_file:
        changes_data = json.load(changes_file)
    changes_file.close()
    changes_data[grp_id].setdefault("Localizations_enUS", {})

    changes_data[grp_id]["Localizations_enUS"][loc_id] = new_loc

    with open(user_save_changes_path, "w") as output_file:
        json.dump(changes_data, output_file, indent=4)
    output_file.close()
    return changes_data


# Credit to Bassiuz for the improved MTGA path detection logic
def get_data_path(mtga_path: Path) -> Path:
    """Gets the correct MTGA_Data path for Windows or macOS."""
    system = platform.system()
    if system == "Darwin" and str(mtga_path).endswith(".app"):
        return mtga_path / "Contents/Resources/Data"

    # For Windows, specifically check if a nested MTGA_Data folder exists
    nested_data_path = mtga_path / "MTGA_Data"
    if system == "Windows" and nested_data_path.exists():
        print(f"   -> Found nested MTGA_Data folder at: {nested_data_path}")
        return nested_data_path

    # Fallback for other structures where Downloads is in the main folder
    return mtga_path


def find_mtga_db_path():
    """Automatically detects the MTG Arena installation path for Windows and macOS."""
    system = platform.system()
    home = Path.home()

    if system == "Windows":
        # List of potential parent directories for the game
        drives = [Path(f"{drive}:/") for drive in "CD" if Path(f"{drive}:/").exists()]
        base_paths = [
            "Program Files/Wizards of the Coast/MTGA",
            "Program Files (x86)/Wizards of the Coast/MTGA",
            "Program Files (x86)/Steam/steamapps/common/MTGA",
            "Program Files/Epic Games/MagicTheGathering",
        ]
        paths_to_check = [drive / path for drive in drives for path in base_paths]
        paths_to_check.append(home / "AppData/Local/Wizards of the Coast/MTGA")

    elif system == "Darwin":  # macOS
        paths_to_check = [
            Path("/Applications/MTGA.app"),
            home / "Library/Application Support/com.wizards.mtga",
            Path("/Library/Application Support/com.wizards.mtga"),
            home / "Applications/MTGA.app",
            Path("/Applications/Epic Games/MagicTheGathering/MTGA.app"),
        ]
    else:
        print(f"Unsupported OS: {system}. Please manually locate the MTGA path.")
        return None

    print("🔍 Searching for MTG Arena installation...")
    for path in paths_to_check:
        if path.exists():
            # Use our new, smarter helper to find the actual data root
            data_root = get_data_path(path)

            asset_bundle_path = data_root / "Downloads/Raw"
            if asset_bundle_path.exists():
                # We return the main installation folder, not the data subfolder
                for file in asset_bundle_path.iterdir():
                    if file.name.startswith("Raw_CardDatabase"):
                        return str(file)

    print("❌ Could not automatically find MTG Arena installation.")
    return None


# if __name__ == "__main__":
#     user_config_directory = Path.home() / ".mtga_swapper"
#     user_config_directory.mkdir(exist_ok=True)
#     db_path = "PATH_TO_YOUR_MTGA_DATABASE_FILE"  # Update this path to your actual MTGA database file for testing
#     changes_path = user_config_directory / "changes.json"

#     if not changes_path.exists():
#         with open("changes.json", "r") as source_config:
#             with open(changes_path, "w") as destination_config:
#                 destination_config.write(source_config.read())

#     connection = sqlite3.connect(db_path)
#     cursor = connection.cursor()


# save changes
# grp_ids = ["100119", "100118"]
# result = get_grp_id_info(grp_ids, changes_path, cursor, connection)
# with open("output.json", "w") as output_file:
#     json.dump(result, output_file)

# load changes
# change_grp_id("output.json", cursor, connection)
