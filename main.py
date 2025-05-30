import sql_editor
import asset_viewer
import FreeSimpleGUI as sg
import os
from tkinter import Tk
from tkinter.filedialog import askopenfilename, askdirectory
import random
import io


def get_file(title, desc, types):
    Tk().withdraw()  # we don't want a full GUI, so keep the root window from appearing
    file = askopenfilename(
        filetypes=[(desc, types)],
        title=title,
    )  # show an "Open" dialog box and return the path to the selected file
    return file


def get_dir(title):
    Tk().withdraw()  # we don't want a full GUI, so keep the root window from appearing
    file = askdirectory(
        title=title,
    )  # show an "Open" dialog box and return the path to the selected file
    return file


with open("config.json", "r") as f:
    config = f.read()
    config = sg.json.loads(config)
    if config["SavePath"] != "":
        save_dir = config["SavePath"]
    else:
        save_dir = None
    if config["DatabasePath"] != "":
        filename = config["DatabasePath"]
        cur, con, filename = sql_editor.main(filename)

        base_cards = cur.execute(
            "SELECT Order_Title, ExpansionCode, ArtSize, GrpID, ArtID FROM Cards WHERE Order_Title IS NOT NULL"
        ).fetchall()
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
        sg.Button("Select database file & image save location", key="-DB-"),
        sg.Button("Swap Arts", key="-SA-"),
        # get details
    ],
    [
        sg.Button(
            (
                "Select database and image save loation before changing sleeves and avatars"
                if filename == None
                else "Change Sleeves, Avatars, etc."
            ),
            key="-Sleeve-",
            disabled=True if filename == None else False,
        )
    ],
    [
        [
            sg.Text(
                "Search for cards by name. The format of the listed cards is: \nName, Set, ArtType (0=normal, 1=planeswalker, 2 = exclusive art lands), GrpID, ArtID"
            )
        ],
        [sg.Input(size=(40, 1), enable_events=True, key="-INPUT-")],
        [sg.Listbox(cards, size=(40, 20), enable_events=True, key="-LIST-")],
    ],
]
window = sg.Window(
    "MTGA Swapper", layout, grab_anywhere=True, background_color="darkblue"
)


while True:  # Event Loop
    event, values = window.read()

    if event == sg.WIN_CLOSED or event == "Exit":
        break
    if event == "-DB-":

        cur, con, filename = sql_editor.main(
            get_file(
                "Select your Raw_CardDatabase mtga file in Raw Folder",
                "mtga files",
                "*.mtga",
            )
        )

        try:
            base_cards = cur.execute(
                "SELECT Order_Title, ExpansionCode, ArtSize, GrpID, ArtID FROM Cards WHERE Order_Title IS NOT NULL"
            ).fetchall()
        except sql_editor.sqlite3.OperationalError:
            sg.popup_error(
                "Missing or incorrect database selected",
                auto_close_duration=3,
            )

        save_dir = get_dir("Select a folder to save images to")

        with open("config.json", "w") as f:
            config["SavePath"] = save_dir
            config["DatabasePath"] = filename
            f.write(sg.json.dumps(config))
        asset_viewer.set_unity_version(filename, "2022.3.42f1")
        window["-LIST-"].update(base_cards)
        window["-Sleeve-"].update("Change Sleeves, Avatars, etc.")
        window["-Sleeve-"].update(disabled=False)
    # FOR CHANGING NON-CARD IMAGES
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
            )
            while True:
                event3, values3 = window3.read()
                print(event3, values3)
                if event3 == "Exit" or event3 == sg.WIN_CLOSED:
                    break
                if event3 == "-LIST3-" and len(values3["-LIST3-"]):
                    name = values3["-LIST3-"][0]
                    print(name)

                    env = asset_viewer.load(path + "/" + name)
                    data_list = asset_viewer.get_texture(
                        env, card=False, land=False, all_textures=True
                    )
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
                                asset_viewer.open_image(data, new_path)
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
            print("Swapping" + str(swap1) + " and " + str(swap2))
            sg.popup_ok("Swapped successfully!", auto_close_duration=2)
            # 73141   89204
        else:

            sg.popup_error(
                "You haven't selected a database, swap1, and/or swap 2 (swap 1 and swap 2 are set by clicking on a card in the list)",
                auto_close_duration=3,
            )

    if values["-INPUT-"] != "":  # if a keystroke entered in search field
        if values["-INPUT-"] != current_input:
            current_input = values["-INPUT-"]
            search = values["-INPUT-"]
            new_values = [x for x in base_cards if search in x[0]]  # do the filtering
            window["-LIST-"].update(new_values)  # display in the listbox
    else:
        # display original unfiltered list
        if current_input != "":

            window["-LIST-"].update(base_cards)
            current_input = ""

    if event == "-LIST-" and len(values["-LIST-"]):
        name, mtg_set, art_size, grp, art = (*values["-LIST-"][0],)
        if name in ["forest", "island", "mountain", "plains", "swamp"]:
            land = True
            card = False
        else:
            land = False
            card = True
        path = os.path.dirname(filename)[0:-3] + r"AssetBundle"
        try:
            prefixed = [f for f in os.listdir(path) if f.startswith(str(art))][0]

            env = asset_viewer.load(path + "/" + prefixed)

            data = asset_viewer.get_texture(env, card=card, land=land)

            if save_dir != "":
                new_path = save_dir + "/" + name + str(random.randint(1, 100)) + ".png"
                asset_viewer.open_image(
                    data,
                    new_path,
                )

                window2 = sg.Window(
                    "Showing: " + name + " Art",
                    [
                        [
                            sg.Button("Change image", key="-EA-"),
                            sg.Button("Change style", key="-CS-"),
                            sg.Button("Set to Swap 1", key="-S1-"),
                            sg.Button("Set to Swap 2", key="-S2-"),
                        ],
                        [sg.Image(filename=new_path, key="-IMAGE-")],
                    ],
                    modal=True,
                    grab_anywhere=True,
                )
                while True:
                    event, values = window2.read()
                    if event == "Exit" or event == sg.WIN_CLOSED:
                        break
                    if event == "-EA-":
                        new = get_file("Select your new image", "image files", "*.png")
                        if new != "":
                            asset_viewer.save_image(
                                data, new, path + "/" + prefixed, env
                            )
                            window2["-IMAGE-"].update(filename=new)
                            sg.popup_auto_close(
                                "Image changed successfully!",
                                auto_close_duration=1,
                            )
                    if event == "-S1-":
                        swap1 = grp
                        print(swap1, swap2)
                    if event == "-S2-":
                        swap2 = grp
                        print(swap1, swap2)

                window2.close()
            else:
                sg.popup_error(
                    "You haven't selected a save location",
                    auto_close_duration=3,
                )
                save_dir = get_dir("Select a folder to save images to")
        except IndexError:
            sg.popup_error(
                "Card not working at the moment",
                auto_close_duration=2,
            )
            continue
window.close()
