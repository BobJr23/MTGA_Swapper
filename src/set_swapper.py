""" "Adapted from https://github.com/Bassiuz/MTGA-Arena-Set-Swapper, check his project out!"""

# fmt: off
import time
import json
import shutil
import os
import csv
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import requests
import UnityPy
from PIL import Image
import FreeSimpleGUI as sg
from src.load_preset import save_grp_id_info


def fetch_scryfall_set_data(set_code: str) -> List[Dict]:
    """Fetches all card data for a given set from Scryfall."""
    all_cards = []
    next_page_url = f"https://api.scryfall.com/cards/search?q=set:{set_code}"
    while next_page_url:
        try:
            response = requests.get(next_page_url)
            response.raise_for_status()
            data = response.json()
            all_cards.extend(data.get("data", []))
            next_page_url = data.get("next_page")
            time.sleep(0.1)  # Be nice to the API
        except requests.exceptions.RequestException:
            return []

    return all_cards


def generate_swap_file(
    source_set_code: str, target_set_code: str, output_path: Path
) -> bool:
    """
    Generates a swaps.json file by matching cards between a source and target set using their Oracle ID.

    Args:
        source_set_code: The set code to swap from (e.g., 'om1')
        target_set_code: The set code to swap to (e.g., 'spm')
        output_path: Path where the swaps.json file should be saved

    Returns:
        True if successful, False otherwise
    """
    # 1. Fetch data for both sets
    source_cards = fetch_scryfall_set_data(source_set_code)
    target_cards = fetch_scryfall_set_data(target_set_code)

    if not source_cards or not target_cards:
        return False

    # 2. Create maps from Oracle ID to card data for efficient matching
    source_map_by_oracle = {
        card["oracle_id"]: card for card in source_cards if "oracle_id" in card
    }
    target_map_by_oracle = {
        card["oracle_id"]: card for card in target_cards if "oracle_id" in card
    }

    # 3. Find common Oracle IDs and generate swap entries
    swaps_to_generate = []
    common_oracle_ids = set(source_map_by_oracle.keys()) & set(
        target_map_by_oracle.keys()
    )

    for oracle_id in sorted(common_oracle_ids):
        source_card = source_map_by_oracle[oracle_id]
        target_card = target_map_by_oracle[oracle_id]

        source_name = source_card.get("printed_name", target_card.get("name"))
        target_name = target_card.get("printed_name", target_card.get("name"))

        expansion_code = source_card.get("set", "").upper()
        collector_number = source_card.get("collector_number")
        target_api_url = target_card.get("uri")

        if not all([source_name, expansion_code, collector_number, target_api_url]):
            continue

        swaps_to_generate.append(
            {
                "source_card_name": target_name,
                "target_card_name": source_name,
                "expansion_code": expansion_code,
                "collector_number": collector_number,
                "target_api_url": target_api_url,
            }
        )

    if not swaps_to_generate:
        return False

    # Save swaps.json to specified path
    try:
        with open(output_path, "w") as f:
            json.dump(swaps_to_generate, f, indent=4)
        return True
    except IOError:
        return False


def get_card_data_from_url(url: str) -> Optional[Dict]:
    """Fetches card data from a Scryfall URL."""
    api_url = url
    if "scryfall.com/card" in api_url:
        parts = api_url.split("/")
        if len(parts) > 6:
            api_url = "/".join(parts[:-1])

    try:
        response = requests.get(api_url)
        response.raise_for_status()
        return response.json()
    except (requests.exceptions.RequestException, json.JSONDecodeError):
        return None


def download_image(url: str, dest_path: Path) -> bool:
    """Downloads an image from a URL to a destination path."""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(response.raw, f)
        return True
    except requests.exceptions.RequestException:
        return False


