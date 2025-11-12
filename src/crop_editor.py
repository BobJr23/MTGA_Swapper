# Crop Editor for MTGA Art Crop Database
# Allows viewing and editing art crop values for cards
#
# The Art Crop Database (Raw_ArtCropDatabase*.mtga) is an SQLite database with a Crops table
# Table structure:
#   CREATE TABLE Crops(
#       Path TEXT NOT NULL,
#       Format TEXT NOT NULL,
#       X REAL NOT NULL,
#       Y REAL NOT NULL,
#       Z REAL NOT NULL,
#       W REAL NOT NULL,
#       Generated INTEGER NOT NULL,
#       PRIMARY KEY (Path, Format)
#   )
#
# Example entries:
#   Path: Assets/Core/CardArt/001000/001155_AIF
#   Format: Normal, X: 1.0, Y: 0.9035433, Z: 0.0, W: 0.04822835, Generated: 1
#
# Features:
# - Search for cards by name to find their ArtIds
# - Filter crop entries by ArtId (the ArtId appears in the path)
# - Edit crop values (X, Y, Z, W), format type, and generated flag
# - Changes are saved directly to the SQLite database
# - Commit or rollback changes as needed
#
# Usage:
#   from src.crop_editor import create_crop_editor_window
#   create_crop_editor_window(database_file_path, database_cursor)

import os
import sqlite3
import FreeSimpleGUI as sg
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class ArtCropData:
    """Represents a single art crop entry from the Crops table."""

    def __init__(
        self,
        path: str,
        format_type: str,
        x: float,
        y: float,
        z: float,
        w: float,
        generated: int,
        row_id: Optional[int] = None,
    ):
        self.path = path
        self.format_type = format_type
        self.x = x
        self.y = y
        self.z = z
        self.w = w
        self.generated = generated
        self.row_id = row_id  # For tracking which row to update
        self.original_path = path  # Store original for PRIMARY KEY updates
        self.original_format = format_type

    def to_tuple(self) -> Tuple:
        """Convert to tuple for database operations."""
        return (
            self.path,
            self.format_type,
            self.x,
            self.y,
            self.z,
            self.w,
            self.generated,
        )

    def __repr__(self):
        return f"ArtCropData({self.path}, {self.format_type}, {self.x}, {self.y}, {self.z}, {self.w}, {self.generated})"


def load_art_crop_database(
    crop_db_path: str,
) -> Tuple[List[ArtCropData], sqlite3.Connection, sqlite3.Cursor]:
    """
    Load the Raw_ArtCropDatabase SQLite file and return all crop entries.

    Args:
        crop_db_path: Path to the Raw_ArtCropDatabase SQLite file

    Returns:
        Tuple of (List of ArtCropData objects, connection, cursor)
    """
    crop_data = []

    try:
        conn = sqlite3.connect(crop_db_path)
        cursor = conn.cursor()

        # Query all rows from the Crops table
        cursor.execute("SELECT Path, Format, X, Y, Z, W, Generated FROM Crops")
        rows = cursor.fetchall()

        for row in rows:
            crop_entry = ArtCropData(
                path=row[0],
                format_type=row[1],
                x=row[2],
                y=row[3],
                z=row[4],
                w=row[5],
                generated=row[6],
            )
            crop_data.append(crop_entry)

        return crop_data, conn, cursor

    except Exception as e:
        print(f"Error loading art crop database: {e}")
        sg.popup_error(f"Failed to load art crop database: {e}", title="Load Error")
        return [], None, None


