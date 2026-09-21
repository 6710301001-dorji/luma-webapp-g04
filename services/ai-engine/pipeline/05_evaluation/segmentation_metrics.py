"""Pixel-level segmentation metrics for binary masks."""

import csv

import numpy as np


def _binary_pair(ground_truth, prediction):
    masks = []
    for name, mask in (("ground_truth", ground_truth), ("prediction", prediction)):
        if not isinstance(mask, np.ndarray) or mask.ndim != 2 or mask.size == 0:
            raise ValueError(f"{name} must be a nonempty two-dimensional array")
        unique = np.unique(mask)
        if not set(unique.tolist()).issubset({0, 1, 255, False, True}):
            raise ValueError(f"{name} must be binary (0/1 or 0/255)")
        masks.append(mask.astype(bool))
    if masks[0].shape != masks[1].shape:
        raise ValueError("ground_truth and prediction must have the same shape")
    return masks


def segmentation_quality(ground_truth, prediction):
    """Return IoU, precision, recall, and pixel confusion counts.

    A pair of empty masks is treated as a perfect result. Precision is 1.0
    when neither mask contains a positive prediction, and recall is 1.0 when
    the ground truth contains no positive pixels.
    """
    truth, predicted = _binary_pair(ground_truth, prediction)
    true_positive = int(np.count_nonzero(truth & predicted))
    false_positive = int(np.count_nonzero(~truth & predicted))
    false_negative = int(np.count_nonzero(truth & ~predicted))
    true_negative = int(np.count_nonzero(~truth & ~predicted))

    union = true_positive + false_positive + false_negative
    predicted_positive = true_positive + false_positive
    actual_positive = true_positive + false_negative
    return {
        "iou": true_positive / union if union else 1.0,
        "precision": true_positive / predicted_positive if predicted_positive else 1.0,
        "recall": true_positive / actual_positive if actual_positive else 1.0,
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "true_negative": true_negative,
    }


def explain_metrics(metrics):
    """Describe what the three quality scores mean for a report reader."""
    required = ("iou", "precision", "recall")
    if not isinstance(metrics, dict) or any(name not in metrics for name in required):
        raise ValueError("metrics must contain iou, precision, and recall")
    return {
        "iou": "IoU measures overlap between the predicted and hand-drawn object regions.",
        "precision": "Precision is the share of selected pixels that truly belong to the object.",
        "recall": "Recall is the share of hand-drawn object pixels found by the segmentation.",
    }


def evaluate_cases(cases):
    """Evaluate at least five named ground-truth and prediction pairs."""
    if not isinstance(cases, dict) or len(cases) < 5:
        raise ValueError("at least five named segmentation cases are required")
    rows = []
    for name, pair in cases.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("every case must have a nonempty name")
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError("each case must contain ground_truth and prediction")
        rows.append({"case": name, **segmentation_quality(pair[0], pair[1])})
    return rows


def write_csv(rows, output_path):
    """Save per-case segmentation scores and confusion counts."""
    if not rows:
        raise ValueError("rows must not be empty")
    columns = (
        "case", "iou", "precision", "recall", "true_positive",
        "false_positive", "false_negative", "true_negative",
    )
    for row in rows:
        if not isinstance(row, dict) or any(column not in row or row[column] is None for column in columns):
            raise ValueError("every row must contain every segmentation metric")
    with open(output_path, "w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        writer.writerows({column: row[column] for column in columns} for row in rows)

