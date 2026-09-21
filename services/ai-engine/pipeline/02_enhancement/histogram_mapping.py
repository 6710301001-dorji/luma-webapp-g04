"""Histogram equalization and matching for uint8 grayscale or BGR images."""

import cv2
import numpy as np


def _check_image(image):
    if not isinstance(image, np.ndarray) or image.dtype != np.uint8 or image.size == 0:
        raise ValueError("image must be a nonempty uint8 array")
    if image.ndim != 2 and not (image.ndim == 3 and image.shape[2] == 3):
        raise ValueError("image must be grayscale or three-channel BGR")
    return image


def _on_intensity(image, operation):
    if image.ndim == 2:
        return operation(image)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hsv[:, :, 2] = operation(hsv[:, :, 2])
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)


def _intensity(image):
    if image.ndim == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[:, :, 2]


def equalize(image):
    """Equalize grayscale pixels or just the value channel of BGR pixels."""
    image = _check_image(image)
    return _on_intensity(image, cv2.equalizeHist)


def match_histogram(image, reference):
    """Map image intensity quantiles to the reference intensity quantiles."""
    image = _check_image(image)
    reference = _check_image(reference)
    target = _intensity(reference)
    reference_counts = np.bincount(target.ravel(), minlength=256)
    reference_cdf = np.cumsum(reference_counts, dtype=np.float64) / target.size

    def apply(source):
        counts = np.bincount(source.ravel(), minlength=256)
        source_cdf = np.cumsum(counts, dtype=np.float64) / source.size
        # Search the first target intensity whose cumulative probability
        # meets each source probability. This keeps a monotonic uint8 mapping.
        mapping = np.searchsorted(reference_cdf, source_cdf, side="left")
        return mapping[source].astype(np.uint8)

    return _on_intensity(image, apply)