def update_crop_entry(
    cursor: sqlite3.Cursor, entry: ArtCropData, commit: bool = False
) -> bool:
    """
    Update a single crop entry in the database.

    Args:
        cursor: Database cursor
        entry: ArtCropData object with updated values
        commit: Whether to commit the transaction

    Returns:
        True if successful, False otherwise
    """
    try:
        # Since (Path, Format) is PRIMARY KEY, we need to delete and insert if they changed
        # Otherwise we can just UPDATE
        if (
            entry.path != entry.original_path
            or entry.format_type != entry.original_format
        ):
            # Delete old entry
            cursor.execute(
                "DELETE FROM Crops WHERE Path = ? AND Format = ?",
                (entry.original_path, entry.original_format),
            )
            # Insert new entry
            cursor.execute(
                "INSERT INTO Crops (Path, Format, X, Y, Z, W, Generated) VALUES (?, ?, ?, ?, ?, ?, ?)",
                entry.to_tuple(),
            )
        else:
            # Update existing entry
            cursor.execute(
                "UPDATE Crops SET X = ?, Y = ?, Z = ?, W = ?, Generated = ? WHERE Path = ? AND Format = ?",
                (
                    entry.x,
                    entry.y,
                    entry.z,
                    entry.w,
                    entry.generated,
                    entry.path,
                    entry.format_type,
                ),
            )

        if commit:
            cursor.connection.commit()

        # Update original values
        entry.original_path = entry.path
        entry.original_format = entry.format_type

        return True

    except Exception as e:
        print(f"Error updating crop entry: {e}")
        sg.popup_error(f"Failed to update crop entry: {e}", title="Update Error")
        return False


def find_art_id_by_card_name(
    card_name: str, database_cursor: sqlite3.Cursor
) -> List[Tuple[str, str]]:
    """
    Search for cards by name and return their ArtIds.

    Args:
        card_name: Name (or partial name) to search for
        database_cursor: SQLite cursor for the card database

    Returns:
        List of tuples (card_name, art_id)
    """
    try:
        # Search in the Cards table with the TitleId linked to Localizations
        query = """
            SELECT DISTINCT c.ArtId, l.Loc
            FROM Cards c
            LEFT JOIN Localizations_enUS l ON c.TitleId = l.LocId
            WHERE l.Loc LIKE ? OR c.Order_Title LIKE ?
        """

        search_pattern = f"%{card_name}%"
        database_cursor.execute(query, (search_pattern, search_pattern))
        results = database_cursor.fetchall()

        return [(str(art_id), name) for art_id, name in results if art_id]

    except Exception as e:
        print(f"Error searching for card: {e}")
        return []


def filter_crops_by_art_id(
    crop_data: List[ArtCropData], art_id: str
) -> List[ArtCropData]:
    """
    Filter crop entries that contain the given ArtId in their path.

    Args:
        crop_data: List of all crop data
        art_id: ArtId to search for

    Returns:
        Filtered list of crop entries
    """
    return [entry for entry in crop_data if art_id.zfill(6) in entry.path]


