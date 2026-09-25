"""Acceptance tests for deterministic and explainable rule-based tags."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "pipeline" / "04_features" / "auto_tag.py"
SPEC = importlib.util.spec_from_file_location("auto_tag", MODULE_PATH)
auto_tag = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(auto_tag)


def _solid(bgr, shape=(80, 120)):
    return np.full((*shape, 3), bgr, dtype=np.uint8)


def test_orange_image_is_tagged_warm_with_a_reason():
    result = auto_tag.classify(_solid((0, 128, 255)))
    assert "warm" in result["tags"]
    assert "cool" not in result["tags"]
    assert "threshold" in result["reasons"]["warm"]


def test_blue_image_is_tagged_cool_with_a_reason():
    result = auto_tag.classify(_solid((255, 0, 0)))
    assert "cool" in result["tags"]
    assert "warm" not in result["tags"]
    assert "threshold" in result["reasons"]["cool"]


def test_grayscale_image_is_tagged_monochrome():
    result = auto_tag.classify(_solid((128, 128, 128)))
    assert "monochrome" in result["tags"]
    assert "warm" not in result["tags"]
    assert "cool" not in result["tags"]


def test_brightness_and_contrast_rules_use_explainable_thresholds():
    dark = auto_tag.classify(_solid((20, 20, 20)))
    bright = auto_tag.classify(_solid((230, 230, 230)))
    split = np.zeros((80, 120, 3), dtype=np.uint8)
    split[:, 60:] = 255
    contrast = auto_tag.classify(split)

    assert {"dark", "low-contrast"}.issubset(dark["tags"])
    assert {"bright", "low-contrast"}.issubset(bright["tags"])
    assert "high-contrast" in contrast["tags"]


@pytest.mark.parametrize(("shape", "expected"), [
    ((60, 120), "landscape-orientation"),
    ((120, 60), "portrait-orientation"),
    ((80, 80), "square-orientation"),
])
def test_orientation_tag_uses_image_aspect_ratio(shape, expected):
    result = auto_tag.classify(_solid((128, 128, 128), shape))
    assert expected in result["tags"]


def test_same_image_returns_identical_tags_and_reasons():
    image = np.random.default_rng(65).integers(0, 256, (73, 91, 3), dtype=np.uint8)
    assert auto_tag.classify(image) == auto_tag.classify(image.copy())


def test_every_tag_has_exactly_one_reason():
    result = auto_tag.classify(_solid((0, 128, 255)))
    assert set(result["tags"]) == set(result["reasons"])
    assert all(isinstance(reason, str) and reason for reason in result["reasons"].values())


@pytest.mark.parametrize("image", [
    None,
    np.array([], dtype=np.uint8),
    np.zeros((5, 5), dtype=np.uint8),
    np.zeros((5, 5, 4), dtype=np.uint8),
    np.zeros((5, 5, 3), dtype=np.float32),
])
def test_invalid_images_are_rejected(image):
    with pytest.raises(ValueError):
        auto_tag.classify(image)
