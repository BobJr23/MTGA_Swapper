# Database management module for MTGA card database operations
# Handles SQLite operations for card swapping and data retrieval

import sqlite3
from typing import List, Tuple
from src.load_preset import (
    save_grp_id_info,
    change_grp_id,
    save_loc_id_info,
    json,
    find_mtga_db_path,
)


def get_tokens_by_artist(
    artist_name: str, database_cursor: sqlite3.Cursor
) -> List[Tuple[str, str]]:
    """
    Retrieve tokens from the database by artist name.

    Args:
        artist_name: The name of the artist to search for
        database_cursor: SQLite database cursor

    Returns:
        A list of tuples containing card information (name, artist) for matching tokens
    """
    database_cursor.execute(
        """
        SELECT ArtistCredit,ArtId FROM Cards WHERE Rarity=0 AND ArtistCredit LIKE ?
        """,
        (f"%{artist_name}%",),
    )
    return database_cursor.fetchall()


def swap_card_group_ids(
    first_grp_id: str,
    second_grp_id: str,
    database_cursor: sqlite3.Cursor,
    database_connection: sqlite3.Connection,
    save_path: str = "",
    asset_bundle_path: str = "",
) -> None:
    """
    Swap the GrpId values between two cards in the database.
    Uses a temporary value (0 and 1) to avoid constraint conflicts.

    Args:
        first_grp_id: Group ID of the first card to swap
        second_grp_id: Group ID of the second card to swap
        database_cursor: SQLite database cursor
        database_connection: SQLite database connection
    """
    try:
        # First pass: Set cards to temporary values to avoid conflicts
        database_cursor.executemany(
            """
        UPDATE Cards
        SET GrpId = ? 
        WHERE GrpId = ?
        
        """,
            [(0, first_grp_id), (1, second_grp_id)],
        )

        # Second pass: Set cards to their final swapped values
        database_cursor.executemany(
            """
        UPDATE Cards
        SET GrpId = ? 
        WHERE GrpId = ?
        
        """,
            [(second_grp_id, 0), (first_grp_id, 1)],
        )
        save_grp_id_info(
            [first_grp_id, second_grp_id],
            save_path,
            database_cursor,
            database_connection,
            asset_bundle_path,
        )
    except sqlite3.OperationalError:
        print("You used the wrong file, relaunch this program and try again")
        exit()
    database_connection.commit()


def swap_card_styles(
    first_grp_id: str,
    second_grp_id: str,
    database_cursor: sqlite3.Cursor,
    database_connection: sqlite3.Connection,
    save_path: str = "",
    asset_bundle_path: str = "",
) -> None:
    """
    Swap the ArtID and tag values between two cards in the database for styles.
    Uses a temporary value (0 and 1) to avoid constraint conflicts.

    Args:
        first_grp_id: Group ID of the first card to swap
        second_grp_id: Group ID of the second card to swap
        database_cursor: SQLite database cursor
        database_connection: SQLite database connection
    """
    try:
        # First pass: Get first card's tags and ArtId
        first_card_data = database_cursor.execute(
            """
                SELECT tags, ArtId FROM Cards WHERE GrpId = ?
            """,
            (first_grp_id,),
        ).fetchone()
        first_card_tags, first_card_art_id = (
            first_card_data if first_card_data else ("", "")
        )

        # Copy tags and ArtId from second card to first card
        database_cursor.execute(
            """
                UPDATE Cards 
                SET tags = (SELECT tags FROM Cards WHERE GrpId = ?),
                    ArtId = (SELECT ArtId FROM Cards WHERE GrpId = ?)
                WHERE GrpId = ?
            """,
            (second_grp_id, second_grp_id, first_grp_id),
        )
        # Set second card's tags and ArtId to first card's values
        database_cursor.execute(
            """
                UPDATE Cards
                SET tags = ?,
                    ArtId = ?
                WHERE GrpId = ?
            """,
            (first_card_tags, first_card_art_id, second_grp_id),
        )
        save_grp_id_info(
            [first_grp_id, second_grp_id],
            save_path,
            database_cursor,
            database_connection,
            asset_bundle_path,
        )

    except sqlite3.OperationalError:
        print("You used the wrong file, relaunch this program and try again")
        exit()
    database_connection.commit()


