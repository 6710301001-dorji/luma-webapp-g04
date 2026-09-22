"""Histogram and quality decisions on images with known pixel values."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "pipeline" / "02_enhancement" / "histogram.py"
SPEC = importlib.util.spec_from_file_location("image_histogram", MODULE_PATH)
image_histogram = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(image_histogram)


def test_constant_gray_image_has_one_bin_and_zero_variance():
    image = np.full((10, 12), 80, dtype=np.uint8)
    counts = image_histogram.histogram(image)["gray"]
    stats = image_histogram.statistics(image)["gray"]
    assert counts.shape == (256,)
    assert counts[80] == 120
    assert counts.sum() == 120
    assert stats == {"mean": 80.0, "variance": 0.0, "skewness": 0.0, "kurtosis": 0.0}
    assert image_histogram.assess_quality(image)["low_contrast"] is True


def test_half_black_half_white_has_known_statistics():
    image = np.array([[0, 0, 255, 255]], dtype=np.uint8)
    stats = image_histogram.statistics(image)["gray"]
    assert stats["mean"] == pytest.approx(127.5)
    assert stats["variance"] == pytest.approx(16256.25)
    assert stats["skewness"] == pytest.approx(0)
    assert stats["kurtosis"] == pytest.approx(-2)
    assert image_histogram.assess_quality(image)["low_contrast"] is False


def test_bgr_channels_are_calculated_separately():
    image = np.zeros((2, 3, 3), dtype=np.uint8)
    image[:, :, 0] = 10
    image[:, :, 1] = 100
    image[:, :, 2] = 240
    counts = image_histogram.histogram(image)
    stats = image_histogram.statistics(image)
    assert counts["blue"][10] == 6
    assert counts["green"][100] == 6
    assert counts["red"][240] == 6
    assert stats["red"]["mean"] == 240


def test_quality_flags_dark_bright_and_narrow_histograms():
    dark = np.full((8, 8), 20, dtype=np.uint8)
    bright = np.full((8, 8), 230, dtype=np.uint8)
    assert image_histogram.assess_quality(dark)["too_dark"] is True
    assert image_histogram.assess_quality(bright)["too_bright"] is True
    assert image_histogram.assess_quality(bright)["low_contrast"] is True


def test_plot_written_and_invalid_dtype_rejected(tmp_path):
    image = np.tile(np.arange(256, dtype=np.uint8), (4, 1))
    path = tmp_path / "histogram.png"
    image_histogram.save_histogram_plot(image, path)
    assert path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    with pytest.raises(ValueError, match="uint8"):
        image_histogram.histogram(image.astype(np.float32))
