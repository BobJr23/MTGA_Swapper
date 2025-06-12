from realesrgan_ncnn_py import Realesrgan
from PIL import Image

realesrgan = Realesrgan(gpuid=0, model=4)


def upscale_image(image_bytes) -> Image.Image:
    """
    Upscale an image using RealESRGAN.

    :param input_image_path: Path to the input image.
    :param output_image_path: Path to save the upscaled image.
    """
    with Image.open(image_bytes) as image:
        upscaled_image = realesrgan.process_pil(image)

    return upscaled_image
