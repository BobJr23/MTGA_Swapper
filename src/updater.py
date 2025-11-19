import os
import sys
import tempfile
import requests
import hashlib
import subprocess
import FreeSimpleGUI as sg

# Configure these
UPDATE_METADATA_URL = (
    "https://raw.githubusercontent.com/BobJr23/MTGA_Swapper/main/update.json"
)
MAIN_EXE_NAME = "MTGA_Swapper.exe"
NO_UPSCALE_EXE_NAME = "MTGA_Swapper_NoUpscale.exe"


def get_local_version(path):
    # Read version from local update.json
    try:
        import json

        with open(path, "r") as f:
            data = json.load(f)
            return data.get("version")
    except Exception:
        return None


def get_remote_info():
    r = requests.get(UPDATE_METADATA_URL, timeout=10)
    r.raise_for_status()
    return r.json()


def download_file(url, target_path):
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(target_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)


def sha256_of_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def replace_executable(new_path, dest_path):
    # On Windows, you can't overwrite a running exe. Strategies:
    # - Use a temporary file and schedule replacement after exit
    # - Or use MoveFileEx with MOVEFILE_DELAY_UNTIL_REBOOT (less ideal)
    # Simpler approach: rename old exe, put new exe in place.
    try:
        backup = dest_path + ".old"
        if os.path.exists(backup):
            os.remove(backup)
        os.rename(dest_path, backup)

    except FileNotFoundError:
        print("File not found, skipping rename.")
    os.rename(new_path, dest_path)

    # Optionally remove backup later
    # os.remove(backup)


def choose_variant():
    """Prompt user to choose between upscale and no_upscale version using GUI."""
    layout = [
        [sg.Text("Update Available!", font=("Arial", 14), justification="center")],
        [sg.Text("Choose which version to install:", font=("Arial", 12))],
        [sg.Text("")],
        [
            sg.Radio(
                "Standard (with upscaling)",
                "VARIANT",
                key="upscale",
                default=True,
                font=("Arial", 10),
            )
        ],
        [
            sg.Radio(
                "No Upscale (smaller download)",
                "VARIANT",
                key="no_upscale",
                font=("Arial", 10),
            )
        ],
        [sg.Text("")],
        [sg.Button("Install", size=(10, 1)), sg.Button("Cancel", size=(10, 1))],
    ]

    window = sg.Window("MTGA Swapper Update", layout, modal=True, finalize=True)

    while True:
        event, values = window.read()

        if event in (sg.WIN_CLOSED, "Cancel"):
            window.close()
            return None

        if event == "Install":
            if values["upscale"]:
                window.close()
                return "upscale"
            elif values["no_upscale"]:
                window.close()
                return "no_upscale"

    window.close()
    return None


def run_main_exe(variant):
    # Launch the main exe
    print("Launching new application...")
    subprocess.Popen(
        [NO_UPSCALE_EXE_NAME]
        if variant == "no_upscale"
        else [MAIN_EXE_NAME] + sys.argv[1:]
    )
    # Exit the launcher
    print("Exiting updater...")
    sys.exit(0)


def main(path):
    local_ver = get_local_version(path)
    try:
        info = get_remote_info()
    except Exception as e:
        sg.popup_error(f"Failed to fetch update info: {e}", title="Update Check Failed")
        return False

    remote_ver = info.get("version")
    downloads = info.get("downloads", {})

    if local_ver != remote_ver:
        # Let user choose variant
        variant = choose_variant()

        # User cancelled

        variant_info = downloads.get(variant)
        if not variant_info:

            return False
        url = variant_info.get("url")
        expected_checksum = variant_info.get("checksum")

        if url is None:
            sg.popup_error("Error: No download URL found.", title="Update Error")
            sys.exit(1)

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".exe")
        tmp_path = tmp.name
        tmp.close()

        try:
            # Show download progress window

            download_file(url, tmp_path)
            actual = sha256_of_file(tmp_path)
            if expected_checksum and actual.lower() != expected_checksum.lower():
                raise ValueError("Checksum mismatch")

            replace_executable(
                tmp_path, MAIN_EXE_NAME if variant == "upscale" else NO_UPSCALE_EXE_NAME
            )

            # Update local update.json with new version info
            import json

            with open(path, "w") as f:
                json.dump(info, f, indent=2)

            if (
                sg.popup_yes_no(
                    f"Update successful!\nUpdated from {local_ver} → {remote_ver}. Would you like to see the changes from this update? \n\nRestart the application to launch.",
                )
                == "Yes"
            ):
                # Show changes
                import webbrowser

                webbrowser.open(
                    "https://github.com/BobJr23/MTGA_Swapper/releases/latest"
                )

        except Exception as e:
            sg.popup_error(f"Update failed: {e}", title="Update Error")
            # Could fallback: run existing version, or abort
            # Optionally clean up tmp file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            if (
                sg.popup_yes_no(
                    "Would you like to download the update manually from the website?",
                    title="Manual Download",
                )
                == "Yes"
            ):
                import webbrowser

                webbrowser.open(
                    "https://github.com/BobJr23/MTGA_Swapper/releases/latest"
                )
            else:
                pass

        # Finally launch the main exe
        # run_main_exe(variant)

        return True

    return False


if __name__ == "__main__":
    main()
