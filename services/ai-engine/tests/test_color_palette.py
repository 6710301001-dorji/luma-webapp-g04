"""Dominant color extraction acceptance checks."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest


path = Path(__file__).resolve().parents[1] / "pipeline/04_features/color_palette.py"
spec = importlib.util.spec_from_file_location("color_palette", path)
palette = importlib.util.module_from_spec(spec)
spec.loader.exec_module(palette)


def test_solid_red_has_one_css_color():
    red_bgr = np.full((16, 16, 3), (0, 0, 255), dtype=np.uint8)
    assert palette.extract_palette(red_bgr) == [{"hex": "#ff0000", "proportion": 1.0}]


def test_half_red_half_blue_has_equal_proportions():
    image = np.zeros((20, 20, 3), dtype=np.uint8)
    image[:, :10] = (0, 0, 255)
    image[:, 10:] = (255, 0, 0)
    result = palette.extract_palette(image)
    assert {entry["hex"]: entry["proportion"] for entry in result} == {
        "#ff0000": 0.5, "#0000ff": 0.5
    }


def test_many_colors_return_five_sorted_proportions():
    rng = np.random.default_rng(3)
    image = rng.integers(0, 256, (80, 80, 3), dtype=np.uint8)
    result = palette.extract_palette(image)
    assert len(result) == 5
    assert all(len(entry["hex"]) == 7 and entry["hex"].startswith("#") for entry in result)
    assert sum(entry["proportion"] for entry in result) == pytest.approx(1)
    assert [entry["proportion"] for entry in result] == sorted(
        [entry["proportion"] for entry in result], reverse=True
    )


@pytest.mark.parametrize("image", [np.array([], dtype=np.uint8), np.zeros((3, 3), dtype=np.uint8),
                                   np.zeros((3, 3, 3), dtype=np.float32)])
def test_invalid_image_is_rejected(image):
    with pytest.raises(ValueError):
        palette.extract_palette(image)
