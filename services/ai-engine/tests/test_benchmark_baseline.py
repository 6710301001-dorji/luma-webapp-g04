"""Check that the two timed box-filter paths produce the same image."""

import importlib.util
from pathlib import Path

import numpy as np


path = Path(__file__).resolve().parents[1] / "pipeline/05_evaluation/benchmark_baseline.py"
spec = importlib.util.spec_from_file_location("benchmark_baseline", path)
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def test_box_filter_comparison_is_numerically_equivalent():
    image = np.random.default_rng(68).integers(0, 256, (64, 64), dtype=np.uint8)
    result = benchmark.benchmark_box_filter(image, kernel_size=15, repeats=2)
    assert result["max_pixel_difference"] < 0.001
    assert result["box_2d_ms"] > 0
    assert result["box_separable_ms"] > 0
