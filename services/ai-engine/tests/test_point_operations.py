"""Known pixel values for the point-operation acceptance criteria."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest


path = Path(__file__).resolve().parents[1] / "pipeline/02_enhancement/point_operations.py"
spec = importlib.util.spec_from_file_location("point_operations", path)
operations = importlib.util.module_from_spec(spec)
spec.loader.exec_module(operations)


def test_gamma_identity_and_brightness():
    image = np.array([[0, 32, 128, 255]], dtype=np.uint8)
    assert np.array_equal(operations.gamma(image, 1.0), image)
    assert operations.gamma(image, 0.5).mean() > image.mean()
    assert operations.gamma(image, 2.0).mean() < image.mean()


def test_log_transform_expands_darks_without_overflow():
    image = np.array([[0, 1, 64, 250, 255]], dtype=np.uint8)
    result = operations.log_transform(image)
    assert result.dtype == np.uint8
    assert result[0, 0] == 0 and result[0, -1] == 255
    assert result[0, 2] > image[0, 2]
    assert np.all(np.diff(result.astype(np.int16)) >= 0)


def test_contrast_stretch_uses_full_range():
    image = np.array([[100, 125, 150]], dtype=np.uint8)
    result = operations.contrast_stretch(image)
    assert result.tolist() == [[0, 128, 255]]
    assert result.dtype == np.uint8


def test_constant_and_color_images_preserve_shape_and_type():
    constant = np.full((2, 2, 3), 100, dtype=np.uint8)
    assert np.array_equal(operations.contrast_stretch(constant), constant)
    for transform in (lambda x: operations.gamma(x, 0.5), operations.log_transform,
                      operations.contrast_stretch):
        result = transform(constant)
        assert result.shape == constant.shape and result.dtype == np.uint8


@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan"), True])
def test_bad_gamma_is_rejected(value):
    with pytest.raises(ValueError):
        operations.gamma(np.array([[10]], dtype=np.uint8), value)
