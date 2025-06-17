import onnxruntime as ort
import numpy as np
import cv2
from PIL import Image
import os, sys


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and PyInstaller"""
    try:
        base_path = sys._MEIPASS  # Only exists when bundled
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# Preprocess input image
def preprocess(img_bytes) -> np.ndarray:
    np_arr = np.frombuffer(img_bytes.read(), np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = img.astype(np.float32) / 255.0  # Normalize to [0, 1]
    img = np.transpose(img, (2, 0, 1))  # HWC to CHW
    img = np.expand_dims(img, axis=0)  # Add batch dimension
    return img


def upscale_image(image_bytes, w, h) -> Image.Image:
    """
    Upscale an image using ONNX model.

    :param image_bytes: Path to the input image.
    :return: Upscaled PIL image.
    """
    input_tensor = preprocess(image_bytes)

    if w + h <= 1024:
        session = session4x
    else:
        session = session2x
    output = session.run(
        [session.get_outputs()[0].name],
        {session.get_inputs()[0].name: input_tensor},
    )[0]

    # Post-process and return
    output_img = output.squeeze(0).transpose(1, 2, 0)  # CHW to HWC
    output_img = np.clip(output_img * 255.0, 0, 255).astype(np.uint8)

    return Image.fromarray(output_img)


# Choose the best available execution provider

print("Loading ONNX models...")
available_providers = ort.get_available_providers()

if "CUDAExecutionProvider" in available_providers:
    providers = ["CUDAExecutionProvider"]
elif "DmlExecutionProvider" in available_providers:  # DirectML for AMD
    providers = ["DmlExecutionProvider"]
else:
    providers = ["CPUExecutionProvider"]

session4x = ort.InferenceSession(resource_path("modelscsr.onnx"), providers=providers)
session2x = ort.InferenceSession(
    resource_path("modelesrgan2.onnx"), providers=providers
)

print("ONNX models loaded successfully.")
