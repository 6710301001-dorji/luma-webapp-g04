"""Tests for HSV segmentation, morphology, contours, and alpha output."""

import importlib.util
from pathlib import Path

import cv2
import numpy as np
import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "pipeline" / "03_segmentation" / "segmentation.py"
SPEC = importlib.util.spec_from_file_location("segmentation", MODULE_PATH)
segmentation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(segmentation)


def test_red_hue_wraparound_selects_both_ends_of_opencv_hue_range():
    hsv = np.array([[[0, 255, 255], [179, 255, 255], [60, 255, 255]]], dtype=np.uint8)
    image = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    mask = segmentation.selective_color_mask(image, center_degrees=0, tolerance_degrees=5)
    assert mask.tolist() == [[255, 255, 0]]


def test_low_saturation_and_value_pixels_are_rejected():
    hsv = np.array([[[30, 255, 255], [30, 20, 255], [30, 255, 20]]], dtype=np.uint8)
    image = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    mask = segmentation.selective_color_mask(image, 60, saturation_min=60, value_min=40)
    assert mask.tolist() == [[255, 0, 0]]


def test_morphology_removes_noise_and_closes_a_small_hole():
    mask = np.zeros((31, 31), dtype=np.uint8)
    cv2.rectangle(mask, (8, 8), (22, 22), 255, -1)
    mask[15, 15] = 0
    mask[2, 2] = 255
    cleaned = segmentation.clean_mask(mask, kernel_size=3)
    assert cleaned[2, 2] == 0
    assert cleaned[15, 15] == 255


def test_find_objects_reports_two_circles_and_bounding_boxes():
    mask = np.zeros((100, 120), dtype=np.uint8)
    cv2.circle(mask, (25, 50), 12, 255, -1)
    cv2.circle(mask, (85, 50), 18, 255, -1)
    objects = segmentation.find_objects(mask)
    assert len(objects) == 2
    assert objects[0]["area"] > objects[1]["area"]
    assert objects[0]["bounding_box"] == {"x": 67, "y": 32, "width": 37, "height": 37}


def test_remove_background_returns_real_alpha_channel():
    image = np.full((4, 5, 3), (10, 20, 30), dtype=np.uint8)
    mask = np.zeros((4, 5), dtype=np.uint8)
    mask[1:3, 2:4] = 255
    result = segmentation.remove_background(image, mask)
    assert result.shape == (4, 5, 4)
    assert np.array_equal(result[:, :, :3], image)
    assert np.array_equal(result[:, :, 3], mask)


def test_complete_segmentation_returns_mask_objects_and_bgra():
    image = np.zeros((80, 100, 3), dtype=np.uint8)
    cv2.circle(image, (30, 40), 12, (0, 0, 255), -1)
    cv2.circle(image, (72, 40), 10, (0, 0, 255), -1)
    result = segmentation.segment(image, center_degrees=0, tolerance_degrees=10)
    assert len(result["objects"]) == 2
    assert result["mask"].dtype == np.uint8
    assert result["image"].shape == (80, 100, 4)


@pytest.mark.parametrize("bad_image", [None, np.array([], dtype=np.uint8), np.zeros((5, 5), dtype=np.uint8)])
def test_invalid_images_are_rejected(bad_image):
    with pytest.raises(ValueError):
        segmentation.selective_color_mask(bad_image, 0)
