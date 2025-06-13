import sql_editor
import asset_viewer
import FreeSimpleGUI as sg
import os
from tkinter import Tk
from tkinter.filedialog import askopenfilename, askdirectory
import io
from upscaler import upscale_image
from pathlib import Path

sg.theme("DarkBlue3")


class Card:
    def __init__(self, name, set_code, art_type, grp_id, art_id):
        self.name = name
        self.set_code = set_code
        self.art_type = art_type
        self.grp_id = grp_id
        self.art_id = art_id

    def __str__(self):
        return self.name


def format_card(card_tuple):

    name, set_code, art_type, grp_id, art_id = card_tuple
    return f"{name:<30} {set_code:<10} {art_type:<9} {grp_id:<8} {art_id:<8}"


def sort_cards(cards, key):
    index_map = {"Name": 0, "Set": 1, "ArtType": 2, "GrpID": 3, "ArtID": 4}
    return sorted(cards, key=lambda x: x.split()[index_map[key]])


def get_file(title, desc, types):
    Tk().withdraw()
    file = askopenfilename(filetypes=[(desc, types)], title=title)
    return Path(file).as_posix() if file else None


def get_dir(title):
    Tk().withdraw()
    return Path(askdirectory(title=title)).as_posix()


def pil_to_bytes(img):
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="PNG")
    return img_byte_arr.getvalue()


# Load config

