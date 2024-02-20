import sqlite3
from tkinter import Tk  # from tkinter import Tk for Python 3.x
from tkinter.filedialog import askopenfilename, askdirectory


def swap_values(value1, value2, cur, con):
    try:
        cur.executemany(
            """
        UPDATE Cards
        SET GrpId = ? 
        WHERE GrpId = ?
        
        """,
            [(0, value1), (1, value2)],
        )
        cur.executemany(
            """
        UPDATE Cards
        SET GrpId = ? 
        WHERE GrpId = ?
        
        """,
            [(value2, 0), (value1, 1)],
        )
    except sqlite3.OperationalError:
        print("You used the wrong file, relaunch this program and try again")
        exit()
    con.commit()


def get_details_from_name(value, cur):
    res = cur.execute(
        f"SELECT GrpID, ArtId, ExpansionCode FROM Cards WHERE Order_Title='{value}'"
    )

    return res.fetchall()


def main(file):

    con = sqlite3.connect(file)

    cur = con.cursor()

    return cur, con, file


# if __name__ == "__main__":
#     cur, con, f = main()
#     name = input("enter a card name to find grp id\n > ")
#     n = get_details_from_name(name.lower(), cur)
#     for x in n:
#         print(x)
