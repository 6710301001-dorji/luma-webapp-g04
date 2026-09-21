"""Known geometry and blurred-image comparisons."""

import importlib.util
from pathlib import Path

import cv2
import numpy as np
import pytest


path = Path(__file__).resolve().parents[1] / "pipeline/04_features/shape_sharpness.py"
spec = importlib.util.spec_from_file_location("shape_sharpness", path)
features = importlib.util.module_from_spec(spec)
spec.loader.exec_module(features)


def _largest_contour(image):
    contours, _ = cv2.findContours(image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return max(contours, key=cv2.contourArea)


def test_circle_is_more_circular_than_square():
    circle = np.zeros((160, 160), dtype=np.uint8)
    square = np.zeros_like(circle)
    cv2.circle(circle, (80, 80), 50, 255, -1)
    cv2.rectangle(square, (30, 30), (130, 130), 255, -1)
    round_features = features.contour_features(_largest_contour(circle))
    square_features = features.contour_features(_largest_contour(square))
    assert round_features["circularity"] > 0.9
    assert square_features["circularity"] < 0.85
    assert round_features["area"] > 0 and round_features["perimeter"] > 0
    assert square_features["aspect_ratio"] == 1.0


def test_high_frequency_energy_decreases_after_blur():
    image = np.random.default_rng(12).integers(0, 256, (128, 128), dtype=np.uint8)
    blurred = cv2.GaussianBlur(image, (9, 9), 3)
    assert features.sharpness(image) > features.sharpness(blurred)
    assert features.sharpness(np.zeros_like(image)) == 0


def test_color_image_is_accepted():
    color = np.random.default_rng(4).integers(0, 256, (64, 64, 3), dtype=np.uint8)
    assert features.sharpness(color) > 0


@pytest.mark.parametrize("bad", [np.array([], dtype=np.uint8), np.ones((5, 5), dtype=np.float32)])
def test_bad_images_are_rejected(bad):
    with pytest.raises(ValueError):
        features.sharpness(bad)
