"""Spatial noise filters with preserved borders and measurable separability."""

from time import perf_counter

import cv2
import numpy as np


def _check(image, size):
    if not isinstance(image, np.ndarray) or image.dtype != np.uint8 or image.size == 0:
        raise ValueError("image must be a nonempty uint8 array")
    if image.ndim != 2 and not (image.ndim == 3 and image.shape[2] == 3):
        raise ValueError("image must be grayscale or BGR")
    if isinstance(size, bool) or not isinstance(size, int) or size < 3 or size % 2 != 1:
        raise ValueError("kernel size must be an odd integer at least 3")


def box(image, size=3):
    """Average over a square neighborhood, reflecting pixels at borders."""
    _check(image, size)
    return cv2.blur(image, (size, size), borderType=cv2.BORDER_REFLECT_101)


def gaussian(image, size=3, sigma=0):
    """Gaussian blur with selectable odd kernel size and optional sigma."""
    _check(image, size)
    if isinstance(sigma, bool) or not isinstance(sigma, (int, float)) or not np.isfinite(sigma) or sigma < 0:
        raise ValueError("sigma must be a finite nonnegative number")
    return cv2.GaussianBlur(image, (size, size), sigma, borderType=cv2.BORDER_REFLECT_101)


def median(image, size=3):
    """Remove impulse noise while retaining edges; OpenCV replicates borders."""
    _check(image, size)
    return cv2.medianBlur(image, size)


def gaussian_kernel(size, sigma=0):
    """Return a 1D Gaussian kernel for direct or separable filtering."""
    if isinstance(size, bool) or not isinstance(size, int) or size < 3 or size % 2 != 1:
        raise ValueError("kernel size must be an odd integer at least 3")
    if isinstance(sigma, bool) or not isinstance(sigma, (int, float)) or not np.isfinite(sigma) or sigma < 0:
        raise ValueError("sigma must be a finite nonnegative number")
    return cv2.getGaussianKernel(size, sigma, cv2.CV_32F)


def filter_2d(image, kernel_x, kernel_y):
    """Reference 2D convolution with the outer-product Gaussian kernel."""
    _check(image, len(kernel_x))
    kernel = np.asarray(kernel_y, dtype=np.float32) @ np.asarray(kernel_x, dtype=np.float32).T
    return cv2.filter2D(image, cv2.CV_32F, kernel, borderType=cv2.BORDER_REFLECT_101)


def filter_separable(image, kernel_x, kernel_y):
    """Equivalent convolution using one horizontal and one vertical pass."""
    _check(image, len(kernel_x))
    return cv2.sepFilter2D(image, cv2.CV_32F, kernel_x, kernel_y, borderType=cv2.BORDER_REFLECT_101)


def benchmark_separability(image, size=15, repeats=5):
    """Measure both paths on the same image and report median runtime and error."""
    _check(image, size)
    if isinstance(repeats, bool) or not isinstance(repeats, int) or repeats < 1:
        raise ValueError("repeats must be a positive integer")
    kernel = gaussian_kernel(size)
    timings = []
    outputs = []
    for operation in (filter_2d, filter_separable):
        operation(image, kernel, kernel)  # Warm up OpenCV before timing.
        samples = []
        for _ in range(repeats):
            start = perf_counter()
            result = operation(image, kernel, kernel)
            samples.append(perf_counter() - start)
        timings.append(float(np.median(samples)))
        outputs.append(result)
    return {
        "filter_2d_ms": timings[0] * 1000,
        "filter_separable_ms": timings[1] * 1000,
        "speedup": timings[0] / timings[1],
        "max_pixel_difference": float(np.max(np.abs(outputs[0] - outputs[1]))),
    }
