"""Tests for IoU, precision, recall, and five-case evaluation."""

import csv
import importlib.util
from pathlib import Path

import cv2
import numpy as np
import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "pipeline" / "05_evaluation" / "segmentation_metrics.py"
SPEC = importlib.util.spec_from_file_location("segmentation_metrics", MODULE_PATH)
segmentation_metrics = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(segmentation_metrics)
SAMPLES = Path(__file__).resolve().parents[1] / "samples" / "segmentation"


def test_identical_mask_has_perfect_scores():
    mask = np.zeros((20, 20), dtype=np.uint8)
    mask[5:15, 5:15] = 255
    result = segmentation_metrics.segmentation_quality(mask, mask)
    assert result["iou"] == 1.0
    assert result["precision"] == 1.0
    assert result["recall"] == 1.0


def test_nonoverlapping_masks_have_zero_scores():
    truth = np.zeros((20, 20), dtype=np.uint8)
    predicted = truth.copy()
    truth[2:7, 2:7] = 255
    predicted[12:17, 12:17] = 255
    result = segmentation_metrics.segmentation_quality(truth, predicted)
    assert result["iou"] == 0.0
    assert result["precision"] == 0.0
    assert result["recall"] == 0.0


def test_confusion_counts_and_scores_match_hand_calculation():
    truth = np.array([[1, 1], [0, 0]], dtype=np.uint8)
    predicted = np.array([[1, 0], [1, 0]], dtype=np.uint8)
    result = segmentation_metrics.segmentation_quality(truth, predicted)
    assert result == {
        "iou": pytest.approx(1 / 3),
        "precision": pytest.approx(1 / 2),
        "recall": pytest.approx(1 / 2),
        "true_positive": 1,
        "false_positive": 1,
        "false_negative": 1,
        "true_negative": 1,
    }


def test_five_ground_truth_fixtures_are_binary_and_evaluable():
    cases = {}
    for index in range(1, 6):
        truth = cv2.imread(str(SAMPLES / "ground_truth" / f"case_{index:02d}.png"), cv2.IMREAD_GRAYSCALE)
        prediction = cv2.imread(str(SAMPLES / "predictions" / f"case_{index:02d}.png"), cv2.IMREAD_GRAYSCALE)
        assert truth is not None and prediction is not None
        assert set(np.unique(truth)).issubset({0, 255})
        assert set(np.unique(prediction)).issubset({0, 255})
        cases[f"case_{index:02d}"] = (truth, prediction)
    rows = segmentation_metrics.evaluate_cases(cases)
    assert len(rows) == 5
    assert all(0 <= row["iou"] <= 1 for row in rows)
    assert len({round(row["iou"], 4) for row in rows}) > 1


def test_metric_explanations_cover_all_scores():
    explanations = segmentation_metrics.explain_metrics({"iou": 0.8, "precision": 0.9, "recall": 0.7})
    assert set(explanations) == {"iou", "precision", "recall"}
    assert all(len(text) > 20 for text in explanations.values())


def test_csv_has_no_empty_values(tmp_path):
    mask = np.ones((8, 8), dtype=np.uint8)
    rows = segmentation_metrics.evaluate_cases({f"case_{index}": (mask, mask) for index in range(5)})
    output = tmp_path / "segmentation_metrics.csv"
    segmentation_metrics.write_csv(rows, output)
    with output.open(newline="", encoding="utf-8") as source:
        saved = list(csv.DictReader(source))
    assert len(saved) == 5
    assert all(value != "" for row in saved for value in row.values())


def test_fewer_than_five_cases_are_rejected():
    mask = np.zeros((8, 8), dtype=np.uint8)
    with pytest.raises(ValueError, match="five"):
        segmentation_metrics.evaluate_cases({"only": (mask, mask)})


@pytest.mark.parametrize("prediction", [None, np.zeros((5, 5, 3), dtype=np.uint8), np.full((5, 5), 2, dtype=np.uint8)])
def test_invalid_masks_are_rejected(prediction):
    truth = np.zeros((5, 5), dtype=np.uint8)
    with pytest.raises(ValueError):
        segmentation_metrics.segmentation_quality(truth, prediction)

