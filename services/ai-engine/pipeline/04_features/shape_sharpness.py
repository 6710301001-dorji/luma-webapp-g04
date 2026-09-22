"""Contour geometry and frequency-domain sharpness features."""

import cv2
import numpy as np


def contour_features(contour):
    """Return area, perimeter, bounding-box aspect ratio, and circularity."""
    if not isinstance(contour, np.ndarray) or contour.ndim != 3 or contour.shape[1:] != (1, 2) or len(contour) < 3:
        raise ValueError("contour must have OpenCV shape (N, 1, 2) with N >= 3")
    if not np.issubdtype(contour.dtype, np.number):
        raise ValueError("contour coordinates must be numeric")
    perimeter = cv2.arcLength(contour, True)
    if perimeter <= 0:
        raise ValueError("contour must have positive perimeter")
    # Simplify pixel staircase artifacts before measuring circularity.
    smooth = cv2.approxPolyDP(contour, 0.01 * perimeter, True)
    area = float(cv2.contourArea(smooth))
    perimeter = float(cv2.arcLength(smooth, True))
    _, _, width, height = cv2.boundingRect(smooth)
    return {
        "area": area,
        "perimeter": perimeter,
        "aspect_ratio": width / height,
        "circularity": float(4 * np.pi * area / perimeter**2) if perimeter else 0.0,
    }


def sharpness(image, cutoff=0.25):
    """Measure high-frequency power above cutoff cycles per pixel."""
    if not isinstance(image, np.ndarray) or image.dtype != np.uint8 or image.size == 0:
        raise ValueError("image must be a nonempty uint8 array")
    if image.ndim == 3 and image.shape[2] == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    elif image.ndim == 2:
        gray = image
    else:
        raise ValueError("image must be grayscale or BGR")
    if isinstance(cutoff, bool) or not isinstance(cutoff, (int, float)) or not 0 < cutoff < 0.5:
        raise ValueError("cutoff must be between 0 and 0.5 cycles per pixel")
    fy = np.fft.fftfreq(gray.shape[0])[:, None]
    fx = np.fft.fftfreq(gray.shape[1])[None, :]
    high_frequency = fy**2 + fx**2 >= cutoff**2
    spectrum = np.fft.fft2(gray.astype(np.float64))
    return float(np.sum(np.abs(spectrum[high_frequency]) ** 2) / gray.size**2)
