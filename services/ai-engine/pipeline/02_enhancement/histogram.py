"""Histogram-based quality assessment (Lecture 4, pp. 23-31)."""

import cv2
import numpy as np
from scipy.stats import kurtosis, skew


def _check_image(image):
    if not isinstance(image, np.ndarray) or image.dtype != np.uint8 or image.size == 0:
        raise ValueError("Expected a nonempty uint8 image array")
    if image.ndim == 2:
        return {"gray": image}
    if image.ndim == 3 and image.shape[2] == 3:
        return {"blue": image[:, :, 0], "green": image[:, :, 1], "red": image[:, :, 2]}
    raise ValueError("Expected a grayscale or 3-channel BGR image")


def histogram(image):
    """Return a 256-bin histogram per channel (Lecture 4, pp. 24-29)."""
    return {name: np.bincount(channel.ravel(), minlength=256)
            for name, channel in _check_image(image).items()}


def statistics(image):
    """Return population mean, variance, skewness and excess kurtosis (Lecture 4, p. 27).

    Constant images have zero variance; their skewness and kurtosis are defined
    here as zero instead of SciPy's undefined NaN values.
    """
    result = {}
    for name, channel in _check_image(image).items():
        values = channel.astype(np.float64).ravel()
        mean = float(values.mean())
        variance = float(values.var())
        result[name] = {
            "mean": mean,
            "variance": variance,
            "skewness": 0.0 if variance == 0 else float(skew(values, bias=True)),
            "kurtosis": 0.0 if variance == 0 else float(kurtosis(values, fisher=True, bias=True)),
        }
    return result


def assess_quality(image, dark_mean=64, bright_mean=192, narrow_range=64):
    """Flag dark, bright and low-contrast images using grayscale intensity.

    These are explainable starting thresholds, not learned classifications.
    The 5th-95th percentile range avoids one stray black or white pixel
    hiding an otherwise narrow histogram (Lecture 4, pp. 23-31).
    """
    _check_image(image)
    gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    mean = float(gray.mean())
    low, high = np.percentile(gray, [5, 95])
    return {
        "mean_intensity": mean,
        "p5": float(low),
        "p95": float(high),
        "too_dark": mean < dark_mean,
        "too_bright": mean > bright_mean,
        "low_contrast": bool(high - low < narrow_range),
    }


def save_histogram_plot(image, output_path):
    """Save a channel histogram figure for the report (Lecture 4, pp. 24-29)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"gray": "black", "blue": "blue", "green": "green", "red": "red"}
    fig, axis = plt.subplots(figsize=(7, 4))
    for name, counts in histogram(image).items():
        axis.plot(np.arange(256), counts, color=colors[name], label=name)
    axis.set(xlim=(0, 255), xlabel="Intensity", ylabel="Pixels", title="Image histogram")
    axis.legend()
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)
