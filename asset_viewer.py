import UnityPy
from PIL import Image
from tkinter.filedialog import askopenfilename
import UnityPy.config
from pathlib import Path
import unicodedata


def set_unity_version(path, version):

    try:
        with open(Path(path).parents[2] / "level0", "rb") as fp:
            txt = fp.read().decode("latin-1").strip()[40:60].replace("\x00", "")
            UnityPy.config.FALLBACK_UNITY_VERSION = txt

    except:
        UnityPy.config.FALLBACK_UNITY_VERSION = version


def get_texture(env, card=True, land=False, all_textures=False):
    if not all_textures:
        for obj in env.objects:
            data = obj.read()
            if obj.type.name == "Texture2D":
                if card:
                    print(f"Texture found: ", data.image.size)
                    if data.image.size[0] in (512, 1024):
                        return data
                elif land:
                    if data.image.size[0] != 1024:
                        return data
                else:
                    return data
    else:
        return [obj.read() for obj in env.objects if obj.type.name == "Texture2D"]
    return None


def open_image(data, path):

    data.image.save(path)

    return data
    # edit texture


def save_image(data, new_path, src, env):

    data.image = Image.open(new_path)
    data.save()
    with open(src, "wb") as f:
        f.write(env.file.save())


def load(path):
    try:
        return UnityPy.load(path)
    except UnityPy.exceptions.UnityVersionFallbackError as e:
        UnityPy.config.FALLBACK_UNITY_VERSION = "2022.3.42f1"
        print(
            f"Error: {e}. Setting fallback Unity version to {UnityPy.config.FALLBACK_UNITY_VERSION}."
        )
        return UnityPy.load(path)