def get_card_and_art_ids_from_db(
    db_cursor, swaps: List[Dict]
) -> Dict[str, Tuple[int, int]]:
    """
    Retrieves MTGA card IDs (GrpId) and Art IDs using ExpansionCode and CollectorNumber.

    Args:
        db_cursor: SQLite cursor for the MTGA database
        swaps: List of swap dictionaries

    Returns:
        Dictionary mapping card names to (GrpId, ArtId) tuples
    """
    card_data = {}

    for swap in swaps:
        source_name = swap.get("source_card_name")
        exp_code = swap.get("expansion_code")
        coll_num = swap.get("collector_number")

        if not all([source_name, exp_code, coll_num]):
            continue

        try:
            query = "SELECT GrpId, ArtId FROM cards WHERE ExpansionCode = ? AND CollectorNumber = ?"
            db_cursor.execute(query, (exp_code, str(coll_num)))
            result = db_cursor.fetchone()
            if result:
                card_data[source_name] = (result[0], result[1])
        except Exception:
            continue

    return card_data

def find_asset_bundles(
    asset_bundle_dir: Path, card_id: int, art_id: int
) -> Path:
    """Finds the asset bundles containing a card's art and data."""
    card_art_bundle = None

    if not asset_bundle_dir.exists():
        return None

    matching_files = [
                filename
                for filename in os.listdir(asset_bundle_dir)
                if filename.startswith(str(art_id))
                and filename.endswith(".mtga")
            ]

    if not matching_files:
        return None

    card_art_bundle = asset_bundle_dir / matching_files[0]

    return card_art_bundle


def perform_image_swap( image_uris, target_type_line, temp_dir,
                        card_id, asset_bundle_dir, art_id ):
    if not image_uris:
        return None, None

    is_saga = "Saga" in target_type_line

    if is_saga:
        image_url = image_uris.get("png")
    else:
        image_url = image_uris.get("art_crop")

    if not image_url:
        return None, None

    image_path = temp_dir / f"{card_id}.png"

    if not download_image(image_url, image_path):
        return None, None

    art_bundle_path = find_asset_bundles(
        asset_bundle_dir, card_id, art_id
    )

    # Replace art
    env_art = UnityPy.load(str(art_bundle_path))
    all_textures = [
        obj for obj in env_art.objects if obj.type.name == "Texture2D"
    ]

    if all_textures:
        all_textures.sort(
            key=lambda x: (
                x.read().m_Width * x.read().m_Height
                if hasattr(x.read(), "m_Width")
                else 0
            ),
            reverse=True,
        )
        main_art_texture_obj = all_textures[0]
        main_art_texture = main_art_texture_obj.read()

        img = Image.open(image_path)

        if is_saga:
            original_width, original_height = img.size

            # Crop vertically in half (take right side)
            crop_left = original_width // 2
            crop_right = original_width

            # Crop some off top and bottom (adjust these percentages as needed)
            top_crop_percent = 0.12
            bottom_crop_percent = 0.17
            right_crop_percent = 0.92

            crop_top = int(original_height * top_crop_percent)
            crop_bottom = int(original_height * (1 - bottom_crop_percent))
            crop_right = int(original_width * right_crop_percent)

            # Perform the crop: (left, top, right, bottom)
            img = img.crop((crop_left, crop_top, crop_right, crop_bottom))
            img = img.resize((256, 512), Image.LANCZOS)

        main_art_texture.image = img
        main_art_texture.save()

        with open(art_bundle_path, "wb") as f:
            f.write(env_art.file.save())

    return art_bundle_path, env_art


