"""Check that the two timed box-filter paths produce the same image."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest


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


def test_latency_summary_reports_percentiles():
    result = benchmark.latency_summary([1.0, 2.0, 3.0, 4.0])
    assert result["samples"] == 4
    assert result["min_s"] == 1.0
    assert result["p50_s"] == 2.5
    assert result["p95_s"] == pytest.approx(3.85)
    assert result["max_s"] == 4.0


@pytest.mark.parametrize("samples", [[], [-1], [True], ["1"]])
def test_latency_summary_rejects_unusable_samples(samples):
    with pytest.raises(ValueError):
        benchmark.latency_summary(samples)


def test_generation_trials_balance_step_counts_across_positions():
    order = benchmark.generation_trial_order((10, 20, 30), repeats=3)

    assert order == [
        (1, 1, 10), (1, 2, 20), (1, 3, 30),
        (2, 1, 20), (2, 2, 30), (2, 3, 10),
        (3, 1, 30), (3, 2, 10), (3, 3, 20),
    ]
    for step_count in (10, 20, 30):
        positions = [position for _, position, step in order if step == step_count]
        assert sorted(positions) == [1, 2, 3]


@pytest.mark.parametrize(("steps", "repeats"), [
    ((), 3),
    ((10, 10), 3),
    ((True, 20), 3),
    ((0, 20), 3),
    ((10, 20), 0),
    ((10, 20), True),
])
def test_generation_trial_order_rejects_invalid_inputs(steps, repeats):
    with pytest.raises(ValueError):
        benchmark.generation_trial_order(steps, repeats)
