# Image processing utilities for MTGA Swapper
# Contains image manipulation, resizing, and format conversion functions

from PIL import Image
import io
from typing import Union, Tuple, Optional


def remove_alpha_channel(
    image: Image.Image, should_remove_alpha: bool = True
) -> Image.Image:
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


def resize_image_to_screen(
    image: Union[bytes, Image.Image],
    target_width: int = 1920,
    target_height: int = 1080,
) -> Image.Image:
    """
    Resize an image to fit within the target screen dimensions while maintaining aspect ratio.

    Args:
        image: PIL Image object or bytes
        target_width: Maximum width for the resized image
        target_height: Maximum height for the resized image

    Returns:
        Resized PIL Image object
    """
    if isinstance(image, bytes):
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
    image: Union[bytes, Image.Image],
    target_aspect_ratio: Tuple[int, int] = (11, 8),
    maintain_ratio: bool = True,
) -> Tuple[Image.Image, int, int]:
    """
    Adjust image dimensions to match a target aspect ratio.

    Args:
        image: PIL Image object or bytes
        target_aspect_ratio: Tuple of (width_ratio, height_ratio)
        maintain_ratio: If True, crop to ratio; if False, stretch to exact dimensions

    Returns:
        Tuple of (resized_image, final_width, final_height)
    """
    if isinstance(image, bytes):
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


def convert_texture_to_bytes(texture_image: Optional[Image.Image]) -> Optional[bytes]:
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


def resize_image_for_gallery(
    image: Image.Image, target_size: Tuple[int, int] = (200, 200)
) -> Image.Image:
    """
    Resize an image to fit within gallery thumbnail dimensions while maintaining aspect ratio.

    Args:
        image: PIL Image object
        target_size: Tuple of (width, height) for the thumbnail

    Returns:
        Resized PIL Image object
    """
    current_width, current_height = image.size
    target_width, target_height = target_size

    # Calculate the scaling factor to fit within target dimensions
    scale_factor = min(target_width / current_width, target_height / current_height)

    # Calculate new dimensions
    new_width = int(current_width * scale_factor)
    new_height = int(current_height * scale_factor)

    # Resize the image using high-quality resampling
    resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    return resized_image


def save_image_to_file(
    image_data: Union[bytes, Image.Image], file_path: str, remove_alpha: bool = True
) -> Image.Image:
    """
    Save image data to a file with optional alpha channel removal.

    Args:
        image_data: Image data (bytes or PIL Image)
        file_path: Destination file path
        remove_alpha: Whether to remove alpha channel before saving

    Returns:
        The processed PIL Image object
    """
    if isinstance(image_data, bytes):
        image_data = Image.open(io.BytesIO(image_data))

    processed_image = remove_alpha_channel(image_data, remove_alpha)
    processed_image.save(file_path)
    return image_data