def perform_set_swap(
    swaps_file_path: Path,
    db_cursor,
    db_connection,
    asset_bundle_dir: Path,
    backup_dir: Path,
    save_path: Optional[Path] = None,
) -> bool:
    """
    Main function to perform all card swaps defined in a swaps.json file.

    Args:
        swaps_file_path: Path to the swaps.json file
        db_cursor: SQLite cursor for the MTGA database
        db_connection: SQLite connection for the MTGA database
        asset_bundle_dir: Path to the AssetBundle directory
        backup_dir: Path where backups should be stored

    Returns:
        True if successful, False otherwise
    """
    try:
        with open(swaps_file_path, "r") as f:
            swaps_config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return False

    card_data_map = get_card_and_art_ids_from_db(db_cursor, swaps_config)

    if not card_data_map:
        return False

    temp_dir = Path("./temp_art")
    temp_dir.mkdir(exist_ok=True)
    backup_dir.mkdir(exist_ok=True)

    try:
        for swap in swaps_config:
            source_name = swap["source_card_name"]
            target_name = swap["target_card_name"]
            if source_name not in card_data_map:
                continue

            card_id, art_id = card_data_map[source_name]

            target_url = swap.get("target_api_url") or swap.get("target_scryfall_url")
            if not target_url:
                continue

            target_data = get_card_data_from_url(target_url)
            if not target_data:
                continue

            target_type_line = target_data.get("type_line", "")

            image_uris = target_data.get("image_uris", {})
            image_uris_list = []

            if image_uris:
                image_uris_list.append(image_uris)
            else:
                for face in target_data.get("card_faces", []):
                    image_uris_list.append(face.get("image_uris", {}))


            for idx, image_uris_entry in enumerate(image_uris_list):
                if idx == 1:
                  db_cursor.execute(
                      "SELECT GrpId, ArtId FROM Cards WHERE LinkedFaceGrpIds = ?", (card_id,)
                  )
                  result = db_cursor.fetchone()
                  card_id = result[0]
                  art_id = result[1]

                art_bundle_path, env_art = perform_image_swap(
                  image_uris_entry,
                  target_type_line,
                  temp_dir,
                  card_id,
                  asset_bundle_dir,
                  art_id,
                )

            if not art_bundle_path or not env_art:
              continue

            # Replace name in TextAsset

            with open(art_bundle_path, "wb") as f:
                f.write(env_art.file.save())

            # Backup the NEW asset file after changes
            shutil.copy(art_bundle_path, backup_dir / f"MOD_{art_bundle_path.name}")

            # Update name in database localizations
            try:
                # Get TitleId for this card

                db_cursor.execute(
                    "SELECT TitleId, InterchangeableTitleId FROM Cards WHERE GrpId = ?", (card_id,)
                )
                result = db_cursor.fetchone()
                if result:
                    title_id = result[0]
                    interchangeable_title_id = result[1]
                    # Update Localizations_enUS table
                    db_cursor.execute(
                        "UPDATE Localizations_enUS SET Loc = ? WHERE LocId = ?",
                        (source_name, title_id),
                    )
                    # Set Loc of InterchangeableTitleId to the old card's name
                    if interchangeable_title_id:
                        db_cursor.execute(
                            "UPDATE Localizations_enUS SET Loc = ? WHERE LocId = ?",
                            (target_name, interchangeable_title_id),
                        )
                    db_connection.commit()
                else:
                    print(f"No TitleId found for GrpId {card_id}")
            except Exception:
                print("Error updating localizations")
                pass
        
    finally:
        id_list = [ids[0] for ids in card_data_map.values()]
        save_grp_id_info(id_list, save_path, db_cursor, db_connection, asset_bundle_dir)
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
    return True