if (
    sg.popup_yes_no(
        "Do you want to load from config file?",
        title="Reset Config",
    )
    == "Yes"
):

    with open("config.json", "r") as f:
        config = sg.json.loads(f.read())
        save_dir = config["SavePath"] if config["SavePath"] else None
        if config["DatabasePath"] != "" and os.path.exists(config["DatabasePath"]):
            filename = config["DatabasePath"]
            cur, con, filename = sql_editor.main(filename)
            base_cards = list(
                map(
                    format_card,
                    sorted(
                        cur.execute(
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
            cards = base_cards
            asset_viewer.set_unity_version(filename, "2022.3.42f1")
        else:
            filename = None
            base_cards = ["Select a database first"]
            cards = ["Select a database first"]
            sg.popup_error(
                "Invalid or missing database file. Please select a valid .mtga file.",
                auto_close_duration=3,
            )
else:
    config = {"SavePath": None, "DatabasePath": None}
    save_dir = None
    filename = None
    base_cards = ["Select a database first"]
    cards = ["Select a database first"]

swap1, swap2 = None, None
current_input = ""

layout = [
    [
        sg.Frame(
            "",
            [
                [
                    sg.Button(
                        "Select database file & image save location",
                        key="-DB-",
                        size=(35, 1),
                        pad=(5, 5),
                    ),
                    sg.Button("Swap Arts", key="-SA-", size=(15, 1), pad=(5, 5)),
                ],
                [
                    sg.Button(
                        (
                            "Select database and image save location before changing sleeves and avatars"
                            if filename is None
                            else "Change Sleeves, Avatars, etc."
                        ),
                        key="-Sleeve-",
                        disabled=filename is None,
                        size=(60, 1),
                        pad=(5, 5),
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
                        "Search by card name (Format: Name, Set, ArtType, GrpID, ArtID)",
                        justification="left",
                    )
                ],
                [sg.Input(size=(40, 1), enable_events=True, key="-INPUT-", pad=(5, 5))],
                [
                    sg.Text("Sort by:"),
                    sg.Combo(
                        ["Name", "Set", "ArtType", "GrpID", "ArtID"],
                        default_value="Name",
                        key="-SORTBY-",
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
                        cards,
                        size=(70, 20),
                        enable_events=True,
                        key="-LIST-",
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

window = sg.Window(
    "MTGA Swapper",
    layout,
    grab_anywhere=True,
    finalize=True,
    font=("Segoe UI", 10),
    element_justification="center",
    background_color="#1B2838",
)

# Main Event Loop
while True:
    event, values = window.read()
    if event in (sg.WIN_CLOSED, "Exit"):
        break

    if event == "-SORTBY-":
        selected_sort = values["-SORTBY-"]
        sorted_cards = sort_cards(window["-LIST-"].Values or base_cards, selected_sort)
        window["-LIST-"].update(sorted_cards)

    if event == "-DB-":
        cur, con, filename = sql_editor.main(
            get_file(
                "Select your Raw_CardDatabase mtga file in Raw Folder",
                "mtga files",
                "*.mtga",
            )
        )
        try:
            base_cards = list(
                map(
                    format_card,
                    sorted(
                        cur.execute(
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
            cards = base_cards
        except sql_editor.sqlite3.OperationalError:
            sg.popup_error(
                "Missing or incorrect database selected", auto_close_duration=3
            )
        save_dir = get_dir("Select a folder to save images to")
        with open("config.json", "w") as f:
            config["SavePath"] = str(Path(save_dir).as_posix())
            config["DatabasePath"] = str(Path(filename).as_posix())
            f.write(sg.json.dumps(config))
        asset_viewer.set_unity_version(filename, "2022.3.42f1")
        window["-LIST-"].update(base_cards)
        window["-Sleeve-"].update("Change Sleeves, Avatars, etc.", disabled=False)

    if event == "-Sleeve-":
        if filename and save_dir:
            print()
            path = os.path.dirname(filename)[0:-3] + "AssetBundle"
            files = sorted(
                [
                    f
                    for f in os.listdir(path)
                    if not any(["CardArt" in f, f.startswith("Bucket_Card.Sleeve")])
                ]
            )
            window3 = sg.Window(
                "Select a file to change the sleeve/avatar of",
                [
                    [sg.Text("Search for files by type")],
                    [sg.Input(size=(20, 1), enable_events=True, key="-INPUT3-")],
                    [
                        sg.Listbox(
                            files, size=(50, 40), enable_events=True, key="-LIST3-"
                        )
                    ],
                ],
                modal=True,
                grab_anywhere=True,
                relative_location=(0, 0),
                finalize=True,
            )
            while True:
                event3, values3 = window3.read()
                if event3 == "Exit" or event3 == sg.WIN_CLOSED:
                    break
                if event3 == "-LIST3-" and len(values3["-LIST3-"]):
                    name = values3["-LIST3-"][0]

                    env = asset_viewer.load(os.path.join(path, name))
                    data_list = asset_viewer.get_texture(env)
                    index = 0
                    data = data_list[0] if len(data_list) > 0 else None
                    if data != None:
                        img_byte_arr = io.BytesIO()
                        data.image.save(img_byte_arr, format="PNG")

                        window4 = sg.Window(
                            "Showing: " + name + " Art",
                            [
                                [
                                    sg.Button("Change image", key="-CI-"),
                                    sg.Button("Previous in bundle", key="-L-"),
                                    sg.Button("Next in bundle", key="-R-"),
                                    sg.Button("Save", key="-SAVE-"),
                                    sg.Button("Close", key="Exit"),
                                ],
                                [
                                    sg.Image(
                                        data=img_byte_arr.getvalue(),
                                        key="-IMAGE-",
                                    )
                                ],
                            ],
                            modal=True,
                            grab_anywhere=True,
                            location=(0, 0),
                            finalize=True,
                        )

                        while True:
                            e, _ = window4.read()
                            if e == "Exit" or e == sg.WIN_CLOSED:
                                break
                            if e == "-L-":
                                index -= 1
                                if index < 0:
                                    index = len(data_list) - 1
                                data = data_list[index]
                                if data != None:
                                    img_byte_arr = io.BytesIO()
                                    data.image.save(img_byte_arr, format="PNG")
                                    window4["-IMAGE-"].update(
                                        data=img_byte_arr.getvalue()
                                    )
                            if e == "-R-":
                                index += 1
                                if index >= len(data_list):
                                    index = 0
                                data = data_list[index]
                                if data != None:
                                    img_byte_arr = io.BytesIO()
                                    data.image.save(img_byte_arr, format="PNG")
                                    window4["-IMAGE-"].update(
                                        data=img_byte_arr.getvalue()
                                    )
                            if e == "-CI-":
                                new = get_file(
                                    "Select your new image", "image files", "*.png"
                                )
                                if new != "":
                                    asset_viewer.save_image(
                                        data, new, os.path.join(path, name), env
                                    )
                                    window4["-IMAGE-"].update(filename=new)
                                    sg.popup_auto_close(
                                        "Image changed successfully!",
                                        auto_close_duration=1,
                                    )
                                else:
                                    sg.popup_error(
                                        "Invalid image file",
                                        auto_close_duration=1,
                                    )
                            if e == "-SAVE-":
                                new_path = (
                                    os.path.join(save_dir, name)
                                    + "-"
                                    + str(index)
                                    + ".png"
                                )
                                asset_viewer.open_image(data.image, new_path)
                                sg.popup_auto_close(
                                    "Image saved successfully!",
                                    auto_close_duration=1,
                                )
                    else:
                        sg.popup_error(
                            "Invalid texture file",
                            auto_close_duration=1,
                        )
                if values3["-INPUT3-"] != "":  # if a keystroke entered in search field
                    if values3["-INPUT3-"] != current_input:
                        current_input = values3["-INPUT3-"]
                        search = values3["-INPUT3-"]
                        new_values = [
                            x for x in files if search.lower() in x.lower()
                        ]  # do the filtering
                        window3["-LIST3-"].update(new_values)
                else:
                    # display original unfiltered list
                    if current_input != "":
                        window3["-LIST3-"].update(files)
                        current_input = ""

        else:
            sg.popup_error(
                "You haven't selected a database and/or save location",
                auto_close_duration=3,
            )

    if event == "-SA-":

        # Prepare images for swap1 and swap2 if available

        img1 = (
            pil_to_bytes(asset_viewer.get_card_textures(swap1, filename)[0][0])
            if swap1
            else None
        )

        img2 = (
            pil_to_bytes(asset_viewer.get_card_textures(swap2, filename)[0][0])
            if swap2
            else None
        )

        layout_swap = [
            [sg.Text("You are about to swap the following cards:")],
            [
                sg.Column(
                    [
                        [sg.Text("Swap 1:")],
                        [
                            sg.Text(
                                str(swap1) if swap1 else "Not selected",
                                font=("Courier New", 10),
                            )
                        ],
                        [sg.Image(img1, subsample=2) if img1 else sg.Text("No image")],
                    ]
                ),
                sg.Column(
                    [
                        [sg.Text("Swap 2:")],
                        [
                            sg.Text(
                                str(swap2) if swap2 else "Not selected",
                                font=("Courier New", 10),
                            )
                        ],
                        [sg.Image(img2, subsample=2) if img2 else sg.Text("No image")],
                    ]
                ),
            ],
            [
                sg.Button(
                    "Confirm Swap",
                    key="-CONFIRM-",
                    disabled=swap1 is None or swap2 is None,
                ),
                sg.Button("Cancel", key="-CANCEL-"),
            ],
        ]
        window_swap = sg.Window("Confirm Swap", layout_swap, modal=True, finalize=True)
        while True:
            e_swap, _ = window_swap.read()
            if e_swap in (sg.WIN_CLOSED, "-CANCEL-"):
                window_swap.close()
                break
            if e_swap == "-CONFIRM-" and swap1 and swap2:
                sql_editor.swap_values(swap1.grp_id, swap2.grp_id, cur, con)
                sg.popup_ok("Swapped successfully!", auto_close_duration=2)
                window_swap.close()
                break

    if values["-INPUT-"] != "":
        if values["-INPUT-"] != current_input:
            current_input = values["-INPUT-"].replace(" ", "").lower()
            search = current_input

            new_values = [x for x in base_cards if search in x.lower()]

            window["-LIST-"].update(new_values)
    else:
        if current_input != "":
            window["-LIST-"].update(base_cards)
            current_input = ""

    if event == "-LIST-" and values["-LIST-"]:
        current_card = Card(
            *values["-LIST-"][0].split(),
        )
        path = os.path.dirname(filename)[0:-3] + "AssetBundle"

        try:
            prefixed = [
                f
                for f in os.listdir(path)
                if f.startswith(str(current_card.art_id)) and f.endswith(".mtga")
            ][0]

            env = asset_viewer.load(os.path.join(path, prefixed))
            index = 0
            textures, data_list = asset_viewer.get_card_textures(current_card, filename)
            data = asset_viewer.get_image_from_texture(textures[index])
            # Get resolution of the image
            w, h = data_list[index].image.size
            if textures != None:
                # img_byte_arr = io.BytesIO()
                # data.save(img_byte_arr, format="PNG")

                window4 = sg.Window(
                    "Showing: " + current_card.name + " Art",
                    [
                        [
                            sg.Button("Change image", key="-CI-"),
                            (
                                sg.Button("Previous in bundle", key="-L-")
                                if len(textures) > 1
                                else sg.Text("")
                            ),
                            (
                                sg.Button("Next in bundle", key="-R-")
                                if len(textures) > 1
                                else sg.Text("")
                            ),
                            sg.Button("Set to Swap 1", key="-S1-"),
                            sg.Button("Set to Swap 2", key="-S2-"),
                            sg.Button("Set aspect ratio to", key="-AR-"),
                            sg.Input(
                                "3" if current_card.art_type == "1" else "11",
                                key="-AR-W-",
                                size=(3, 1),
                            ),
                            sg.Input(
                                "4" if current_card.art_type == "1" else "8",
                                key="-AR-H-",
                                size=(3, 1),
                            ),
                            sg.Button("Save", key="-SAVE-"),
                            sg.Button("Upscale", key="-UPSCALE-"),
                            sg.Button("Close", key="-EXIT-"),
                        ],
                        [
                            sg.Image(
                                data=asset_viewer.get_image_from_texture(
                                    textures[index]
                                ),
                                key="-IMAGE-",
                            )
                        ],
                    ],
                    modal=True,
                    grab_anywhere=True,
                    relative_location=(0, 0),
                    finalize=True,
                )

                while True:
                    e, values = window4.read()
                    if e == "-EXIT-" or e == sg.WIN_CLOSED:
                        break

                    if e in ("-L-", "-R-"):
                        index += 1 if e == "-R-" else -1
                        if index >= len(textures):
                            index = 0
                        if index < 0:
                            index = len(textures) - 1

                        window4["-IMAGE-"].update(
                            data=asset_viewer.get_image_from_texture(textures[index])
                        )

                        data = asset_viewer.get_image_from_texture(textures[index])

                    if e == "-CI-":
                        new = get_file("Select your new image", "image files", "*.png")
                        if new != "":
                            asset_viewer.save_image(
                                data_list[index],
                                new,
                                os.path.join(path, prefixed),
                                env,
                            )
                            window4["-IMAGE-"].update(filename=new)
                            sg.popup_auto_close(
                                "Image changed successfully!",
                                auto_close_duration=1,
                            )
                        else:
                            sg.popup_error(
                                "Invalid image file",
                                auto_close_duration=1,
                            )
                    if e == "-SAVE-":
                        new_path = f"{os.path.join(save_dir,current_card.name.replace('/', '-'))}-{str(index)}-{w}x{h}.png"
                        asset_viewer.open_image(data, new_path)
                        sg.popup_auto_close(
                            "Image saved successfully!",
                            auto_close_duration=1,
                        )
                    if e == "-UPSCALE-":
                        upped = upscale_image(
                            io.BytesIO(data),
                        )
                        img_byte_arr = io.BytesIO()
                        shrunk = asset_viewer.shrink_to_monitor(upped)
                        shrunk.save(img_byte_arr, format="PNG")

                        window4["-IMAGE-"].update(data=img_byte_arr.getvalue())
                        new_arr = io.BytesIO()
                        upped.save(new_arr, format="PNG")
                        data = new_arr.getvalue()
                        w, h = upped.size

                    if e == "-S1-":
                        swap1 = current_card

                    if e == "-S2-":
                        swap2 = current_card

                    if e == "-AR-":
                        img_byte_arr = io.BytesIO()
                        resized, w, h = asset_viewer.set_aspect_ratio(
                            data,
                            (
                                float(values["-AR-W-"]),
                                float(values["-AR-H-"]),
                            ),
                        )
                        resized.save(img_byte_arr, format="PNG")

                        window4["-IMAGE-"].update(data=img_byte_arr.getvalue())
                        data = img_byte_arr.getvalue()

            else:
                sg.popup_error(
                    "Invalid texture file",
                    auto_close_duration=1,
                )

        except IndexError:
            sg.popup_error(
                "Card not working at the moment",
                auto_close_duration=2,
            )
            continue

window.close()
