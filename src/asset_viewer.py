import UnityPy
from PIL import Image
from tkinter.filedialog import askopenfilename, askdirectory
import UnityPy.classes
import UnityPy.config
from pathlib import Path
import io
import os


def no_alpha(image) -> Image.Image:
    """Remove alpha channel from an image."""
    if image.mode == "RGBA":
        image = image.convert("RGB")
    return image


def shrink_to_monitor(image, target_width=1920, target_height=1080) -> Image.Image:
    """Resize an image to fit within the target dimensions while maintaining aspect ratio."""
    if type(image) == bytes:
        image = Image.open(io.BytesIO(image))

    width, height = image.size

    # Calculate the scaling factor
    scale_factor = min(target_width / width, target_height / height)

    # Calculate new dimensions
    new_width = int(width * scale_factor)
    new_height = int(height * scale_factor)

    # Resize the image
    resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    return resized_image


def set_aspect_ratio(
    image, target_aspect_ratio=(11, 8), ratio=True
) -> tuple[Image.Image, int, int]:
    if type(image) == bytes:
        image = Image.open(io.BytesIO(image))
    if ratio:
        width, height = image.size

        current_aspect = width / height
        target_aspect = target_aspect_ratio[0] / target_aspect_ratio[1]

        if current_aspect > target_aspect:
            target_height = height
            target_width = int(height * target_aspect)
        else:
            target_width = width
            target_height = int(width / target_aspect)

    # Resize (stretch) the image to this new size
    else:
        if sum(target_aspect_ratio) > sum(image.size):
            return image, *image.size
        else:
            target_width, target_height = target_aspect_ratio
    resized = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
    return resized, target_width, target_height


def set_unity_version(path, version) -> None:

    try:
        with open(Path(path).parents[2] / "level0", "rb") as fp:
            txt = fp.read().decode("latin-1").strip()[40:60].replace("\x00", "")
            UnityPy.config.FALLBACK_UNITY_VERSION = txt

    except:
        UnityPy.config.FALLBACK_UNITY_VERSION = version


def get_texture(env: UnityPy.Environment) -> list[UnityPy.classes.Texture2D]:

    return sorted(
        [obj.read() for obj in env.objects if obj.type.name == "Texture2D"],
        key=lambda x: (x.image.size[0] + x.image.size[1], len(set(x.image.getdata()))),
        reverse=True,
    )


def get_card_textures(
    card, filename
) -> tuple[list[Image.Image] | None, list[UnityPy.classes.Texture2D] | None] | None:
    if card and filename:
        try:

            db_parent_dir = Path(filename).parent
            game_root_dir = db_parent_dir.parent

            path = str(game_root_dir / "AssetBundle")
            prefixed = [
                f
                for f in os.listdir(path)
                if f.startswith(str(card.art_id)) and f.endswith(".mtga")
            ][0]
            env = load(os.path.join(path, prefixed))
            data = get_texture(env)
            if data and len(data) > 0:
                return list(map(lambda x: no_alpha(x.image), data)), data

            # asset_viewer.no_alpha(data[0].image).save(img_byte_arr, format="PNG")
            # return img_byte_arr.getvalue()

        except Exception as e:
            print(f"Error: {e}")
            return None
    return None


def get_image_from_texture(texture) -> bytes | None:
    if texture:
        img_byte_arr = io.BytesIO()
        texture.save(img_byte_arr, format="PNG")
        return img_byte_arr.getvalue()
    return None


def open_image(data, path) -> Image.Image:
    if type(data) == bytes:
        data = Image.open(io.BytesIO(data))
    no_alpha(data).save(path)

    return data


def save_image(data, new_path, src, env) -> None:

    data.image = no_alpha(Image.open(new_path))
    data.save()
    with open(src, "wb") as f:
        f.write(env.file.save())


def load(path) -> UnityPy.Environment:
    try:
        return UnityPy.load(path)
    except UnityPy.exceptions.UnityVersionFallbackError as e:
        UnityPy.config.FALLBACK_UNITY_VERSION = "2022.3.42f1"
        print(
            f"Error: {e}. Setting fallback Unity version to {UnityPy.config.FALLBACK_UNITY_VERSION}."
        )
        return UnityPy.load(path)


def get_fonts(env: UnityPy.Environment, path) -> None:
    """Get all fonts from the Unity environment."""

    for obj in env.objects:
        if obj.type.name == "Font":
            font = obj.read()

            if font.m_FontData:
                extension = ".ttf"
                if font.m_FontData[0:4] == b"OTTO":
                    extension = ".otf"

            with open(os.path.join(path, font.m_Name + extension), "wb") as f:
                f.write(bytes(font.m_FontData))


if __name__ == "__main__":
    # Run to export fonts
    font_path = askopenfilename(
        title="Select file that starts with 'Fonts_' in AssetBundle Folder"
    )
    font_save_path = askdirectory(
        initialdir=os.path.dirname(font_path),
        title="Select folder to save fonts",
    )
    if font_path:
        env = load(font_path)
        fonts = get_fonts(env, font_save_path)
