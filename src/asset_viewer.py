# Unity Asset Bundle manipulation module
# Handles loading, viewing, and modifying MTGA Unity assets including textures and fonts

import UnityPy
from PIL import Image
from tkinter.filedialog import askopenfilename, askdirectory
import UnityPy.classes
import UnityPy.config
from pathlib import Path
import io
import os


def remove_alpha_channel(image, should_remove_alpha=True) -> Image.Image:
    """
    Remove alpha channel from an image by converting RGBA to RGB.

    Args:
        image: PIL Image object
        should_remove_alpha: Whether to actually remove the alpha channel

    Returns:
        Image with alpha channel removed if applicable
    """
    if should_remove_alpha and image.mode == "RGBA":
        image = image.convert("RGB")
    return image


def resize_image_to_screen(image, target_width=1920, target_height=1080) -> Image.Image:
    """
    Resize an image to fit within the target screen dimensions while maintaining aspect ratio.

    Args:
        image: PIL Image object or bytes
        target_width: Maximum width for the resized image
        target_height: Maximum height for the resized image

    Returns:
        Resized PIL Image object
    """
    if type(image) == bytes:
        image = Image.open(io.BytesIO(image))

    current_width, current_height = image.size

    # Calculate the scaling factor to fit within target dimensions
    scale_factor = min(target_width / current_width, target_height / current_height, 1)

    # Calculate new dimensions
    new_width = int(current_width * scale_factor)
    new_height = int(current_height * scale_factor)

    # Resize the image using high-quality resampling
    resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    return resized_image


def adjust_image_aspect_ratio(
    image: bytes | Image.Image, target_aspect_ratio=(11, 8), maintain_ratio=True
) -> tuple[Image.Image, int, int]:
    """
    Adjust image dimensions to match a target aspect ratio.

    Args:
        image: PIL Image object or bytes
        target_aspect_ratio: Tuple of (width_ratio, height_ratio)
        maintain_ratio: If True, crop to ratio; if False, stretch to exact dimensions

    Returns:
        Tuple of (resized_image, final_width, final_height)
    """
    if type(image) == bytes:
        image = Image.open(io.BytesIO(image))

    if maintain_ratio:
        current_width, current_height = image.size

        current_aspect = current_width / current_height
        target_aspect = target_aspect_ratio[0] / target_aspect_ratio[1]

        # Calculate new dimensions maintaining aspect ratio
        if current_aspect > target_aspect:
            target_height = current_height
            target_width = int(current_height * target_aspect)
        else:
            target_width = current_width
            target_height = int(current_width / target_aspect)

    else:
        # Don't upscale if target dimensions are larger than original
        if sum(target_aspect_ratio) > sum(image.size):
            return image, *image.size
        else:
            target_width, target_height = target_aspect_ratio

    # Resize the image to the calculated dimensions
    resized_image = image.resize(
        (target_width, target_height), Image.Resampling.LANCZOS
    )
    return resized_image, target_width, target_height


def configure_unity_version(database_path, fallback_version) -> None:
    """
    Configure Unity version for asset bundle loading based on the game installation.

    Args:
        database_path: Path to the MTGA database file
        fallback_version: Version string to use if detection fails
    """
    try:
        # Try to read Unity version from the level0 file in the game directory
        level0_path = Path(database_path).parents[2] / "level0"
        with open(level0_path, "rb") as version_file:
            version_text = (
                version_file.read().decode("latin-1").strip()[40:60].replace("\x00", "")
            )
            UnityPy.config.FALLBACK_UNITY_VERSION = version_text

    except:
        # Use fallback version if detection fails
        UnityPy.config.FALLBACK_UNITY_VERSION = fallback_version


def extract_textures_from_bundle(
    unity_environment: UnityPy.Environment,
) -> list[UnityPy.classes.Texture2D]:
    """
    Extract all Texture2D objects from a Unity asset bundle.

    Args:
        unity_environment: Loaded Unity environment

    Returns:
        List of Texture2D objects sorted by size and complexity
    """
    texture_objects = [
        obj.read() for obj in unity_environment.objects if obj.type.name == "Texture2D"
    ]

    # Sort by size (width + height) and color complexity (number of unique colors), largest first
    return sorted(
        texture_objects,
        key=lambda texture: (
            texture.image.size[0] + texture.image.size[1],
            len(set(texture.image.getdata())),
        ),
        reverse=True,
    )


def export_3d_meshes(unity_environment: UnityPy.Environment, export_directory) -> int:
    """
    Export all 3D meshes from the Unity environment to OBJ files.

    Args:
        unity_environment: Loaded Unity environment
        export_directory: Directory to save the exported mesh files

    Returns:
        Number of meshes successfully exported
    """
    mesh_counter = 0
    for unity_object in unity_environment.objects:
        if unity_object.type.name == "Mesh":
            mesh_data = unity_object.read()
            mesh_file_path = os.path.join(export_directory, f"{mesh_data.m_Name}.obj")
            with open(mesh_file_path, "wt", newline="") as mesh_file:
                mesh_file.write(mesh_data.export())
            mesh_counter += 1
    return mesh_counter


