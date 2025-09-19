# GUI utilities and dialog functions for MTGA Swapper
# Contains file dialogs, image conversion utilities, and other GUI helper functions

from tkinter import Tk
from tkinter.filedialog import askopenfilename, askdirectory
from pathlib import Path
from PIL import Image
import io
from typing import Optional


def open_file_dialog(title: str, description: str, file_types: str) -> Optional[str]:
    """
    Open a file selection dialog.

    Args:
        title: Dialog window title
        description: File type description
        file_types: File extension pattern (e.g., '*.mtga')

    Returns:
        Selected file path as POSIX string, or None if cancelled
    """
    Tk().withdraw()
    selected_file = askopenfilename(filetypes=[(description, file_types)], title=title)
    return Path(selected_file).as_posix() if selected_file else None


def open_directory_dialog(title: str) -> str:
    """
    Open a directory selection dialog.

    Args:
        title: Dialog window title

    Returns:
        Selected directory path as POSIX string
    """
    Tk().withdraw()
    return Path(askdirectory(title=title)).as_posix()


def convert_pil_image_to_bytes(pil_image: Image.Image) -> bytes:
    """
    Convert a PIL Image to bytes for display in PySimpleGUI.

    Args:
        pil_image: PIL Image object

    Returns:
        Image data as bytes in PNG format
    """
    image_byte_array = io.BytesIO()
    pil_image.save(image_byte_array, format="PNG")
    return image_byte_array.getvalue()

