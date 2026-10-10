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


# --- find_faces() (Function page "จับหน้า", replaces the old color-box tool) ---
#
# No real photo is committed here — a person's likeness has consent/redistribution
# concerns the same way the sunflower dataset does (see samples/segmentation/).
# Detector *wiring* (box clipping, min_size filter, sort order, confidence
# passthrough) is tested by mocking FaceDetectorYN.detect(); a blank synthetic
# image proves the "no face -> []" path with the real model. Genuine detection
# accuracy on a real photo was checked by hand against a public-domain group
# selfie (opencv_zoo's own YuNet demo image) — 86 faces, confidences 0.60-0.99,
# not committed to the repo.

def test_no_face_in_a_blank_image_returns_an_empty_list_not_an_error():
    blank = np.zeros((64, 64, 3), dtype=np.uint8)
    assert segmentation.find_faces(blank) == []


@pytest.mark.parametrize("confidence_min", [True, -0.1, 1.1, float("nan")])
def test_find_faces_rejects_invalid_confidence_min(confidence_min):
    with pytest.raises(ValueError):
        segmentation.find_faces(np.zeros((10, 10, 3), dtype=np.uint8), confidence_min=confidence_min)


@pytest.mark.parametrize("min_size", [True, -1])
def test_find_faces_rejects_invalid_min_size(min_size):
    with pytest.raises(ValueError):
        segmentation.find_faces(np.zeros((10, 10, 3), dtype=np.uint8), min_size=min_size)


@pytest.mark.parametrize("bad_image", [None, np.array([], dtype=np.uint8), np.zeros((5, 5), dtype=np.uint8)])
def test_find_faces_rejects_invalid_images(bad_image):
    with pytest.raises(ValueError):
        segmentation.find_faces(bad_image)


class _StubDetector:
    """Stands in for cv2.FaceDetectorYN — returns canned rows shaped like the
    real API: [x, y, w, h, <5 landmark pairs>, score]. Only x, y, w, h, score
    matter to find_faces(); the landmark columns are filler so row[-1] is score.
    """

    def __init__(self, rows):
        self._rows = None if rows is None else np.array(rows, dtype=np.float32)

    def setInputSize(self, size):
        pass

    def detect(self, image):
        return None, self._rows


def test_find_faces_clips_a_box_that_overshoots_the_image_edge(monkeypatch):
    # x=90, w=30 on a 100-wide image -> right edge at 120, must clip to 100
    monkeypatch.setattr(
        segmentation.cv2, "FaceDetectorYN_create",
        lambda *a, **k: _StubDetector([[90, 5, 30, 20, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.9]]),
    )
    faces = segmentation.find_faces(np.zeros((50, 100, 3), dtype=np.uint8), min_size=1)
    assert faces == [{"bounding_box": {"x": 90, "y": 5, "width": 10, "height": 20},
                      "area": 200.0, "confidence": pytest.approx(0.9)}]


def test_find_faces_drops_boxes_smaller_than_min_size(monkeypatch):
    rows = [
        [0, 0, 40, 40, *([0] * 10), 0.8],   # kept: 40x40 >= min_size
        [0, 0, 10, 40, *([0] * 10), 0.9],   # dropped: width 10 < min_size
    ]
    monkeypatch.setattr(segmentation.cv2, "FaceDetectorYN_create", lambda *a, **k: _StubDetector(rows))
    faces = segmentation.find_faces(np.zeros((50, 50, 3), dtype=np.uint8), min_size=20)
    assert len(faces) == 1
    assert faces[0]["bounding_box"]["width"] == 40


def test_find_faces_sorts_by_area_descending_and_keeps_confidence(monkeypatch):
    rows = [
        [0, 0, 10, 10, *([0] * 10), 0.7],   # area 100, smaller
        [0, 0, 20, 20, *([0] * 10), 0.6],   # area 400, larger
    ]
    monkeypatch.setattr(segmentation.cv2, "FaceDetectorYN_create", lambda *a, **k: _StubDetector(rows))
    faces = segmentation.find_faces(np.zeros((50, 50, 3), dtype=np.uint8), min_size=1)
    assert [f["area"] for f in faces] == [400.0, 100.0]
    assert [f["confidence"] for f in faces] == pytest.approx([0.6, 0.7])
