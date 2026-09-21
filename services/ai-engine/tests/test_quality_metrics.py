"""Tests for PSNR, SSIM, complete tables, and CSV output."""

import csv
import importlib.util
from pathlib import Path

import cv2
import numpy as np
import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "pipeline" / "05_evaluation" / "quality_metrics.py"
SPEC = importlib.util.spec_from_file_location("quality_metrics", MODULE_PATH)
quality_metrics = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(quality_metrics)


def _load_enhancement_module(name):
    path = MODULE_PATH.parents[1] / "02_enhancement" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sample_images():
    clean = np.zeros((64, 64), dtype=np.uint8)
    cv2.rectangle(clean, (12, 12), (51, 51), 180, -1)
    cv2.circle(clean, (32, 32), 10, 240, -1)
    rng = np.random.default_rng(42)
    noisy = clean.copy()
    coordinates = rng.integers(0, 64, size=(2, 500))
    noisy[coordinates[0], coordinates[1]] = rng.choice([0, 255], size=500)
    return clean, noisy


def test_identical_image_has_perfect_metrics():
    image, _ = _sample_images()
    metrics = quality_metrics.image_quality(image, image)
    assert metrics["psnr"] == float("inf")
    assert metrics["ssim"] == pytest.approx(1.0)


def test_median_filter_improves_psnr_for_impulse_noise():
    clean, noisy = _sample_images()
    restored = cv2.medianBlur(noisy, 3)
    assert quality_metrics.image_quality(clean, restored)["psnr"] > quality_metrics.image_quality(clean, noisy)["psnr"]


def test_color_images_are_supported():
    image, noisy = _sample_images()
    color = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    noisy_color = cv2.cvtColor(noisy, cv2.COLOR_GRAY2BGR)
    metrics = quality_metrics.image_quality(color, noisy_color)
    assert 0 <= metrics["ssim"] < 1
    assert np.isfinite(metrics["psnr"])


def test_before_after_table_has_every_method_and_no_empty_cells():
    clean, noisy = _sample_images()
    points = _load_enhancement_module("point_operations")
    histograms = _load_enhancement_module("histogram_mapping")
    filters = _load_enhancement_module("spatial_filters")
    enhanced = {
        "gamma": points.gamma(noisy, 0.8),
        "log": points.log_transform(noisy),
        "contrast_stretch": points.contrast_stretch(noisy),
        "equalization": histograms.equalize(noisy),
        "histogram_matching": histograms.match_histogram(noisy, clean),
        "box": filters.box(noisy),
        "gaussian": filters.gaussian(noisy),
        "median": filters.median(noisy),
    }
    rows = quality_metrics.before_after_table(clean, noisy, enhanced)
    assert [row["method"] for row in rows] == list(quality_metrics.REQUIRED_ENHANCEMENT_METHODS)
    assert all(np.isfinite(value) for row in rows for key, value in row.items() if key != "method")
    assert rows[-1]["after_psnr"] > rows[-1]["before_psnr"]


def test_table_rejects_a_missing_enhancement_method():
    clean, noisy = _sample_images()
    with pytest.raises(ValueError, match="median"):
        quality_metrics.before_after_table(clean, noisy, {
            "gamma": noisy, "equalization": noisy, "box": noisy, "gaussian": noisy,
        })


def test_csv_contains_header_and_all_rows(tmp_path):
    rows = [{
        "method": name,
        "before_psnr": 20.0,
        "after_psnr": 25.0,
        "psnr_change": 5.0,
        "before_ssim": 0.7,
        "after_ssim": 0.9,
        "ssim_change": 0.2,
    } for name in quality_metrics.REQUIRED_ENHANCEMENT_METHODS]
    output = tmp_path / "quality.csv"
    quality_metrics.write_csv(rows, output)
    with output.open(newline="", encoding="utf-8") as source:
        saved = list(csv.DictReader(source))
    assert len(saved) == 8
    assert saved[0]["method"] == "gamma"
    assert all(value != "" for row in saved for value in row.values())


@pytest.mark.parametrize("candidate", [None, np.array([], dtype=np.uint8), np.zeros((8, 7), dtype=np.uint8)])
def test_invalid_or_mismatched_images_are_rejected(candidate):
    reference = np.zeros((8, 8), dtype=np.uint8)
    with pytest.raises(ValueError):
        quality_metrics.image_quality(reference, candidate)
