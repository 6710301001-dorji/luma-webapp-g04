"""Spatial filter behavior and numerical separability checks."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest
from skimage.metrics import peak_signal_noise_ratio


path = Path(__file__).resolve().parents[1] / "pipeline/02_enhancement/spatial_filters.py"
spec = importlib.util.spec_from_file_location("spatial_filters", path)
filters = importlib.util.module_from_spec(spec)
spec.loader.exec_module(filters)


def test_box_and_gaussian_preserve_size_and_process_borders():
    image = np.zeros((9, 9), dtype=np.uint8)
    image[0, 0] = 255
    for operation in (filters.box, filters.gaussian):
        result = operation(image, 3)
        assert result.dtype == np.uint8 and result.shape == image.shape
        assert result[0, 0] > 0 and result[0, 1] > 0


def test_median_removes_salt_and_pepper_better_than_box():
    original = np.full((32, 32), 128, dtype=np.uint8)
    noisy = original.copy()
    noisy[::4, ::4] = 255
    noisy[2::4, 2::4] = 0
    box_error = np.mean((filters.box(noisy, 3).astype(float) - original) ** 2)
    median_error = np.mean((filters.median(noisy, 3).astype(float) - original) ** 2)
    assert median_error < box_error
    assert median_error == 0
    with np.errstate(divide="ignore"):
        assert peak_signal_noise_ratio(original, filters.median(noisy, 3), data_range=255) > peak_signal_noise_ratio(
            original, filters.box(noisy, 3), data_range=255
        )


def test_separable_result_matches_2d():
    image = np.random.default_rng(5).integers(0, 256, (64, 64), dtype=np.uint8)
    kernel = filters.gaussian_kernel(15)
    assert np.allclose(filters.filter_2d(image, kernel, kernel),
                       filters.filter_separable(image, kernel, kernel), atol=1)


def test_benchmark_reports_real_measurements():
    image = np.random.default_rng(8).integers(0, 256, (128, 128), dtype=np.uint8)
    result = filters.benchmark_separability(image, size=15, repeats=2)
    assert result["filter_2d_ms"] > 0 and result["filter_separable_ms"] > 0
    assert result["max_pixel_difference"] <= 1


@pytest.mark.parametrize("size", [0, 2, 4, True])
def test_invalid_kernel_sizes(size):
    with pytest.raises(ValueError):
        filters.box(np.zeros((4, 4), dtype=np.uint8), size)