def unlock_parallax_style(
    card_ids: List[str],
    database_cursor: sqlite3.Cursor,
    database_connection: sqlite3.Connection,
    save_path: str = "",
    asset_bundle_path: str = "",
) -> None:
    """
    Unlock the parallax style for a list of card IDs.

    Args:
        card_ids: List of card IDs to unlock
        database_cursor: SQLite database cursor
    """
    try:
        print(card_ids)
        database_cursor.executemany(
            """
        UPDATE Cards
        SET tags = CASE
            WHEN tags IS NULL OR TRIM(tags) = '' THEN '1696804317'
            ELSE tags || ',1696804317'
        END
        WHERE GrpId = ? AND tags NOT LIKE '%1696804317%'
        """,
            [(card_id,) for card_id in card_ids],
        )
        database_cursor.connection.commit()
        save_grp_id_info(
            card_ids, save_path, database_cursor, database_connection, asset_bundle_path
        )
        return True

    except sqlite3.OperationalError:
        return False


def get_card_details_by_name(
    card_name: str, database_cursor: sqlite3.Cursor
) -> List[Tuple]:
    """
    Retrieve card details (GrpID, ArtId, ExpansionCode) by card name.

    Args:
        card_name: Name of the card to search for
        database_cursor: SQLite database cursor

    Returns:
        List of tuples containing card details
    """
    query_result = database_cursor.execute(
        f"SELECT GrpID, ArtId, ExpansionCode FROM Cards WHERE Order_Title='{card_name}'"
    )

    return query_result.fetchall()


def create_database_connection(
    database_file_path: str,
) -> Tuple[sqlite3.Cursor, sqlite3.Connection, str]:
    """
    Create a connection to the MTGA SQLite database.

    Args:
        database_file_path: Path to the .mtga database file

    Returns:
        Tuple of (cursor, connection, file_path)
    """
    database_connection = sqlite3.connect(database_file_path)
    database_cursor = database_connection.cursor()

    return database_cursor, database_connection, database_file_path


def fetch_all_data(database_cursor: sqlite3.Cursor, grp_id: str) -> List[Tuple]:
    """
    Fetch all data from the Cards table for a specific GrpId.

    Args:
        database_cursor: SQLite database cursor

    Returns:
        List of tuples containing all rows from the Cards table
    """
    database_cursor.execute("SELECT * FROM Cards WHERE GrpId=?", (grp_id,))
    column_names = [description[0] for description in database_cursor.description]

    # Fetch all results and format with column names
    row = database_cursor.fetchone()

    if row:
        row_dict = {col_name: value for col_name, value in zip(column_names, row)}
    else:
        return {}
    return row_dict


def get_localization_from_id(
    database_cursor: sqlite3.Cursor, loc_id, language: str = "enUS"
) -> str:
    """
    Retrieve localized text from the LocalizedText table by LocId and language.

    Args:
        database_cursor: SQLite database cursor
        loc_id: The LocId to search for
        language: The language code (default is "enUS")

    Returns:
        The localized text if found, otherwise an empty string
    """
    database_cursor.execute(
        f"SELECT Loc FROM Localizations_{language} WHERE LocId=?",
        (str(loc_id),),
    )
    result = database_cursor.fetchone()
    return result[0] if result else ""


def set_localization_from_id(
    database_cursor: sqlite3.Cursor, loc_id: str, new_text: str, language: str = "enUS"
) -> None:
    """
    Update localized text in the Localizations table by LocId and language.

    Args:
        database_cursor: SQLite database cursor
        loc_id: The LocId to search for
        new_text: The new localized text to set
    """
    database_cursor.execute(
        f"UPDATE Localizations_{language} SET Loc=? WHERE LocId=?",
        (new_text, loc_id),
    )
    database_cursor.connection.commit()


# Debug/testing code (commented out for production)
# if __name__ == "__main__":
#     cur, con, f = create_database_connection()
#     name = input("enter a card name to find grp id\n > ")
#     n = get_card_details_by_name(name.lower(), cur)
#     for x in n:
#         print(x)
