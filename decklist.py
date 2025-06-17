import FreeSimpleGUI as sg
import re


def create_decklist_window() -> set[str]:
    cards = None
    layout = [
        [
            sg.Text(
                "Paste a decklist in MTGA format below: \nEx:\n\nDeck\n20 Forest\n3 Llanowar Elves\n\nor upload cards separated by a new line from .txt file\nNote: Cards with Aftermath require ///, while other dual cards use //"
            ),
        ],
        [sg.Checkbox("MTG Arena format", default=True, key="-MTGA-")],
        [sg.Multiline(size=(40, 20), key="-DECKLIST-", expand_x=True, expand_y=True)],
        [
            sg.Button("Load from .txt file", key="-LOAD-"),
            sg.Button("Save and Exit", key="Exit"),
        ],
    ]
    window = sg.Window(
        "Decklist Manager",
        layout,
        resizable=True,
        grab_anywhere=True,
    )

    while True:

        event, values = window.read()
        if event == sg.WIN_CLOSED or event == "Exit":

            cards = values["-DECKLIST-"].strip().split("\n")

            if values["-MTGA-"]:
                cards = list(filter(lambda x: x != "" and x[0] in "123456789", cards))
                # Convert to database friendly format
                cards = set(
                    map(
                        lambda x: re.sub(
                            r"[^a-zA-Z0-9/]",
                            "",
                            "".join(x.split("(")[0].split(" ")[1:]).strip().lower(),
                        )[:15],
                        cards,
                    )
                )

                sg.popup_quick_message(
                    "Deck imported successfully!", auto_close_duration=1
                )
            else:
                cards = set(
                    map(
                        lambda x: re.sub(r"[^a-zA-Z0-9/]", "", x.strip().lower())[:15],
                        filter(lambda x: x != "", cards),
                    )
                )
                print(cards)
                sg.popup_quick_message(
                    "Deck imported successfully!", auto_close_duration=1
                )
            break

        elif event == "-LOAD-":
            filename = sg.popup_get_file(
                "Select a .txt file containing your decklist",
                file_types=(("Text Files", "*.txt"),),
            )
            if filename:
                try:
                    with open(filename, "r", encoding="utf-8") as f:
                        content = f.read()
                        window["-DECKLIST-"].update(content)
                        sg.popup_quick_message(
                            "File loaded successfully!", auto_close_duration=1
                        )
                    window["-MTGA-"].update(value=False)
                except Exception as e:
                    sg.popup_error(f"Error loading file: {e}")

    window.close()

    return cards


if __name__ == "__main__":
    c = create_decklist_window()
    print(c)
