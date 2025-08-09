# Image upscaling module using ONNX models
# Handles both ESRGAN 4x and 2x upscaling based on image dimensions

import os
import sys
from typing import Optional, Union
import io

try:
    import onnxruntime as ort
    import numpy as np
    import cv2
    from PIL import Image

    # Flag to indicate if upscaling functionality is available
    is_upscaling_available = True
except ImportError as e:
    Image = None
    np = None
    print(f"Some upscaling packages not installed.")
    is_upscaling_available = False


def get_resource_path(relative_path: str) -> str:
    """
    Get absolute path to resource, works for both development and PyInstaller builds.

    Args:
        relative_path: Path relative to the application directory

    Returns:
        Absolute path to the resource file
    """
    try:
        # Only exists when bundled with PyInstaller
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# Initialize upscaling models if dependencies are available
if is_upscaling_available:

    def preprocess_image_for_upscaling(image_bytes: io.BytesIO):
        """
        Preprocess input image bytes for ONNX model inference.

        Args:
            image_bytes: Raw image data as BytesIO object

        Returns:
            Preprocessed numpy array ready for model input
        """
        numpy_array = np.frombuffer(image_bytes.read(), np.uint8)
        image = cv2.imdecode(numpy_array, cv2.IMREAD_COLOR)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image = image.astype(np.float32) / 255.0  # Normalize to [0, 1]
        image = np.transpose(image, (2, 0, 1))  # HWC to CHW format
        image = np.expand_dims(image, axis=0)  # Add batch dimension
        return image

    def upscale_card_image(image_bytes: io.BytesIO, width: int, height: int):
        """
        Upscale an image using appropriate ONNX model based on dimensions.
        Uses 4x model for smaller images, 2x model for larger ones.

        Args:
            image_bytes: Input image as BytesIO object
            width: Original image width
            height: Original image height

        Returns:
            Upscaled PIL Image object
        """
        input_tensor = preprocess_image_for_upscaling(image_bytes)

        # Choose model based on image size to prevent memory issues
        if width + height <= 1024:
            upscaling_session = onnx_session_4x
        else:
            upscaling_session = onnx_session_2x

        # Run inference
        model_output = upscaling_session.run(
            [upscaling_session.get_outputs()[0].name],
            {upscaling_session.get_inputs()[0].name: input_tensor},
        )[0]

        # Post-process the output
        output_image = model_output.squeeze(0).transpose(1, 2, 0)  # CHW to HWC
        output_image = np.clip(output_image * 255.0, 0, 255).astype(np.uint8)

        return Image.fromarray(output_image)

    # Initialize ONNX inference sessions
    print("Loading ONNX upscaling models...")
    available_execution_providers = ort.get_available_providers()

    # Select best available execution provider for hardware acceleration
    if "CUDAExecutionProvider" in available_execution_providers:
        execution_providers = ["CUDAExecutionProvider"]
        print("Using CUDA acceleration for upscaling")
    elif "DmlExecutionProvider" in available_execution_providers:  # DirectML for AMD
        execution_providers = ["DmlExecutionProvider"]
        print("Using DirectML acceleration for upscaling")
    else:
        execution_providers = ["CPUExecutionProvider"]
        print("Using CPU for upscaling")

    # Load the upscaling models
    onnx_session_4x = ort.InferenceSession(
        get_resource_path("modelscsr.onnx"), providers=execution_providers
    )
    onnx_session_2x = ort.InferenceSession(
        get_resource_path("modelesrgan2.onnx"), providers=execution_providers
    )

    print("ONNX upscaling models loaded successfully.")
