# Unity Asset Bundle operations for MTGA Swapper
# Handles Unity asset bundle loading, texture extraction, and asset manipulation

import UnityPy
import UnityPy.classes
import UnityPy.config
from PIL import Image
from pathlib import Path
import os
from typing import List, Tuple, Optional, Union
from tkinter.filedialog import askopenfilename, askdirectory

from .image_utils import remove_alpha_channel


def configure_unity_version(database_path: str, fallback_version: str) -> None:
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


def load_unity_bundle(bundle_file_path: str) -> UnityPy.Environment:
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


def extract_textures_from_bundle(
    unity_environment: UnityPy.Environment,
) -> List[UnityPy.classes.Texture2D]:
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
    texture_objects = list(
        filter(
            lambda tex: "atlas" not in tex.m_Name.lower().split()[-1]
            and "font texture" != tex.m_Name.lower(),
            texture_objects,
        )
    )

    # Sort by size (width + height) and color complexity (number of unique colors), largest first
    return sorted(
        texture_objects,
        key=lambda texture: (
            texture.image.size[0] + texture.image.size[1],
            len(set(texture.image.getdata())),
        ),
        reverse=True,
    )


def export_3d_meshes(
    unity_environment: UnityPy.Environment, export_directory: str
) -> int:
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


def extract_fonts(
    unity_environment: UnityPy.Environment, export_directory: str
) -> None:
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


def get_card_texture_data(
    card_object, database_file_path: str, ret_matching=False
) -> Optional[Tuple[List[Image.Image], List[UnityPy.classes.Texture2D]]]:
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

            print(
                f"Extracted textures for card {card_object.art_id}: {len(texture_data_list)}"
            )
            if texture_data_list and len(texture_data_list) > 0:
                # Process images to remove alpha channel
                processed_images = [
                    remove_alpha_channel(texture.image) for texture in texture_data_list
                ]
                if ret_matching:
                    return processed_images, texture_data_list, matching_files[0]
                return processed_images, texture_data_list

        except Exception as error:
            print(f"Error loading card textures: {error}")
    return None


def replace_texture_in_bundle(
    texture_data,
    new_image_path: str,
    bundle_file_path: str,
    unity_environment: UnityPy.Environment,
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


def convert_texture_to_bytes(
    texture_image: Union[Image.Image, bytes],
) -> Optional[bytes]:
    """
    Convert a texture image to bytes for display purposes.

    Args:
        texture_image: PIL Image object or bytes

    Returns:
        Image data as bytes in PNG format, or None if conversion fails
    """
    try:
        if isinstance(texture_image, bytes):
            return texture_image

        if not isinstance(texture_image, Image.Image):
            return None

        # Convert PIL Image to bytes
        import io

        image_byte_array = io.BytesIO()
        texture_image.save(image_byte_array, format="PNG")
        return image_byte_array.getvalue()

    except Exception as error:
        print(f"Error converting texture to bytes: {error}")
        return None


def save_image_to_file(
    image_data: Union[Image.Image, bytes], file_path: str, remove_alpha: bool = True
) -> Optional[Image.Image]:
    """
    Save image data to a file with optional alpha channel removal.

    Args:
        image_data: PIL Image object or bytes
        file_path: Destination file path
        remove_alpha: Whether to remove alpha channel before saving

    Returns:
        The processed PIL Image that was saved, or None if failed
    """
    try:
        import io

        # Convert bytes to PIL Image if needed
        if isinstance(image_data, bytes):
            image = Image.open(io.BytesIO(image_data))
        else:
            image = image_data

        # Remove alpha channel if requested
        if remove_alpha and image.mode == "RGBA":
            image = remove_alpha_channel(image)

        # Save the image
        image.save(file_path)
        print(f"Image saved to: {file_path}")
        return image

    except Exception as error:
        print(f"Error saving image to file: {error}")
        return None


# def replace_texture_in_bundle(
#     bundle_file_path: str,
#     texture_name: str,
#     new_image_path: str,
#     output_bundle_path: str,
# ) -> bool:
#     """
#     Replace a texture within a Unity asset bundle with a new image.

#     Args:
#         bundle_file_path: Path to the source bundle file
#         texture_name: Name of the texture to replace
#         new_image_path: Path to the new image file
#         output_bundle_path: Path where the modified bundle will be saved

#     Returns:
#         True if replacement was successful, False otherwise
#     """
#     try:
#         # Load the Unity asset bundle
#         unity_environment = load_unity_bundle(bundle_file_path)
#         if not unity_environment:
#             return False

#         # Load the new image
#         new_image = Image.open(new_image_path)
#         texture_replaced = False

#         # Find and replace the target texture
#         for unity_object in unity_environment.objects:
#             if unity_object.type.name == "Texture2D":
#                 texture = unity_object.read()
#                 if getattr(texture, "name", "") == texture_name:
#                     # Replace the texture data
#                     texture.image = new_image
#                     texture.save()
#                     texture_replaced = True
#                     break

#         if texture_replaced:
#             # Save the modified bundle
#             with open(output_bundle_path, "wb") as output_file:
#                 output_file.write(unity_environment.file.save())
#             print(
#                 f"Texture '{texture_name}' replaced and bundle saved to: {output_bundle_path}"
#             )
#             return True
#         else:
#             print(f"Texture '{texture_name}' not found in bundle")
#             return False

#     except Exception as error:
#         print(f"Error replacing texture in bundle: {error}")
#         return False


# def extract_textures_from_bundle(
#     bundle_file_path: str,
#     export_directory: str,
#     texture_name_filter: Optional[str] = None,
# ) -> int:
#     """
#     Extract all textures from a Unity asset bundle to a directory.

#     Args:
#         bundle_file_path: Path to the Unity asset bundle
#         export_directory: Directory to save extracted textures
#         texture_name_filter: Optional filter for texture names

#     Returns:
#         Number of textures successfully extracted
#     """
#     try:
#         # Create export directory if it doesn't exist
#         Path(export_directory).mkdir(parents=True, exist_ok=True)

#         # Load the Unity asset bundle
#         unity_environment = load_unity_bundle(bundle_file_path)
#         if not unity_environment:
#             return 0

#         textures_extracted = 0

#         # Extract all textures
#         for unity_object in unity_environment.objects:
#             if unity_object.type.name == "Texture2D":
#                 texture = unity_object.read()
#                 texture_name = getattr(texture, "name", f"texture_{textures_extracted}")

#                 # Apply name filter if specified
#                 if texture_name_filter and texture_name_filter not in texture_name:
#                     continue

#                 if hasattr(texture, "image") and texture.image:
#                     # Save the texture as PNG
#                     output_path = Path(export_directory) / f"{texture_name}.png"
#                     texture.image.save(str(output_path))
#                     textures_extracted += 1

#         print(f"Extracted {textures_extracted} textures to: {export_directory}")
#         return textures_extracted

#     except Exception as error:
#         print(f"Error extracting textures from bundle: {error}")
#         return 0
