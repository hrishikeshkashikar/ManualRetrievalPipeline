"""
Image utility functions for encoding, resizing, and format conversion.
"""

import base64
import io
import logging
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)


def resize_image(image: Image.Image, max_resolution: int = 1024) -> Image.Image:
    """
    Resize an image so its largest dimension does not exceed max_resolution,
    preserving aspect ratio.

    Args:
        image: PIL Image to resize.
        max_resolution: Maximum width or height in pixels.

    Returns:
        Resized PIL Image (or original if already within bounds).
    """
    width, height = image.size
    if width <= max_resolution and height <= max_resolution:
        return image

    if width > height:
        new_width = max_resolution
        new_height = int(height * (max_resolution / width))
    else:
        new_height = max_resolution
        new_width = int(width * (max_resolution / height))

    resized = image.resize((new_width, new_height), Image.LANCZOS)
    logger.debug(f"Resized image from {width}x{height} to {new_width}x{new_height}")
    return resized


def image_to_base64(image: Image.Image, format: str = "PNG") -> str:
    """
    Convert a PIL Image to a base64-encoded string.

    Args:
        image: PIL Image to encode.
        format: Image format (PNG, JPEG, etc.).

    Returns:
        Base64-encoded string of the image.
    """
    buffer = io.BytesIO()
    image.save(buffer, format=format)
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")


def image_to_bytes(image: Image.Image, format: str = "PNG") -> bytes:
    """
    Convert a PIL Image to raw bytes.

    Args:
        image: PIL Image to convert.
        format: Image format (PNG, JPEG, etc.).

    Returns:
        Raw bytes of the image.
    """
    buffer = io.BytesIO()
    image.save(buffer, format=format)
    buffer.seek(0)
    return buffer.read()


def load_image(path: str | Path) -> Image.Image:
    """
    Load an image from disk.

    Args:
        path: Path to the image file.

    Returns:
        PIL Image.

    Raises:
        FileNotFoundError: If the image file does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")
    return Image.open(path).convert("RGB")


def save_image(image: Image.Image, path: str | Path, format: str = "PNG") -> Path:
    """
    Save a PIL Image to disk, creating parent directories if needed.

    Args:
        image: PIL Image to save.
        path: Destination file path.
        format: Image format (PNG, JPEG, etc.).

    Returns:
        The path where the image was saved.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format=format)
    logger.debug(f"Saved image to {path}")
    return path
