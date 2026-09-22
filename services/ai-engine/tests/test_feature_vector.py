"""Tests for deterministic, size-independent histogram feature vectors."""

import importlib.util
from pathlib import Path

import cv2
import numpy as np
import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "pipeline" / "04_features" / "feature_vector.py"
SPEC = importlib.util.spec_from_file_location("feature_vector", MODULE_PATH)
feature_vector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(feature_vector)


def _scene(color, size=(80, 120)):
    image = np.full((*size, 3), color, dtype=np.uint8)
    cv2.circle(image, (size[1] // 2, size[0] // 2), min(size) // 5, tuple(min(255, value + 20) for value in color), -1)
    return image


def test_vector_length_is_fixed_for_different_image_sizes():
    small = _scene((180, 130, 80), (40, 60))
    large = _scene((180, 130, 80), (240, 320))
    assert feature_vector.extract(small).shape == (feature_vector.FEATURE_LENGTH,)
    assert feature_vector.extract(large).shape == (feature_vector.FEATURE_LENGTH,)


def test_same_image_is_deterministic():
    image = _scene((200, 150, 90))
    assert np.array_equal(feature_vector.extract(image), feature_vector.extract(image))


def test_resized_image_remains_close():
    image = _scene((190, 140, 80))
    resized = cv2.resize(image, (240, 160), interpolation=cv2.INTER_NEAREST)
    assert feature_vector.distance(feature_vector.extract(image), feature_vector.extract(resized)) < 0.01


def test_similar_sky_images_are_closer_than_an_indoor_colored_image():
    sky_one = _scene((220, 160, 90))
    sky_two = _scene((225, 165, 95))
    indoor = _scene((50, 70, 190))
    sky_distance = feature_vector.distance(feature_vector.extract(sky_one), feature_vector.extract(sky_two))
    indoor_distance = feature_vector.distance(feature_vector.extract(sky_one), feature_vector.extract(indoor))
    assert sky_distance < indoor_distance


def test_grayscale_image_produces_finite_features():
    gray = np.tile(np.arange(64, dtype=np.uint8), (64, 1)) * 4
    result = feature_vector.extract(gray)
    assert result.shape == (feature_vector.FEATURE_LENGTH,)
    assert np.all(np.isfinite(result))


def test_histogram_sections_are_normalized():
    result = feature_vector.extract(_scene((20, 100, 200)))
    for start in (0, 8, 16):
        assert result[start:start + 8].sum() == pytest.approx(1.0)


@pytest.mark.parametrize("bad_image", [None, np.array([], dtype=np.uint8), np.zeros((4, 4, 4), dtype=np.uint8)])
def test_invalid_images_are_rejected(bad_image):
    with pytest.raises(ValueError):
        feature_vector.extract(bad_image)

