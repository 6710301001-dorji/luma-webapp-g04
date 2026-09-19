"""Image acquisition utilities (Lecture 3, pp. 23-29 and 55-56).

File I/O is confined to this stage. Later pipeline stages receive NumPy arrays.
"""

import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError
from PIL.ExifTags import TAGS


MAX_FILE_BYTES = 16 * 1024 * 1024
SUPPORTED_FORMATS = {"JPEG", "PNG", "WEBP", "TIFF"}


class ImageValidationError(ValueError):
    """The input cannot be accepted as a usable image."""


def validate_image_file(path, max_bytes=MAX_FILE_BYTES, max_aspect_ratio=10):
    """Check file size, actual image format and dimensions (Lecture 3, pp. 23-29)."""
    path = Path(path)
    if not path.is_file():
        raise ImageValidationError("Image file does not exist")
    size = path.stat().st_size
    if size == 0:
        raise ImageValidationError("Image file is empty")
    if size > max_bytes:
        raise ImageValidationError(f"Image exceeds {max_bytes} bytes")

    try:
        with Image.open(path) as source:
            image_format = source.format
            width, height = source.size
            source.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageValidationError("File is not a readable image") from exc

    if image_format not in SUPPORTED_FORMATS:
        raise ImageValidationError(f"Unsupported image format: {image_format}")
    if width <= 0 or height <= 0:
        raise ImageValidationError("Image dimensions must be positive")
    if max(width / height, height / width) > max_aspect_ratio:
        raise ImageValidationError("Image aspect ratio is too extreme")
    return {"format": image_format, "width": width, "height": height, "file_bytes": size}


def load(path, max_bytes=MAX_FILE_BYTES):
    """Return a BGR NumPy image, or None for invalid input (Lecture 3, p. 23)."""
    try:
        validate_image_file(path, max_bytes=max_bytes)
    except ImageValidationError:
        return None
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    return image if image is not None and image.size else None


def image_metadata(image):
    """Describe a loaded NumPy image (Lecture 3, pp. 23-29)."""
    if not isinstance(image, np.ndarray) or image.ndim not in (2, 3) or image.size == 0:
        raise ImageValidationError("Expected a nonempty 2D or 3D image array")
    height, width = image.shape[:2]
    channels = 1 if image.ndim == 2 else image.shape[2]
    return {"width": width, "height": height, "channels": channels, "dtype": str(image.dtype)}


def read_exif(path):
    """Read camera EXIF when present (Lecture 3, pp. 31-59; Lecture 7, pp. 3-20).

    Sensor width is rarely stored in EXIF, so it must be provided separately for FOV.
    """
    validate_image_file(path)
    with Image.open(path) as source:
        raw = {TAGS.get(key, key): value for key, value in source.getexif().items()}
    names = {
        "FocalLength": "focal_length_mm",
        "ISOSpeedRatings": "iso",
        "PhotographicSensitivity": "iso",
        "ExposureTime": "exposure_seconds",
        "FocalLengthIn35mmFilm": "focal_length_35mm_equivalent_mm",
    }
    result = {}
    for tag, name in names.items():
        if tag in raw:
            value = raw[tag]
            result[name] = float(value) if name in ("focal_length_mm", "exposure_seconds") else int(value)
    return result


def field_of_view(sensor_width_mm, focal_length_mm, distance_m):
    """Return horizontal angle in degrees and scene width in metres (Lecture 3, pp. 55-56)."""
    values = (sensor_width_mm, focal_length_mm, distance_m)
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or
           not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError("Sensor width, focal length and distance must be positive numbers")
    angle_rad = 2 * math.atan(sensor_width_mm / (2 * focal_length_mm))
    scene_width_m = 2 * distance_m * math.tan(angle_rad / 2)
    return {"angle_degrees": math.degrees(angle_rad), "scene_width_m": scene_width_m}


def normalize_width(image, width=512):
    """Resize an array while preserving aspect ratio (Lecture 3, pp. 23-29)."""
    metadata = image_metadata(image)
    if isinstance(width, bool) or not isinstance(width, int) or width <= 0:
        raise ValueError("width must be a positive integer")
    if metadata["width"] == width:
        return image.copy()
    height = max(1, round(metadata["height"] * width / metadata["width"]))
    interpolation = cv2.INTER_AREA if width < metadata["width"] else cv2.INTER_LINEAR
    return cv2.resize(image, (width, height), interpolation=interpolation)