def create_crop_editor_window(
    database_file_path: str, database_cursor: sqlite3.Cursor
) -> None:
    """
    Create and display the crop editor window.

    Args:
        database_file_path: Path to the Raw_CardDatabase file
        database_cursor: SQLite cursor for querying card data
    """
    # Determine the crop database path
    db_dir = os.path.dirname(database_file_path)
    crop_db_path = None

    # Look for Raw_ArtCropDatabase file in the same directory
    for file in os.listdir(db_dir):
        if file.startswith("Raw_ArtCropDatabase") and file.endswith(".mtga"):
            crop_db_path = os.path.join(db_dir, file)
            break

    if not crop_db_path or not os.path.exists(crop_db_path):
        sg.popup_error(
            "Could not find Raw_ArtCropDatabase file in the same directory as Raw_CardDatabase",
            title="File Not Found",
        )
        return

    # Load the crop database
    crop_data, crop_conn, crop_cursor = load_art_crop_database(crop_db_path)

    if not crop_data or crop_conn is None:
        sg.popup_error(
            "No crop data loaded. The database might be empty or corrupt.",
            title="Load Error",
        )
        return

    # Keep track of filtered results
    filtered_crops = crop_data.copy()
    current_art_id = None

    # Define the layout
    search_frame = [
        [
            sg.Text("Search Card Name:", size=(15, 1)),
            sg.Input(key="-SEARCH_CARD-", size=(30, 1), enable_events=True),
        ],
        [
            sg.Text("Found Cards:", size=(15, 1)),
            sg.Listbox(
                values=[],
                key="-CARD_RESULTS-",
                size=(50, 5),
                enable_events=True,
            ),
        ],
    ]

    crop_table_headings = ["Path", "Format", "X", "Y", "Z", "W", "Generated"]

    crop_frame = [
        [
            sg.Table(
                values=[],
                headings=crop_table_headings,
                key="-CROP_TABLE-",
                auto_size_columns=False,
                col_widths=[40, 10, 8, 8, 8, 8, 8],
                num_rows=15,
                justification="left",
                enable_events=True,
                select_mode=sg.TABLE_SELECT_MODE_BROWSE,
            )
        ],
        [
            sg.Text(f"Total Entries: {len(crop_data)}", key="-TOTAL_COUNT-"),
            sg.Text("", key="-FILTERED_COUNT-", size=(30, 1)),
        ],
    ]

    edit_frame = [
        [sg.Text("Edit Selected Crop Entry", font=("Arial", 12, "bold"))],
        [sg.Text("Path:"), sg.Text("", key="-EDIT_PATH-", size=(60, 1))],
        [sg.Text("Format:"), sg.Input("", key="-EDIT_FORMAT-", size=(15, 1))],
        [
            sg.Text("X:"),
            sg.Input("", key="-EDIT_X-", size=(10, 1)),
            sg.Text("Y:"),
            sg.Input("", key="-EDIT_Y-", size=(10, 1)),
            sg.Text("Z:"),
            sg.Input("", key="-EDIT_Z-", size=(10, 1)),
            sg.Text("W:"),
            sg.Input("", key="-EDIT_W-", size=(10, 1)),
        ],
        [sg.Text("Generated:"), sg.Input("", key="-EDIT_GENERATED-", size=(10, 1))],
        [
            sg.Button("Save Changes", key="-SAVE_EDIT-"),
            sg.Button("Revert", key="-REVERT_EDIT-"),
        ],
    ]

    layout = [
        [sg.Frame("Search", search_frame, expand_x=True)],
        [sg.Frame("Crop Entries", crop_frame, expand_x=True)],
        [sg.Frame("Edit Entry", edit_frame, expand_x=True)],
        [
            sg.Button("Save Database", key="-SAVE_DB-"),
            sg.Button("Reload Database", key="-RELOAD_DB-"),
            sg.Button("Close", key="-CLOSE-"),
        ],
    ]

    window = sg.Window(
        "Art Crop Editor", layout, modal=True, resizable=True, finalize=True
    )

    # Track the currently selected entry
    selected_entry_index = None

    def update_crop_table(entries: List[ArtCropData]):
        """Update the crop table with the given entries."""
        table_data = [
            [e.path, e.format_type, e.x, e.y, e.z, e.w, e.generated] for e in entries
        ]
        window["-CROP_TABLE-"].update(values=table_data)
        window["-FILTERED_COUNT-"].update(f"Showing: {len(entries)} entries")

    def clear_edit_fields():
        """Clear all edit fields."""
        window["-EDIT_PATH-"].update("")
        window["-EDIT_FORMAT-"].update("")
        window["-EDIT_X-"].update("")
        window["-EDIT_Y-"].update("")
        window["-EDIT_Z-"].update("")
        window["-EDIT_W-"].update("")
        window["-EDIT_GENERATED-"].update("")

    def load_entry_to_edit(entry: ArtCropData):
        """Load an entry into the edit fields."""
        window["-EDIT_PATH-"].update(entry.path)
        window["-EDIT_FORMAT-"].update(entry.format_type)
        window["-EDIT_X-"].update(str(entry.x))
        window["-EDIT_Y-"].update(str(entry.y))
        window["-EDIT_Z-"].update(str(entry.z))
        window["-EDIT_W-"].update(str(entry.w))
        window["-EDIT_GENERATED-"].update(str(entry.generated))

    # Initial display of all entries
    update_crop_table(filtered_crops)

    # Event loop
    while True:
        event, values = window.read()

        if event in (sg.WIN_CLOSED, "-CLOSE-"):
            break

        if event == "-SEARCH_CARD-":
            search_term = values["-SEARCH_CARD-"].strip()

            if not search_term:
                continue

            # Search for cards
            results = find_art_id_by_card_name(search_term, database_cursor)

            if results:
                # Display results as "CardName (ArtId)"
                display_results = [
                    f"{name} (ArtId: {art_id})" for art_id, name in results
                ]
                window["-CARD_RESULTS-"].update(values=display_results)
            else:
                window["-CARD_RESULTS-"].update(values=[])
                sg.popup_error(
                    f"No cards found matching '{search_term}'", title="Search"
                )

        if event == "-CARD_RESULTS-":
            # User selected a card from the search results
            if values["-CARD_RESULTS-"]:
                selected = values["-CARD_RESULTS-"][0]
                # Extract ArtId from the display string
                art_id = selected.split("(ArtId: ")[1].rstrip(")")
                current_art_id = art_id

                # Filter crop data by this ArtId
                filtered_crops = filter_crops_by_art_id(crop_data, art_id)
                update_crop_table(filtered_crops)
                clear_edit_fields()

                if not filtered_crops:
                    sg.popup_error(
                        f"No crop entries found for ArtId {art_id}", title="No Results"
                    )

        if event == "-CROP_TABLE-":
            # User selected a row in the crop table
            if values["-CROP_TABLE-"]:
                selected_row = values["-CROP_TABLE-"][0]
                if 0 <= selected_row < len(filtered_crops):
                    selected_entry_index = selected_row
                    load_entry_to_edit(filtered_crops[selected_row])

        if event == "-SAVE_EDIT-":
            # Save the edited values back to the entry
            if selected_entry_index is not None and 0 <= selected_entry_index < len(
                filtered_crops
            ):
                try:
                    entry = filtered_crops[selected_entry_index]

                    # Update the entry with new values
                    entry.format_type = values["-EDIT_FORMAT-"]
                    entry.x = float(values["-EDIT_X-"])
                    entry.y = float(values["-EDIT_Y-"])
                    entry.z = float(values["-EDIT_Z-"])
                    entry.w = float(values["-EDIT_W-"])
                    entry.generated = int(values["-EDIT_GENERATED-"])

                    # Update in the database (without committing yet)
                    if update_crop_entry(crop_cursor, entry, commit=False):
                        # Update the display
                        update_crop_table(filtered_crops)

                        sg.popup_ok(
                            "Entry updated! Click 'Save Database' to commit changes to file.",
                            auto_close=True,
                            auto_close_duration=2,
                        )
                    else:
                        sg.popup_error(
                            "Failed to update entry in database", title="Update Error"
                        )

                except ValueError as e:
                    sg.popup_error(
                        f"Invalid values entered: {e}", title="Validation Error"
                    )
            else:
                sg.popup_error(
                    "Please select an entry from the table first", title="No Selection"
                )

        if event == "-REVERT_EDIT-":
            # Reload the selected entry
            if selected_entry_index is not None and 0 <= selected_entry_index < len(
                filtered_crops
            ):
                load_entry_to_edit(filtered_crops[selected_entry_index])
            else:
                clear_edit_fields()

        if event == "-SAVE_DB-":
            # Commit all changes to the database file
            if (
                sg.popup_yes_no(
                    "Commit all changes to the Art Crop Database file?",
                    title="Confirm Save",
                )
                == "Yes"
            ):
                try:
                    crop_conn.commit()
                    sg.popup_ok(
                        "Database saved successfully!",
                        auto_close=True,
                        auto_close_duration=2,
                    )
                except Exception as e:
                    sg.popup_error(f"Failed to save database: {e}", title="Save Error")

        if event == "-RELOAD_DB-":
            # Reload the database from file
            if (
                sg.popup_yes_no(
                    "Reload database from file? Any unsaved changes will be lost.",
                    title="Confirm Reload",
                )
                == "Yes"
            ):
                # Close current connection and reload
                crop_conn.rollback()  # Discard any uncommitted changes
                crop_conn.close()

                crop_data, crop_conn, crop_cursor = load_art_crop_database(crop_db_path)
                filtered_crops = crop_data.copy()
                update_crop_table(filtered_crops)
                clear_edit_fields()
                selected_entry_index = None
                window["-TOTAL_COUNT-"].update(f"Total Entries: {len(crop_data)}")
                sg.popup_ok("Database reloaded", auto_close=True, auto_close_duration=1)

    # Clean up: close database connection
    if crop_conn:
        crop_conn.close()

    window.close()


if __name__ == "__main__":
    # For testing purposes
    print(
        "Crop Editor module loaded. Use create_crop_editor_window() to open the editor."
    )
