import sql_editor
import asset_viewer
import FreeSimpleGUI as sg
import os
from tkinter import Tk
from tkinter.filedialog import askopenfilename, askdirectory
import io

# list fonts available


sg.theme("DarkBlue3")  # Modern dark theme


def format_card(card_tuple):

    name, set_code, art_type, grp_id, art_id = card_tuple
    return f"{name:<25} {set_code:<10} {art_type:<9} {grp_id:<8} {art_id:<8}"


def sort_cards(cards, key):
    index_map = {"Name": 0, "Set": 1, "ArtType": 2, "GrpID": 3, "ArtID": 4}
    return sorted(cards, key=lambda x: x.split()[index_map[key]])


def get_file(title, desc, types):
    Tk().withdraw()
    file = askopenfilename(filetypes=[(desc, types)], title=title)
    return file


def get_dir(title):
    Tk().withdraw()
    return askdirectory(title=title)


# Load config
with open("config.json", "r") as f:
    config = sg.json.loads(f.read())
    save_dir = config["SavePath"] if config["SavePath"] else None
    if config["DatabasePath"] != "":
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
        WHEN c1.Order_Title IS NULL AND c2.Order_Title IS NOT NULL THEN CONCAT(c2.Order_Title, '-flip-side')
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
                        f"{'Name':<25} {'Set':<7} {'ArtType':<12} {'GrpID':<8} {'ArtID':<8}",
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
                            "SELECT Order_Title, ExpansionCode, ArtSize, GrpID, ArtID FROM Cards WHERE Order_Title IS NOT NULL"
                        ).fetchall()
                    ),
                )
            )
        except sql_editor.sqlite3.OperationalError:
            sg.popup_error(
                "Missing or incorrect database selected", auto_close_duration=3
            )
        save_dir = get_dir("Select a folder to save images to")
        with open("config.json", "w") as f:
            config["SavePath"] = save_dir
            config["DatabasePath"] = filename
            f.write(sg.json.dumps(config))
        asset_viewer.set_unity_version(filename, "2022.3.42f1")
        window["-LIST-"].update(base_cards)
        window["-Sleeve-"].update("Change Sleeves, Avatars, etc.", disabled=False)

    if event == "-Sleeve-":
        if filename and save_dir:
            path = os.path.dirname(filename)[0:-3] + r"/AssetBundle"
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
            )
            while True:
                event3, values3 = window3.read()
                if event3 == "Exit" or event3 == sg.WIN_CLOSED:
                    break
                if event3 == "-LIST3-" and len(values3["-LIST3-"]):
                    name = values3["-LIST3-"][0]
                    print(name)

                    env = asset_viewer.load(path + "/" + name)
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
                                        data, new, path + "/" + name, env
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
                                    save_dir + "/" + name + "-" + str(index) + ".png"
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
        if filename and swap1 and swap2:
            sql_editor.swap_values(swap1, swap2, cur, con)
            sg.popup_ok("Swapped successfully!", auto_close_duration=2)
        else:
            sg.popup_error(
                "You haven't selected a database and/or swap cards",
                auto_close_duration=3,
            )

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
        name, mtg_set, art_size, grp, art = (*values["-LIST-"][0].split(),)

        path = os.path.dirname(filename)[0:-3] + "AssetBundle"

        try:
            prefixed = [f for f in os.listdir(path) if f.startswith(str(art))][0]

            env = asset_viewer.load(path + "/" + prefixed)

            data = asset_viewer.get_texture(env)

            index = 0
            data_list = list(map(lambda x: asset_viewer.no_alpha(x.image), data))

            data = data_list[0] if len(data_list) > 0 else None
            if data != None:
                img_byte_arr = io.BytesIO()
                data.save(img_byte_arr, format="PNG")

                window4 = sg.Window(
                    "Showing: " + name + " Art",
                    [
                        [
                            sg.Button("Change image", key="-CI-"),
                            (
                                sg.Button("Previous in bundle", key="-L-")
                                if len(data_list) > 1
                                else sg.Text("")
                            ),
                            (
                                sg.Button("Next in bundle", key="-R-")
                                if len(data_list) > 1
                                else sg.Text("")
                            ),
                            sg.Button("Set to Swap 1", key="-S1-"),
                            sg.Button("Set to Swap 2", key="-S2-"),
                            sg.Button("Set aspect ratio to", key="-AR-"),
                            sg.Input(
                                "3" if art_size == "1" else "11",
                                key="-AR-W-",
                                size=(3, 1),
                            ),
                            sg.Input(
                                "4" if art_size == "1" else "8",
                                key="-AR-H-",
                                size=(3, 1),
                            ),
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
                    relative_location=(0, 0),
                )

                while True:
                    e, values = window4.read()
                    if e == "Exit" or e == sg.WIN_CLOSED:
                        break

                    if e in ("-L-", "-R-"):
                        index += 1 if e == "-R-" else -1
                        if index >= len(data_list):
                            index = 0
                        if index < 0:
                            index = len(data_list) - 1

                        data = data_list[index]
                        if data != None:
                            img_byte_arr = io.BytesIO()
                            data.save(img_byte_arr, format="PNG")
                            window4["-IMAGE-"].update(data=img_byte_arr.getvalue())
                            data = img_byte_arr.getvalue()
                    if e == "-CI-":
                        new = get_file("Select your new image", "image files", "*.png")
                        if new != "":
                            asset_viewer.save_image(data, new, path + "/" + name, env)
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
                            save_dir
                            + "/"
                            + name.replace("/", "-")
                            + "-"
                            + str(index)
                            + ".png"
                        )
                        asset_viewer.open_image(data, new_path)
                        sg.popup_auto_close(
                            "Image saved successfully!",
                            auto_close_duration=1,
                        )
                    if e == "-S1-":
                        swap1 = grp
                        print(swap1, swap2)
                    if e == "-S2-":
                        swap2 = grp
                        print(swap1, swap2)
                    if e == "-AR-":
                        img_byte_arr = io.BytesIO()
                        asset_viewer.set_aspect_ratio(
                            data,
                            (
                                int(values["-AR-W-"]),
                                int(values["-AR-H-"]),
                            ),
                        ).save(img_byte_arr, format="PNG")

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