def create_set_swap_window():
    """Creates a window for set swapping functionality."""
    layout = [
        [sg.Text("Set Swapper", font=("Helvetica", 16, "bold"))],
        [
            sg.Text(
                "Swap entire sets of cards between different Magic sets (Includes art and names at the moment)"
            )
        ],
        [
            sg.Text(
                "Huge thanks to Bassiuz, his script can be found at https://github.com/Bassiuz/MTGA-Arena-Set-Swapper"
            )
        ],
        [sg.HorizontalSeparator()],
        [sg.Text("Step 1: Generate Swap File", font=("Helvetica", 12, "bold"))],
        [
            sg.Text("Source Set Code:"),
            sg.Input(key="-SOURCE_SET-", size=(10, 1), default_text="om1"),
        ],
        [
            sg.Text("Target Set Code:"),
            sg.Input(key="-TARGET_SET-", size=(10, 1), default_text="spm"),
        ],
        [sg.Button("Generate Swap File", key="-GENERATE_SWAPS-")],
        [sg.HorizontalSeparator()],
        [sg.Text("Step 2: Apply Swaps", font=("Helvetica", 12, "bold"))],
        [
            sg.Text("Swap File:"),
            sg.Input(key="-SWAP_FILE-", size=(40, 1)),
            sg.FileBrowse(file_types=(("JSON Files", "*.json"),)),
        ],
        [
            sg.Button("Apply Swaps", key="-APPLY_SWAPS-"),
            sg.Button("Close", key="-CLOSE-"),
        ],
        [sg.Button("Swap Spiderman descriptions", key="-SPIDERMAN-")],
    ]

    return sg.Window("Set Swapper", layout, modal=True, finalize=True)


def spiderman_localizations(
    db_cursor, db_connection, csv_file_path: Optional[str] = None
) -> bool:
    """
    Apply localization changes from TempLocalizations.csv for Spider-Man themed swaps.

    CSV format expected (semicolon-delimited):
    LocId;Formatted;Loc
    12345;1;Spider-Man Card Name
    67890;0;Another Card Name

    Args:
        db_cursor: SQLite cursor for the MTGA database
        db_connection: SQLite connection for the MTGA database
        csv_file_path: Optional path to the CSV file. Defaults to './TempLocalizations.csv'

    Returns:
        True if successful, False otherwise
    """
    if csv_file_path is None:
        csv_file_path = Path("./TempLocalizations.csv")

    if not Path(csv_file_path).exists():
        sg.popup_error(
            f"CSV file not found: {csv_file_path}", title="Localization Error"
        )
        return False

    try:
        updated_count = 0

        with open(csv_file_path, "r", encoding="utf-8") as csvfile:
            # Use semicolon as delimiter
            csv_reader = csv.DictReader(csvfile, delimiter=";")

            # Validate headers
            if (
                "LocId" not in csv_reader.fieldnames
                or "Loc" not in csv_reader.fieldnames
            ):
                sg.popup_error(
                    "CSV file must have 'LocId', 'Formatted', and 'Loc' columns",
                    title="Invalid CSV Format",
                )
                return False

            for row in csv_reader:
                loc_id = row.get("LocId", "").strip()
                formatted = row.get("Formatted", "").strip()
                new_text = row.get("Loc", "").strip()

                if not loc_id or not new_text:
                    continue

                # Only use formatted text (Formatted == 1)
                if formatted != "1":
                    continue

                try:
                    # Convert LocId to integer
                    loc_id_int = int(loc_id)

                    # Update the localization in the database
                    db_cursor.execute(
                        "UPDATE Localizations_enUS SET Loc = ? WHERE LocId = ?",
                        (new_text, loc_id_int),
                    )

                    if db_cursor.rowcount > 0:
                        updated_count += 1

                except (ValueError, Exception) as e:
                    # Skip invalid entries
                    print("invalid")
                    continue
        db_cursor.execute(
            """
            UPDATE Localizations_enUS
            SET Loc = 'When Flash Thompson enters, choose one or both — 
            • Tap target creature. 
            • Untap target creature.'
            WHERE LocId = 1086483
            """
        )

        # Commit all changes
        db_connection.commit()

        if updated_count > 0:
            sg.popup_ok(
                f"Successfully updated {updated_count} localization entries!",
                title="Localization Complete",
            )
            return True
        else:
            sg.popup_warning(
                "No localization entries were updated. Check your CSV file.",
                title="No Updates",
            )
            return False

    except Exception as e:
        sg.popup_error(
            f"Error processing localizations: {e}", title="Localization Error"
        )
        return False
