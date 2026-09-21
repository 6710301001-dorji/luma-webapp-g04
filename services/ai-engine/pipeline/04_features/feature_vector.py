"""Fixed-length image descriptors based on normalized histograms and statistics."""

import cv2
import numpy as np
from scipy.stats import kurtosis, skew


HISTOGRAM_BINS = 8
FEATURE_LENGTH = HISTOGRAM_BINS * 3 + 4


def _check_image(image):
    if not isinstance(image, np.ndarray) or image.dtype != np.uint8 or image.size == 0:
        raise ValueError("image must be a nonempty uint8 array")
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.ndim == 3 and image.shape[2] == 3:
        return image
    raise ValueError("image must be grayscale or three-channel BGR")


def extract(image):
    """Return a deterministic 28-value descriptor for any image dimensions.

    The first 24 values are normalized eight-bin BGR histograms. The final
    four values are normalized grayscale mean, standard deviation, skewness,
    and excess kurtosis. Histogram normalization removes image-size effects.
    """
    image = _check_image(image)
    features = []
    for channel_index in range(3):
        histogram = cv2.calcHist([image], [channel_index], None, [HISTOGRAM_BINS], [0, 256]).ravel()
        features.extend((histogram / image.shape[0] / image.shape[1]).tolist())

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float64).ravel()
    variance = float(gray.var())
    features.extend([
        float(gray.mean() / 255.0),
        float(gray.std() / 127.5),
        0.0 if variance == 0 else float(np.clip(skew(gray, bias=True), -10, 10) / 10),
        0.0 if variance == 0 else float(np.clip(kurtosis(gray, fisher=True, bias=True), -10, 10) / 10),
    ])
    return np.asarray(features, dtype=np.float32)


def distance(first, second):
    """Return Euclidean distance between two compatible feature vectors."""
    first = np.asarray(first)
    second = np.asarray(second)
    if first.shape != (FEATURE_LENGTH,) or second.shape != (FEATURE_LENGTH,):
        raise ValueError(f"feature vectors must each have shape ({FEATURE_LENGTH},)")
    if not np.all(np.isfinite(first)) or not np.all(np.isfinite(second)):
        raise ValueError("feature vectors must contain only finite values")
    return float(np.linalg.norm(first.astype(np.float64) - second.astype(np.float64)))

