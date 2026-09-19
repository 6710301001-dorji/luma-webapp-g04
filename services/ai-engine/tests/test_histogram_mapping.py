"""Acceptance checks for histogram equalization and matching."""

import importlib.util
from pathlib import Path

import cv2
import numpy as np
import pytest


path = Path(__file__).resolve().parents[1] / "pipeline/02_enhancement/histogram_mapping.py"
spec = importlib.util.spec_from_file_location("histogram_mapping", path)
mapping = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mapping)


def test_equalization_expands_low_contrast_image():
    image = np.tile(np.array([100, 101, 102, 103], dtype=np.uint8), (16, 1))
    result = mapping.equalize(image)
    assert result.dtype == np.uint8 and result.shape == image.shape
    assert result.var() > image.var()
    assert result.min() == 0 and result.max() == 255
    assert np.max(np.abs(mapping.equalize(result).astype(int) - result.astype(int))) <= 1


def test_matching_moves_values_to_reference_distribution():
    source = np.array([[0, 0, 10, 10]], dtype=np.uint8)
    reference = np.array([[100, 100, 200, 200]], dtype=np.uint8)
    assert mapping.match_histogram(source, reference).tolist() == [[100, 100, 200, 200]]


def test_color_mapping_changes_value_without_large_hue_shift():
    hsv = np.zeros((8, 4, 3), dtype=np.uint8)
    hsv[:, :, 0] = 50
    hsv[:, :, 1] = 180
    hsv[:, :, 2] = np.array([80, 85, 90, 95], dtype=np.uint8)
    image = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    reference = np.full((8, 4), 220, dtype=np.uint8)
    for result in (mapping.equalize(image), mapping.match_histogram(image, reference)):
        output_hsv = cv2.cvtColor(result, cv2.COLOR_BGR2HSV)
        assert result.dtype == np.uint8 and result.shape == image.shape
        visible = output_hsv[:, :, 2] > 0  # Hue is undefined for black pixels.
        assert np.max(np.abs(output_hsv[:, :, 0][visible].astype(int) - 50)) <= 1


@pytest.mark.parametrize("bad", [np.array([], dtype=np.uint8), np.zeros((2, 2), dtype=np.float32),
                                  np.zeros((2, 2, 4), dtype=np.uint8)])
def test_invalid_images_are_rejected(bad):
    with pytest.raises(ValueError):
        mapping.equalize(bad)
