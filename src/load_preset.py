import json
import sqlite3
from pathlib import Path


def get_grp_id_info(
    grp_id: list[str], user_save_changes_path: str, cursor, connection
) -> None:
    """
    Load the saved changes for a specific GrpId from the user's save changes file.

    Args:
        grp_id: The Group ID of the card to load changes for
        user_save_changes_path: Path to the user's save changes JSON file

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
    formatted_results = {}

    for row in rows:
        # Create a dictionary for this row with column names as keys
        row_dict = {col_name: value for col_name, value in zip(column_names, row)}

        # Extract GrpId as the main key
        grp_id_value = row_dict.pop(
            "GrpId"
        )  # Remove GrpId from the dict and get its value

        # Use GrpId as the key, and the remaining columns as the value
        formatted_results[grp_id_value] = row_dict
    connection.commit()
    with open(user_save_changes_path, "w") as output_file:
        json.dump(formatted_results, output_file)
    output_file.close()


def change_grp_id(
    change_path: str, cursor, connection, json_manual: dict | None = None
) -> None:
    if json_manual:
        grp_id = json_manual.pop("GrpId")

        # Update the database with the new values for the specified GrpId
        set_values = ", ".join([f"{col} = ?" for col in json_manual.keys()])
        cursor.execute(
            f"UPDATE Cards SET {set_values} WHERE GrpId = ?",
            list(json_manual.values()) + [grp_id],
        )
    else:
        with open(change_path, "r") as changes_file:
            changes_data = json.load(changes_file)

        for grp_id, new_values in changes_data.items():
            # Update the database with the new values for the specified GrpId
            set_values = ", ".join([f"{col} = ?" for col in new_values.keys()])
            cursor.execute(
                f"UPDATE Cards SET {set_values} WHERE GrpId = ?",
                list(new_values.values()) + [grp_id],
            )

    connection.commit()


if __name__ == "__main__":
    user_config_directory = Path.home() / ".mtga_swapper"
    user_config_directory.mkdir(exist_ok=True)
    db_path = "PATH_TO_YOUR_MTGA_DATABASE_FILE"  # Update this path to your actual MTGA database file for testing
    changes_path = user_config_directory / "changes.json"

    if not changes_path.exists():
        with open("changes.json", "r") as source_config:
            with open(changes_path, "w") as destination_config:
                destination_config.write(source_config.read())

    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    # save changes
    # grp_ids = ["100119", "100118"]
    # result = get_grp_id_info(grp_ids, changes_path, cursor, connection)
    # with open("output.json", "w") as output_file:
    #     json.dump(result, output_file)

    # load changes
    # change_grp_id("output.json", cursor, connection)
