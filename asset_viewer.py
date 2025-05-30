import UnityPy
from PIL import Image
from tkinter.filedialog import askopenfilename
import UnityPy.config
from pathlib import Path
import io


def no_alpha(image):
    """Remove alpha channel from an image."""
    if image.mode == "RGBA":
        image = image.convert("RGB")
    return image


def set_aspect_ratio(image, target_aspect_ratio=(10, 8)):
    if type(image) == bytes:
        image = Image.open(io.BytesIO(image))

    width, height = image.size

    # Compute target height based on current width and desired aspect ratio
    target_height = height
    target_width = int(target_height * target_aspect_ratio[0] / target_aspect_ratio[1])

    # Resize (stretch) the image to this new size
    resized = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
    return resized


def set_unity_version(path, version):

    try:
        with open(Path(path).parents[2] / "level0", "rb") as fp:
            txt = fp.read().decode("latin-1").strip()[40:60].replace("\x00", "")
            UnityPy.config.FALLBACK_UNITY_VERSION = txt

    except:
        UnityPy.config.FALLBACK_UNITY_VERSION = version


def get_texture(env, card=True, land=False, planeswalkers=False):
    if land:
        for obj in env.objects:
            data = obj.read()
            if obj.type.name == "Texture2D":
                if data.image.size[0] != 1024:
                    return [data]
    elif planeswalkers:
        return [obj.read() for obj in env.objects if obj.type.name == "Texture2D"]
    else:
        return [
            obj.read()
            for obj in env.objects
            if obj.type.name == "Texture2D"
            and obj.read().image.size[0] in (256, 512, 1024)
        ]
    return None


def open_image(data, path):
    if type(data) == bytes:
        data = Image.open(io.BytesIO(data))
    no_alpha(data).save(path)

    return data
    # edit texture


def save_image(data, new_path, src, env):

    data.image = no_alpha(Image.open(new_path))
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
