# Decklist import and parsing module
# Handles importing card lists from MTGA format text or plain text files

import FreeSimpleGUI as sg
import re
from typing import Set, Optional


def create_decklist_import_window() -> Optional[Set[str]]:
    """
    Create a GUI window for importing and parsing decklists.
    Supports both MTGA Arena format and plain text format.

    Returns:
        Set of normalized card names from the imported decklist
    """
    imported_cards = None

    # Define the GUI layout for the decklist import window
    decklist_window_layout = [
        [
            sg.Text(
                "Paste a decklist in MTGA format below: \nEx:\n\nDeck\n20 Forest\n3 Llanowar Elves\n\nor upload cards separated by a new line from .txt file\nNote: Cards with Aftermath require ///, while other dual cards use //"
            ),
        ],
        [sg.Checkbox("MTG Arena format", default=True, key="-MTGA_FORMAT-")],
        [
            sg.Multiline(
                size=(40, 20), key="-DECKLIST_TEXT-", expand_x=True, expand_y=True
            )
        ],
        [
            sg.Button("Load from .txt file", key="-LOAD_FILE-"),
            sg.Button("Save and Exit", key="Exit"),
        ],
    ]

    # Create the decklist import window
    decklist_window = sg.Window(
        "Decklist Manager",
        decklist_window_layout,
        resizable=True,
        grab_anywhere=True,
    )

    # Main event loop for the decklist window
    while True:
        event, values = decklist_window.read()

        # Handle window close or exit button
        if event == sg.WIN_CLOSED or event == "Exit":
            try:
                # Parse the decklist text into individual lines
                raw_card_lines = values["-DECKLIST_TEXT-"].strip().split("\n")
            except AttributeError:
                break

            # Process cards based on selected format
            if values["-MTGA_FORMAT-"]:
                # Filter lines that start with numbers (MTGA format: "4 Lightning Bolt")
                numbered_card_lines = list(
                    filter(
                        lambda line: line != "" and line[0] in "123456789",
                        raw_card_lines,
                    )
                )

                # Convert MTGA format to database-friendly format
                imported_cards = set(
                    map(
                        lambda line: normalize_card_name_for_database(
                            "".join(line.split("(")[0].split(" ")[1:]).strip().lower()
                        )[
                            :15
                        ],  # Take first 15 characters for matching
                        numbered_card_lines,
                    )
                )

                sg.popup_quick_message(
                    "Deck imported successfully!", auto_close_duration=1
                )
            else:
                # Process as plain text format (one card per line)
                imported_cards = set(
                    map(
                        lambda line: normalize_card_name_for_database(
                            line.strip().lower()
                        )[:15],
                        filter(lambda line: line != "", raw_card_lines),
                    )
                )
                print(imported_cards)
                sg.popup_quick_message(
                    "Deck imported successfully!", auto_close_duration=1
                )
            break

        # Handle loading decklist from file
        elif event == "-LOAD_FILE-":
            selected_filename = sg.popup_get_file(
                "Select a .txt file containing your decklist",
                file_types=(("Text Files", "*.txt"),),
            )
            if selected_filename:
                try:
                    # Read the file content and populate the text area
                    with open(
                        selected_filename, "r", encoding="utf-8"
                    ) as decklist_file:
                        file_content = decklist_file.read()
                        decklist_window["-DECKLIST_TEXT-"].update(file_content)
                        sg.popup_quick_message(
                            "File loaded successfully!", auto_close_duration=1
                        )
                    # Switch to plain text format when loading from file
                    decklist_window["-MTGA_FORMAT-"].update(value=False)
                except Exception as file_error:
                    sg.popup_error(f"Error loading file: {file_error}")

    decklist_window.close()
    return imported_cards


def normalize_card_name_for_database(card_name_text: str) -> str:
    """
    Normalize a card name for database matching by removing special characters.

    Args:
        card_name_text: Raw card name text

    Returns:
        Normalized card name with only alphanumeric characters and slashes
    """
    return re.sub(r"[^a-zA-Z0-9/]", "", card_name_text)

def create_search_tokens_window(database_cursor) -> sg.Window:
    """
    Create the search tokens window.

    Returns:
        The search tokens window instance.
    """
    layout = [
        [sg.Text("Search Tokens by Artist Name", font=("Segoe UI", 12))],
        [sg.InputText(key="-SEARCH_INPUT-", size=(40, 1))],
        [sg.Button("Search", key="-SEARCH_BUTTON-")],
        [sg.Listbox(values=[], key="-RESULT_LIST-", size=(40, 10), enable_events=True)],
        [sg.Button("Cancel", key="-CANCEL_BUTTON-")],

    ]
    window = sg.Window("Search Tokens", layout, modal=True)
    

    return window