def get_card_texture_data(
    card_object,
    database_file_path,
) -> tuple[list[Image.Image] | None, list[UnityPy.classes.Texture2D] | None] | None:
    """
    Extract texture data for a specific card from its asset bundle.

    Args:
        card_object: Card object containing art_id and other metadata
        database_file_path: Path to the MTGA database file

    Returns:
        Tuple of (processed_images_list, raw_texture_data_list) or None if not found
    """
    if card_object and database_file_path:
        try:
            # Construct path to AssetBundle directory
            database_parent_directory = Path(database_file_path).parent
            game_root_directory = database_parent_directory.parent
            asset_bundle_path = str(game_root_directory / "AssetBundle")

            # Find the asset bundle file for this card
            matching_files = [
                filename
                for filename in os.listdir(asset_bundle_path)
                if filename.startswith(str(card_object.art_id))
                and filename.endswith(".mtga")
            ]

            if not matching_files:
                return None

            bundle_file_path = os.path.join(asset_bundle_path, matching_files[0])
            unity_environment = load_unity_bundle(bundle_file_path)
            texture_data_list = extract_textures_from_bundle(unity_environment)

            if texture_data_list and len(texture_data_list) > 0:
                # Process images to remove alpha channel
                processed_images = [
                    remove_alpha_channel(texture.image) for texture in texture_data_list
                ]
                return processed_images, texture_data_list

        except Exception as error:
            print(f"Error loading card textures: {error}")
            return None
    return None


def convert_texture_to_bytes(texture_image) -> bytes | None:
    """
    Convert a PIL Image texture to bytes for display in GUI.

    Args:
        texture_image: PIL Image object

    Returns:
        Image data as bytes in PNG format, or None if conversion fails
    """
    if texture_image:
        image_byte_buffer = io.BytesIO()
        texture_image.save(image_byte_buffer, format="PNG")
        return image_byte_buffer.getvalue()
    return None


def save_image_to_file(image_data, file_path, remove_alpha=True) -> Image.Image:
    """
    Save image data to a file with optional alpha channel removal.

    Args:
        image_data: Image data (bytes or PIL Image)
        file_path: Destination file path
        remove_alpha: Whether to remove alpha channel before saving

    Returns:
        The processed PIL Image object
    """
    if type(image_data) == bytes:
        image_data = Image.open(io.BytesIO(image_data))

    processed_image = remove_alpha_channel(image_data, remove_alpha)
    processed_image.save(file_path)
    return image_data


def replace_texture_in_bundle(
    texture_data, new_image_path, bundle_file_path, unity_environment
) -> None:
    """
    Replace a texture in a Unity asset bundle with a new image.

    Args:
        texture_data: Original texture data object
        new_image_path: Path to the new image file
        bundle_file_path: Path to the asset bundle file
        unity_environment: Unity environment object
    """
    # Load the new image and replace the texture data
    texture_data.image = Image.open(new_image_path)
    texture_data.save()

    # Save the modified bundle back to file
    with open(bundle_file_path, "wb") as bundle_file:
        bundle_file.write(unity_environment.file.save())


def load_unity_bundle(bundle_file_path) -> UnityPy.Environment:
    """
    Load a Unity asset bundle file with error handling for version compatibility.

    Args:
        bundle_file_path: Path to the Unity asset bundle file

    Returns:
        Loaded Unity environment object
    """
    try:
        return UnityPy.load(bundle_file_path)
    except UnityPy.exceptions.UnityVersionFallbackError as error:
        # Set fallback version and retry
        UnityPy.config.FALLBACK_UNITY_VERSION = "2022.3.42f1"
        print(
            f"Unity version error: {error}. Using fallback version {UnityPy.config.FALLBACK_UNITY_VERSION}."
        )
        return UnityPy.load(bundle_file_path)


def extract_fonts(unity_environment: UnityPy.Environment, export_directory) -> None:
    """
    Extract all font files from the Unity environment.

    Args:
        unity_environment: Loaded Unity environment
        export_directory: Directory to save the extracted fonts
    """
    for unity_object in unity_environment.objects:
        if unity_object.type.name == "Font":
            font_data = unity_object.read()

            # Determine font file extension based on font data
            if font_data.m_FontData:
                file_extension = ".ttf"
                if font_data.m_FontData[0:4] == b"OTTO":
                    file_extension = ".otf"

            # Save font file
            font_file_path = os.path.join(
                export_directory, font_data.m_Name + file_extension
            )
            with open(font_file_path, "wb") as font_file:
                font_file.write(bytes(font_data.m_FontData))
