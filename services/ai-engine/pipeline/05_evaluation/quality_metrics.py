"""Objective image-quality metrics and complete before/after tables."""

import csv
import math

import numpy as np
from skimage.metrics import peak_signal_noise_ratio, structural_similarity


REQUIRED_ENHANCEMENT_METHODS = (
    "gamma", "log", "contrast_stretch", "equalization", "histogram_matching",
    "box", "gaussian", "median",
)


def _check_pair(reference, candidate):
    for name, image in (("reference", reference), ("candidate", candidate)):
        if not isinstance(image, np.ndarray) or image.dtype != np.uint8 or image.size == 0:
            raise ValueError(f"{name} must be a nonempty uint8 array")
        if image.ndim != 2 and not (image.ndim == 3 and image.shape[2] == 3):
            raise ValueError(f"{name} must be grayscale or three-channel BGR")
    if reference.shape != candidate.shape:
        raise ValueError("reference and candidate must have the same shape")
    if min(reference.shape[:2]) < 3:
        raise ValueError("images must be at least 3 by 3 pixels for SSIM")


def image_quality(reference, candidate):
    """Return PSNR and SSIM for equally sized uint8 images.

    Infinite PSNR is retained for identical images because it is the correct
    mathematical result when the mean squared error is zero.
    """
    _check_pair(reference, candidate)
    if np.array_equal(reference, candidate):
        return {"psnr": float("inf"), "ssim": 1.0}
    smallest_side = min(reference.shape[:2])
    window_size = min(7, smallest_side if smallest_side % 2 else smallest_side - 1)
    channel_axis = -1 if reference.ndim == 3 else None
    return {
        "psnr": float(peak_signal_noise_ratio(reference, candidate, data_range=255)),
        "ssim": float(structural_similarity(
            reference,
            candidate,
            data_range=255,
            channel_axis=channel_axis,
            win_size=window_size,
        )),
    }


def before_after_table(reference, before, enhanced_images):
    """Build a complete metric row for every required enhancement method."""
    if not isinstance(enhanced_images, dict):
        raise ValueError("enhanced_images must map method names to images")
    missing = [name for name in REQUIRED_ENHANCEMENT_METHODS if name not in enhanced_images]
    if missing:
        raise ValueError("missing enhancement results: " + ", ".join(missing))

    before_metrics = image_quality(reference, before)
    rows = []
    for method in REQUIRED_ENHANCEMENT_METHODS:
        after_metrics = image_quality(reference, enhanced_images[method])
        rows.append({
            "method": method,
            "before_psnr": before_metrics["psnr"],
            "after_psnr": after_metrics["psnr"],
            "psnr_change": _metric_change(before_metrics["psnr"], after_metrics["psnr"]),
            "before_ssim": before_metrics["ssim"],
            "after_ssim": after_metrics["ssim"],
            "ssim_change": after_metrics["ssim"] - before_metrics["ssim"],
        })
    return rows


def _metric_change(before, after):
    if math.isinf(before) and math.isinf(after):
        return 0.0
    return after - before


def write_csv(rows, output_path):
    """Write a before/after table to a report-ready CSV file."""
    if not rows:
        raise ValueError("rows must not be empty")
    columns = (
        "method", "before_psnr", "after_psnr", "psnr_change",
        "before_ssim", "after_ssim", "ssim_change",
    )
    for row in rows:
        if not isinstance(row, dict) or any(column not in row or row[column] is None for column in columns):
            raise ValueError("every row must contain a value for every table column")
    with open(output_path, "w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows({column: row[column] for column in columns} for row in rows)
