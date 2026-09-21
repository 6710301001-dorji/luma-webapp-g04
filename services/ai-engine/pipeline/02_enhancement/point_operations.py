"""Intensity transforms for uint8 grayscale and color images."""

import numpy as np


def _check_image(image):
    if not isinstance(image, np.ndarray) or image.dtype != np.uint8 or image.ndim not in (2, 3):
        raise ValueError("image must be a 2D or 3D uint8 array")
    if image.size == 0:
        raise ValueError("image must not be empty")
    return image


def gamma(image, value):
    """Apply s = 255 * (r / 255) ** gamma; gamma < 1 brightens."""
    image = _check_image(image)
    if isinstance(value, bool) or not np.isscalar(value) or not np.isfinite(value) or value <= 0:
        raise ValueError("gamma must be a positive finite number")
    if value == 1:
        return image.copy()
    lut = np.clip(np.rint(255 * (np.arange(256, dtype=np.float64) / 255) ** value), 0, 255).astype(np.uint8)
    return lut[image]


def log_transform(image):
    """Expand dark intensities with a normalized logarithmic mapping."""
    image = _check_image(image)
    lut = np.clip(np.rint(255 * np.log1p(np.arange(256)) / np.log1p(255)), 0, 255).astype(np.uint8)
    return lut[image]


def contrast_stretch(image):
    """Map the image's minimum intensity to 0 and maximum to 255."""
    image = _check_image(image)
    low, high = int(image.min()), int(image.max())
    if low == high:
        return image.copy()
    lut = np.clip(np.rint((np.arange(256, dtype=np.float64) - low) * 255 / (high - low)), 0, 255).astype(np.uint8)
    return lut[image]
