"""Check that the two timed box-filter paths produce the same image."""

import csv
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


class _EndpointResponse:
    status_code = 200
    content = b"{}"

    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self.body


class _EndpointSession:
    def __init__(self):
        self.cookies = {"csrf_token": "benchmark-token"}

    def get(self, url, timeout):
        assert url.endswith("/api/assets?per_page=20")
        assert timeout == 10
        return _EndpointResponse({"items": [], "total": 0})

    def post(self, url, json, headers, timeout):
        assert headers == {"X-CSRFToken": "benchmark-token"}
        assert timeout == 10
        if url.endswith("/api/img2img"):
            return _EndpointResponse({"status": "success", "asset_id": 1})
        if url.endswith("/api/pipeline/blur-region"):
            return _EndpointResponse({"image": "aW1hZ2U="})
        if url.endswith("/api/pipeline/find-objects"):
            return _EndpointResponse({"objects": [], "count": 0})
        if url.endswith("/api/pipeline/palette/extract"):
            return _EndpointResponse({"colors": ["#ff0000"]})
        raise AssertionError(f"unexpected endpoint {url}")


def test_endpoint_baseline_records_each_route_and_balances_order(tmp_path, monkeypatch):
    monkeypatch.setattr(
        benchmark,
        "_authenticated_session",
        lambda backend_url: _EndpointSession(),
    )

    summary = benchmark.record_endpoint_baseline(
        tmp_path,
        "http://backend.test/",
        repeats=5,
        timeout=10,
        image_size=512,
    )

    assert len(summary) == 5
    assert all(row["samples"] == 5 and row["p50_s"] >= 0 for row in summary)
    with (tmp_path / "endpoint_latency_raw.csv").open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == 25
    assert {row["status_code"] for row in rows} == {"200"}
    for endpoint in {row["endpoint"] for row in rows}:
        positions = [int(row["position"]) for row in rows if row["endpoint"] == endpoint]
        assert sorted(positions) == [1, 2, 3, 4, 5]
    for filename in (
        "endpoint_latency_summary.csv",
        "endpoint_latency_metadata.json",
        "endpoint_latency.png",
    ):
        assert (tmp_path / filename).is_file()


@pytest.mark.parametrize(("repeats", "timeout", "image_size"), [
    (1, 10, 512),
    (True, 10, 512),
    (5, 0, 512),
    (5, True, 512),
    (5, 10, 32),
    (5, 10, True),
])
def test_endpoint_baseline_rejects_invalid_settings(
        tmp_path, repeats, timeout, image_size):
    with pytest.raises(ValueError):
        benchmark.record_endpoint_baseline(
            tmp_path,
            "http://backend.test",
            repeats=repeats,
            timeout=timeout,
            image_size=image_size,
        )
